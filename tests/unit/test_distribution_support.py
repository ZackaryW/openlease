from __future__ import annotations

import os
from pathlib import Path
from zipfile import ZipFile

import pytest

from features.support.distribution import (
    DistributionArtifact,
    DistributionProbe,
    accepts_python,
    read_requires_python,
)
from openlease.utils.processes import ProcessAdapterError, ProcessResult


class RecordingRunner:
    def __init__(self, results: tuple[ProcessResult, ...] = ()) -> None:
        self.results = list(results)
        self.calls: list[tuple[tuple[str, ...], Path | None]] = []

    def run(self, arguments, *, cwd=None, env=None):
        del env
        self.calls.append((arguments, cwd))
        if self.results:
            return self.results.pop(0)
        return ProcessResult(arguments, 0, "", "")


def _wheel(path: Path, members: dict[str, str]) -> Path:
    with ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


def test_reads_requires_python_from_one_wheel_metadata_member(tmp_path: Path) -> None:
    wheel = _wheel(
        tmp_path / "openlease.whl",
        {
            "openlease-0.1.0.dist-info/METADATA": (
                "Metadata-Version: 2.4\n"
                "Name: openlease\n"
                "Version: 0.1.0\n"
                "Requires-Python: >=3.11\n"
            )
        },
    )

    assert read_requires_python(wheel) == ">=3.11"


@pytest.mark.parametrize(
    "members",
    (
        {},
        {
            "first.dist-info/METADATA": "Requires-Python: >=3.11\n",
            "second.dist-info/METADATA": "Requires-Python: >=3.11\n",
        },
        {"openlease.dist-info/METADATA": "Name: openlease\n"},
    ),
)
def test_rejects_missing_ambiguous_or_incomplete_metadata(
    tmp_path: Path, members: dict[str, str]
) -> None:
    wheel = _wheel(tmp_path / "invalid.whl", members)

    with pytest.raises(ValueError, match="wheel metadata"):
        read_requires_python(wheel)


def test_evaluates_python_versions_with_pep_440_specifiers() -> None:
    assert accepts_python(">=3.11", "3.11") is True
    assert accepts_python(">=3.11", "3.14") is True
    assert accepts_python(">=3.11", "3.10") is False


def test_builds_one_wheel_with_a_literal_uv_argument_vector(tmp_path: Path) -> None:
    output = tmp_path / "dist"
    output.mkdir()
    wheel = _wheel(
        output / "openlease-0.1.0-py3-none-any.whl",
        {"openlease-0.1.0.dist-info/METADATA": "Requires-Python: >=3.11\n"},
    )
    runner = RecordingRunner()
    project = tmp_path / "project"
    python = tmp_path / "python"

    artifact = DistributionProbe(project, runner).build(output, python=python)

    assert artifact.wheel == wheel
    assert artifact.requires_python == ">=3.11"
    assert runner.calls == [
        (
            (
                "uv",
                "build",
                "--wheel",
                "--out-dir",
                str(output),
                "--python",
                str(python),
                str(project),
            ),
            project,
        )
    ]


def test_creates_and_installs_base_and_extra_in_an_isolated_environment(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner()
    probe = DistributionProbe(tmp_path / "project", runner)
    environment = tmp_path / "environment"
    source_python = tmp_path / "python"
    artifact = DistributionArtifact(tmp_path / "openlease.whl", ">=3.11")

    environment_python = probe.create_environment(environment, python=source_python)
    probe.install(environment_python, artifact)
    probe.install(environment_python, artifact, extra="cli")

    expected_python = (
        environment / "Scripts" / "python.exe"
        if os.name == "nt"
        else environment / "bin" / "python"
    )
    assert environment_python == expected_python
    assert runner.calls == [
        (
            (
                "uv",
                "venv",
                str(environment),
                "--python",
                str(source_python),
                "--no-project",
            ),
            tmp_path / "project",
        ),
        (
            (
                "uv",
                "pip",
                "install",
                "--python",
                str(expected_python),
                str(artifact.wheel),
            ),
            tmp_path / "project",
        ),
        (
            (
                "uv",
                "pip",
                "install",
                "--python",
                str(expected_python),
                f"{artifact.wheel}[cli]",
            ),
            tmp_path / "project",
        ),
    ]


def test_invokes_the_installed_interpreter_outside_the_source_tree(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner()
    probe = DistributionProbe(tmp_path / "project", runner)
    python = tmp_path / "environment" / "Scripts" / "python.exe"

    result = probe.invoke(python, ("-c", "import openlease"))

    assert result.returncode == 0
    assert runner.calls == [
        (
            (str(python), "-c", "import openlease"),
            tmp_path / "environment",
        )
    ]


def test_reports_a_bounded_build_failure(tmp_path: Path) -> None:
    arguments = ("uv", "build")
    runner = RecordingRunner((ProcessResult(arguments, 1, "", "build failed " * 1000),))

    with pytest.raises(ProcessAdapterError, match="distribution build failed") as error:
        DistributionProbe(tmp_path, runner).build(
            tmp_path / "dist", python=tmp_path / "python"
        )

    assert len(str(error.value)) < 4100
