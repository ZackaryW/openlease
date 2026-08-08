import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

import openlease.cli
from openlease.cli import app
from openlease.result import CommandResult


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


def test_session_attach_prints_the_parent_shell_selection(tmp_path: Path) -> None:
    runner = CliRunner()
    state_root = tmp_path / "state"
    runner.invoke(
        app,
        ["--state-root", str(state_root), "session", "start", "example"],
    )

    attached = runner.invoke(
        app,
        ["--state-root", str(state_root), "session", "attach", "example"],
    )

    assert attached.exit_code == 0
    assert attached.stdout == "OPENLEASE_SPACE=example\n"


def test_cli_preserves_an_omitted_worktree_base(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, Path | None] = {}

    class FakeOpenLease:
        def __init__(self, state_root: Path, *, worktree_base: Path | None) -> None:
            captured["state_root"] = state_root
            captured["worktree_base"] = worktree_base

        def status(self, space):
            del space
            return CommandResult("status", changed=False, data={})

    monkeypatch.setattr(openlease.cli, "OpenLease", FakeOpenLease)

    result = CliRunner().invoke(
        app,
        ["--state-root", str(tmp_path / "state"), "status"],
        env={"OPENLEASE_WORKTREE_BASE": ""},
    )

    assert result.exit_code == 0
    assert captured["worktree_base"] is None


def test_cli_retains_the_environment_worktree_base_override(
    tmp_path: Path, monkeypatch
) -> None:
    captured: dict[str, Path | None] = {}

    class FakeOpenLease:
        def __init__(self, state_root: Path, *, worktree_base: Path | None) -> None:
            del state_root
            captured["worktree_base"] = worktree_base

        def status(self, space):
            del space
            return CommandResult("status", changed=False, data={})

    monkeypatch.setattr(openlease.cli, "OpenLease", FakeOpenLease)
    configured = tmp_path / "automation-worktrees"

    result = CliRunner().invoke(
        app,
        ["--state-root", str(tmp_path / "state"), "status"],
        env={"OPENLEASE_WORKTREE_BASE": str(configured)},
    )

    assert result.exit_code == 0
    assert captured["worktree_base"] == configured.resolve()
