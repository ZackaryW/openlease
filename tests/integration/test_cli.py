import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

import openlease.cli
from openlease import OpenLease
from openlease.cli import app
from openlease.result import CommandResult


def _repository(path: Path) -> Path:
    path.mkdir()
    for arguments in (
        ("init", "--quiet"),
        ("config", "user.email", "cli@openlease.invalid"),
        ("config", "user.name", "OpenLease CLI Tests"),
        ("commit", "--allow-empty", "--quiet", "-m", "base"),
    ):
        subprocess.run(
            ("git", "-C", str(path), *arguments),
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    return path


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


def test_cli_reuses_and_closes_a_cwd_temporary_space(
    tmp_path: Path, monkeypatch
) -> None:
    runner = CliRunner()
    state_root = tmp_path / "state"
    repository = _repository(tmp_path / "repo")
    OpenLease(state_root).register_repository("repo", repository)
    monkeypatch.chdir(repository)
    environment = {"OPENLEASE_SESSION_TOKEN": "host-session"}

    first = runner.invoke(
        app,
        ["--state-root", str(state_root), "--json", "status"],
        env=environment,
    )
    second = runner.invoke(
        app,
        ["--state-root", str(state_root), "--json", "status"],
        env=environment,
    )
    closed = runner.invoke(
        app,
        ["--state-root", str(state_root), "--json", "session", "close"],
        env=environment,
    )

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    first_space = json.loads(first.stdout)["data"]["spaces"][0]
    second_space = json.loads(second.stdout)["data"]["spaces"][0]
    assert second_space["identifier"] == first_space["identifier"]
    assert second_space["temporary"]["session_fingerprint"]
    assert json.loads(closed.stdout)["data"]["removed"] == [first_space["identifier"]]
    assert OpenLease(state_root).snapshot().spaces == ()


def test_cli_explicit_space_precedes_cwd_session_selection(
    tmp_path: Path, monkeypatch
) -> None:
    state_root = tmp_path / "state"
    repository = _repository(tmp_path / "repo")
    system = OpenLease(state_root)
    system.register_repository("repo", repository)
    system.create_space("durable")
    monkeypatch.chdir(repository)

    selected = CliRunner().invoke(
        app,
        [
            "--state-root",
            str(state_root),
            "--space",
            "durable",
            "--json",
            "status",
        ],
        env={"OPENLEASE_SESSION_TOKEN": "host-session"},
    )

    assert selected.exit_code == 0, selected.output
    assert json.loads(selected.stdout)["data"]["spaces"][0]["identifier"] == "durable"
    assert tuple(space.identifier for space in system.snapshot().spaces) == ("durable",)


def test_cli_reports_an_invalid_cwd_session_without_a_traceback(
    tmp_path: Path, monkeypatch
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)

    failed = CliRunner().invoke(
        app,
        ["--state-root", str(tmp_path / "state"), "--json", "status"],
        env={"OPENLEASE_SESSION_TOKEN": "host-session"},
    )

    assert failed.exit_code == 2
    assert "Traceback" not in failed.stderr
    assert json.loads(failed.stderr)["outcome"] == "invalid_request"


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


def test_cli_configures_and_inspects_namespaced_extension_roots(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    state_root = tmp_path / "state"
    product_root = tmp_path / ".zpp"

    configured = runner.invoke(
        app,
        [
            "--state-root",
            str(state_root),
            "extension",
            "roots-set",
            "zpp",
            "--product-root",
            str(product_root),
        ],
    )
    inspected = runner.invoke(
        app,
        [
            "--state-root",
            str(state_root),
            "--json",
            "extension",
            "roots-show",
            "zpp",
        ],
    )

    assert configured.exit_code == 0, configured.output
    assert inspected.exit_code == 0, inspected.output
    roots = json.loads(inspected.stdout)["data"]
    assert Path(roots["configuration"]["path"]).is_relative_to(product_root)
    assert roots["configuration"]["provenance"] == "product_root"


def test_cli_binds_and_resolves_a_managed_extension_document(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    state_root = tmp_path / "state"
    repository = _repository(tmp_path / "repo")
    source = tmp_path / "traits.json"
    source.write_text('{"zpp": {"traits": "current"}}', encoding="utf-8")

    commands = (
        ("register", "repository", "repo", str(repository)),
        ("space", "create", "work"),
        ("associate", "repo", "--space", "work"),
        (
            "config",
            "bind",
            "zpp",
            "machine",
            str(source),
            "--scope",
            "machine",
            "--codec",
            "json",
            "--layout",
            "shared",
        ),
    )
    for command in commands:
        completed = runner.invoke(app, ["--state-root", str(state_root), *command])
        assert completed.exit_code == 0, completed.output

    resolved = runner.invoke(
        app,
        [
            "--state-root",
            str(state_root),
            "--json",
            "extension",
            "context",
            "zpp",
            "--space",
            "work",
            "--repository",
            "repo",
        ],
    )

    assert resolved.exit_code == 0, resolved.output
    data = json.loads(resolved.stdout)["data"]
    assert data["configuration"]["values"] == {"traits": "current"}
    assert data["configuration"]["bindings"][0]["identifier"] == "machine"


def test_cli_manages_pack_attachments_and_source_removal(tmp_path: Path) -> None:
    runner = CliRunner()
    state_root = tmp_path / "state"
    source = tmp_path / "pack.json"
    source.write_text('{"zpp": {"pack": true}}', encoding="utf-8")
    commands = (
        ("space", "create", "work"),
        ("pack", "define", "zpp", "backend"),
        ("pack", "attach", "zpp", "backend", "--space", "work", "--order", "2"),
        (
            "config",
            "bind",
            "zpp",
            "pack-source",
            str(source),
            "--scope",
            "pack",
            "--scope-id",
            "backend",
            "--codec",
            "json",
            "--layout",
            "shared",
        ),
        ("config", "remove", "zpp", "pack-source"),
        ("pack", "detach", "zpp", "backend", "--space", "work"),
    )

    for command in commands:
        completed = runner.invoke(app, ["--state-root", str(state_root), *command])
        assert completed.exit_code == 0, completed.output

    state = OpenLease(state_root).snapshot()
    assert state.configuration_sources == ()
    assert state.space_pack_attachments == ()
    assert state.configuration_packs[0].identifier == "backend"


def test_cli_rejects_an_ambiguous_extension_target_without_partial_state(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    state_root = tmp_path / "state"
    runner.invoke(app, ["--state-root", str(state_root), "space", "create", "work"])
    before = OpenLease(state_root).snapshot()

    failed = runner.invoke(
        app,
        [
            "--state-root",
            str(state_root),
            "extension",
            "context",
            "zpp",
            "--space",
            "work",
            "--repository",
            "repo",
            "--authority",
            "authority",
        ],
    )

    assert failed.exit_code == 2
    assert json.loads(failed.stderr)["outcome"] == "invalid_request"
    assert OpenLease(state_root).snapshot() == before


def test_cli_configuration_failure_includes_stable_code(tmp_path: Path) -> None:
    runner = CliRunner()
    state_root = tmp_path / "state"
    repository = _repository(tmp_path / "repo")
    source = tmp_path / "invalid.json"
    source.write_text("not-json", encoding="utf-8")
    commands = (
        ("register", "repository", "repo", str(repository)),
        ("space", "create", "work"),
        ("associate", "repo", "--space", "work"),
    )
    for command in commands:
        completed = runner.invoke(app, ["--state-root", str(state_root), *command])
        assert completed.exit_code == 0, completed.output

    failed = runner.invoke(
        app,
        [
            "--state-root",
            str(state_root),
            "--json",
            "config",
            "bind",
            "zpp",
            "machine",
            str(source),
            "--scope",
            "machine",
            "--codec",
            "json",
            "--layout",
            "dedicated",
        ],
    )

    assert failed.exit_code == 2
    envelope = json.loads(failed.stderr)
    assert envelope["code"] == "configuration_decode_failed"
    assert envelope["outcome"] == "invalid_request"
