import subprocess
from pathlib import Path

import pytest

from openlease.utils import processes
from openlease.utils.processes import ProcessAdapterError, SubprocessRunner


def test_runs_an_argument_vector_without_a_shell(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: dict[str, object] = {}

    def fake_run(arguments, **options):
        observed["arguments"] = arguments
        observed.update(options)
        return subprocess.CompletedProcess(arguments, 0, "ok\n", "")

    monkeypatch.setattr(processes.subprocess, "run", fake_run)

    result = SubprocessRunner().run(("git", "status"), cwd=tmp_path)

    assert result.stdout == "ok\n"
    assert observed["arguments"] == ("git", "status")
    assert observed["shell"] is False


def test_required_failure_retains_bounded_diagnostics() -> None:
    result = processes.ProcessResult(("git", "status"), 1, "", "bad state" * 1000)

    with pytest.raises(ProcessAdapterError) as captured:
        processes.require_success(result, "Git status")

    assert "Git status failed" in str(captured.value)
    assert "bad state" in str(captured.value)
    assert len(str(captured.value)) < 4100
