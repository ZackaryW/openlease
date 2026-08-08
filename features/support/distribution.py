"""Undecorated distribution probes for compatibility behavior."""

from __future__ import annotations

import os
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from openlease.utils.processes import (
    ProcessResult,
    ProcessRunner,
    require_success,
)


@dataclass(frozen=True, slots=True)
class DistributionArtifact:
    wheel: Path
    requires_python: str


class DistributionProbe:
    def __init__(
        self, project_root: Path, runner: ProcessRunner, uv: str = "uv"
    ) -> None:
        self.project_root = project_root
        self.runner = runner
        self.uv = uv

    def build(self, output_dir: Path, *, python: Path) -> DistributionArtifact:
        output_dir.mkdir(parents=True, exist_ok=True)
        result = self.runner.run(
            (
                self.uv,
                "build",
                "--wheel",
                "--out-dir",
                str(output_dir),
                "--python",
                str(python),
                str(self.project_root),
            ),
            cwd=self.project_root,
        )
        require_success(result, "distribution build")
        wheels = tuple(output_dir.glob("*.whl"))
        if len(wheels) != 1:
            raise ValueError("distribution build must produce exactly one wheel")
        return DistributionArtifact(wheels[0], read_requires_python(wheels[0]))

    def create_environment(self, root: Path, *, python: Path) -> Path:
        result = self.runner.run(
            (
                self.uv,
                "venv",
                str(root),
                "--python",
                str(python),
                "--no-project",
            ),
            cwd=self.project_root,
        )
        require_success(result, "environment creation")
        if os.name == "nt":
            return root / "Scripts" / "python.exe"
        return root / "bin" / "python"

    def install(
        self,
        environment_python: Path,
        artifact: DistributionArtifact,
        *,
        extra: str | None = None,
    ) -> None:
        requirement = str(artifact.wheel)
        if extra is not None:
            requirement = f"{requirement}[{extra}]"
        result = self.runner.run(
            (
                self.uv,
                "pip",
                "install",
                "--python",
                str(environment_python),
                requirement,
            ),
            cwd=self.project_root,
        )
        require_success(result, "distribution installation")

    def invoke(
        self, environment_python: Path, arguments: tuple[str, ...]
    ) -> ProcessResult:
        return self.runner.run(
            (str(environment_python), *arguments),
            cwd=environment_python.parent.parent,
        )


def read_requires_python(wheel: Path) -> str:
    with ZipFile(wheel) as archive:
        metadata_members = tuple(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        if len(metadata_members) != 1:
            raise ValueError("wheel metadata must contain exactly one METADATA member")
        metadata = BytesParser().parsebytes(archive.read(metadata_members[0]))

    values = metadata.get_all("Requires-Python", ())
    if len(values) != 1 or not values[0].strip():
        raise ValueError("wheel metadata must contain one Requires-Python field")
    return values[0].strip()


def accepts_python(specifier: str, version: str) -> bool:
    return Version(version) in SpecifierSet(specifier)
