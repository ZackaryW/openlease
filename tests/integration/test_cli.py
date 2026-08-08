import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from openlease.cli import app


def test_base_import_does_not_import_typer() -> None:
    completed = subprocess.run(
        (
            sys.executable,
            "-c",
            "import sys; import openlease; assert 'typer' not in sys.modules",
        ),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr


def test_cli_reads_the_same_public_state_and_emits_one_json_envelope(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    state_root = tmp_path / "state"

    created = runner.invoke(
        app,
        ["--state-root", str(state_root), "space", "create", "example"],
    )
    status = runner.invoke(
        app,
        ["--state-root", str(state_root), "--json", "status", "--space", "example"],
    )

    assert created.exit_code == 0
    assert status.exit_code == 0
    envelope = json.loads(status.stdout)
    assert envelope["ok"] is True
    assert envelope["operation"] == "status"
    assert envelope["data"]["spaces"][0]["identifier"] == "example"
    assert status.stdout.count("\n") == 1


def test_domain_failure_uses_stable_status_without_traceback(tmp_path: Path) -> None:
    runner = CliRunner()
    state_root = tmp_path / "state"
    runner.invoke(
        app,
        ["--state-root", str(state_root), "space", "create", "example"],
    )

    failed = runner.invoke(
        app,
        ["--state-root", str(state_root), "--space", "example", "lock"],
    )

    assert failed.exit_code == 2
    assert "Traceback" not in failed.stderr
    assert json.loads(failed.stderr)["outcome"] == "invalid_request"
