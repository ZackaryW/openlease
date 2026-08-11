import subprocess
from pathlib import Path

import pytest

from openlease import (
    AuthorityConflict,
    CallbackEvent,
    CallbackMode,
    CallbackSelection,
    ExtensionCallback,
    ExtensionManifest,
    ExtensionOperation,
    ExtensionRegistration,
    InvalidRequest,
    OpenLease,
    PreparationFailed,
    ReconcileSelection,
)
from openlease.core.graph import AccessRole
from openlease.utils.git_adapter import IntegrationStrategy
from openlease.utils.openspec_adapter import OpenSpecWorkset


def _git(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ("git", "-C", str(repo), *arguments),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _repository(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "--quiet")
    _git(path, "config", "user.email", "tests@openlease.invalid")
    _git(path, "config", "user.name", "OpenLease Tests")
    _git(path, "commit", "--allow-empty", "--quiet", "-m", "base")
    return path


class MemoryOpenSpec:
    def __init__(self) -> None:
        self.worksets: dict[str, OpenSpecWorkset] = {}

    def list_worksets(self) -> tuple[OpenSpecWorkset, ...]:
        return tuple(self.worksets.values())

    def create_workset(self, name: str, members: tuple[Path, ...]) -> None:
        if name in self.worksets:
            raise ValueError("workset exists")
        self.worksets[name] = OpenSpecWorkset(name, members)

    def open_workset(self, name: str, tool: str | None = None) -> None:
        del tool
        if name not in self.worksets:
            raise ValueError("workset missing")

    def remove_workset(self, name: str) -> None:
        del self.worksets[name]


def _system(
    tmp_path: Path, *, extensions=()
) -> tuple[OpenLease, dict[str, Path], MemoryOpenSpec]:
    repos = {
        name: _repository(tmp_path / name) for name in ("repo-1", "repo-2", "repo-3")
    }
    openspec = MemoryOpenSpec()
    system = OpenLease(
        tmp_path / "state",
        worktree_base=tmp_path / "worktrees",
        openspec=openspec,  # type: ignore[arg-type]
        extensions=extensions,
    )
    for name, path in repos.items():
        system.register_repository(name, path)
    system.register_authority("root", "repo-1")
    system.register_authority("a", "repo-1", "A/openspec")
    system.register_authority("b", "repo-1", "B/openspec")
    system.register_authority("shared", "repo-3")
    system.relate_parent("a", "root")
    system.relate_parent("b", "root")
    system.relate_dependency("repo-2", "shared", AccessRole.WRITABLE)
    return system, repos, openspec


def _space(system: OpenLease, name: str, authority: str) -> None:
    system.create_space(name)
    system.associate(name, ("repo-1", "repo-2", "repo-3"))
    system.set_affected(name, authority_ids=(authority,))


def test_session_cwd_scaffolds_and_reuses_one_temporary_draft(
    tmp_path: Path,
) -> None:
    system, repos, _ = _system(tmp_path)
    nested = repos["repo-1"] / "nested"
    nested.mkdir()

    first = system.resolve_session_space(nested, "host-session").data
    second = system.resolve_session_space(repos["repo-1"], "host-session").data

    assert second.identifier == first.identifier
    assert first.associated_repository_ids == ("repo-1",)
    assert first.affected_repository_ids == ()
    assert first.affected_authority_ids == ()
    assert first.held_authority_ids == ()
    assert first.temporary is not None
    assert first.temporary.worktree_path == str(repos["repo-1"].resolve())
    assert len(system.snapshot().spaces) == 1


def test_session_cwd_rejects_an_unregistered_worktree_without_state_change(
    tmp_path: Path,
) -> None:
    registered = _repository(tmp_path / "registered")
    unregistered = _repository(tmp_path / "unregistered")
    system = OpenLease(tmp_path / "state")
    system.register_repository("registered", registered)
    before = system.snapshot()

    with pytest.raises(InvalidRequest, match="exactly one"):
        system.resolve_session_space(unregistered, "host-session")

    assert system.snapshot() == before


def test_session_cwd_reports_a_non_git_directory_as_invalid(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    system = OpenLease(tmp_path / "state")

    with pytest.raises(InvalidRequest, match="Git checkout inspection"):
        system.resolve_session_space(outside, "host-session")

    assert system.snapshot().spaces == ()


def test_new_session_reclaims_an_abandoned_disposable_draft(tmp_path: Path) -> None:
    system, repos, _ = _system(tmp_path)

    abandoned = system.resolve_session_space(repos["repo-1"], "session-a").data
    reclaimed = system.resolve_session_space(repos["repo-1"], "session-b").data

    assert reclaimed.identifier == abandoned.identifier
    assert reclaimed.temporary != abandoned.temporary
    assert len(system.snapshot().spaces) == 1


def test_closing_a_session_removes_only_its_disposable_draft(tmp_path: Path) -> None:
    system, repos, _ = _system(tmp_path)
    temporary = system.resolve_session_space(repos["repo-1"], "session-a").data
    system.create_space("durable")

    closed = system.close_temporary_session("session-a")

    assert closed.data["removed"] == (temporary.identifier,)
    assert tuple(space.identifier for space in system.snapshot().spaces) == ("durable",)


def test_lock_atomically_promotes_a_temporary_space(tmp_path: Path) -> None:
    system, repos, _ = _system(tmp_path)
    temporary = system.resolve_session_space(repos["repo-1"], "session-a").data
    system.set_affected(temporary.identifier, authority_ids=("a",))

    locked = system.lock(temporary.identifier).data

    assert locked.status == "locked"
    assert locked.held_authority_ids == ("a",)
    assert locked.temporary is None
    assert system.close_temporary_session("session-a").changed is False
    assert system.status(temporary.identifier).data["spaces"] == (locked,)


def test_space_scoped_configuration_promotes_before_a_new_session_selects(
    tmp_path: Path,
) -> None:
    registration = ExtensionRegistration(ExtensionManifest("extension"))
    system, repos, _ = _system(tmp_path, extensions=(registration,))
    temporary = system.resolve_session_space(repos["repo-1"], "session-a").data
    system.define_configuration_pack("extension", "defaults")

    system.attach_configuration_pack(temporary.identifier, "extension", "defaults")
    selected = system.resolve_session_space(repos["repo-1"], "session-b").data

    retained = system.status(temporary.identifier).data["spaces"][0]
    assert retained.temporary is None
    assert selected.identifier != retained.identifier
    assert selected.temporary is not None


def test_space_scoped_configuration_source_promotes_a_temporary_space(
    tmp_path: Path,
) -> None:
    registration = ExtensionRegistration(ExtensionManifest("extension"))
    system, repos, _ = _system(tmp_path, extensions=(registration,))
    temporary = system.resolve_session_space(repos["repo-1"], "session-a").data
    source = repos["repo-1"] / "configuration.json"
    source.write_text("{}", encoding="utf-8")

    system.bind_configuration_source(
        "extension",
        "local",
        source,
        "space",
        temporary.identifier,
        codec="json",
        layout="dedicated",
    )

    retained = system.status(temporary.identifier).data["spaces"][0]
    assert retained.temporary is None


def test_opening_a_projection_promotes_a_temporary_space(tmp_path: Path) -> None:
    system, repos, _ = _system(tmp_path)
    temporary = system.resolve_session_space(repos["repo-1"], "session-a").data
    system.set_affected(temporary.identifier, authority_ids=("a",))

    opened = system.open(temporary.identifier).data

    assert opened.projection_name is not None
    assert opened.temporary is None


def test_sibling_spaces_lock_while_parent_conflicts(tmp_path: Path) -> None:
    system, _, _ = _system(tmp_path)
    _space(system, "child-a", "a")
    _space(system, "child-b", "b")
    _space(system, "parent", "root")

    system.lock("child-a")
    system.lock("child-b")

    with pytest.raises(AuthorityConflict) as caught:
        system.lock("parent")
    assert {item.authority_id for item in caught.value.details} == {"a", "b"}


def test_defer_generates_only_the_affected_repository(tmp_path: Path) -> None:
    system, repos, openspec = _system(tmp_path)
    _space(system, "blocker", "a")
    system.lock("blocker")
    _space(system, "request", "a")

    result = system.defer("request", "successor")
    successor = result.data

    assert successor.status == "deferred"
    generated = [item for item in successor.members if item.generated]
    pinned = [item for item in successor.members if not item.generated]
    assert [item.repository_id for item in generated] == ["repo-1"]
    assert [item.repository_id for item in pinned] == ["repo-2", "repo-3"]
    assert Path(generated[0].effective_path).exists()
    assert Path(pinned[0].effective_path) == repos["repo-2"].resolve()
    assert "openlease-successor" in openspec.worksets


def test_external_writable_closure_generates_consumer_and_provider(
    tmp_path: Path,
) -> None:
    system, _, _ = _system(tmp_path)
    system.create_space("blocker")
    system.associate("blocker", ("repo-3",))
    system.set_affected("blocker", authority_ids=("shared",))
    system.lock("blocker")
    system.create_space("request")
    system.associate("request", ("repo-1", "repo-2", "repo-3"))
    system.set_affected("request", repository_ids=("repo-2",))

    successor = system.defer("request", "external-successor").data

    assert {item.repository_id for item in successor.members if item.generated} == {
        "repo-2",
        "repo-3",
    }
    authority_path = system.authority_path("external-successor", "shared")
    repo3_member = next(
        item for item in successor.members if item.repository_id == "repo-3"
    )
    assert authority_path == Path(repo3_member.effective_path) / "openspec"


def test_failed_preparation_reservation_consumes_its_exact_destination(
    tmp_path: Path,
) -> None:
    system, _, _ = _system(tmp_path)
    _space(system, "blocker", "a")
    system.lock("blocker")
    _space(system, "request", "a")
    delegate = system.git

    class FailCreation:
        def __getattr__(self, name):
            return getattr(delegate, name)

        def create_worktree(self, source, request):
            del source, request
            raise RuntimeError("injected failure before Git mutation")

    system.git = FailCreation()
    with pytest.raises(PreparationFailed):
        system.defer("request", "failed-successor")
    failed = system.status("failed-successor").data["spaces"][0]
    reserved = next(item for item in failed.members if item.generated)
    assert Path(reserved.effective_path).name == "repo-1-olease-1"
    assert not Path(reserved.effective_path).exists()

    system.git = delegate
    successor = system.defer("request", "next-successor").data

    generated = next(item for item in successor.members if item.generated)
    assert Path(generated.effective_path).name == "repo-1-olease-2"


def test_git_registered_missing_worktree_path_consumes_its_suffix(
    tmp_path: Path,
) -> None:
    system, repos, _ = _system(tmp_path)
    _space(system, "blocker", "a")
    system.lock("blocker")
    _space(system, "request", "a")
    registered = tmp_path / "worktrees" / "repo-1-olease-1"
    registered.parent.mkdir()
    _git(repos["repo-1"], "worktree", "add", "--detach", str(registered), "HEAD")
    registered.rename(tmp_path / "moved-registered-worktree")
    assert not registered.exists()

    successor = system.defer("request", "successor").data

    generated = next(item for item in successor.members if item.generated)
    assert Path(generated.effective_path).name == "repo-1-olease-2"


def test_unmanaged_symbolic_link_consumes_its_suffix(tmp_path: Path) -> None:
    system, _, _ = _system(tmp_path)
    _space(system, "blocker", "a")
    system.lock("blocker")
    _space(system, "request", "a")
    target = tmp_path / "unmanaged-target"
    target.mkdir()
    link = tmp_path / "worktrees" / "repo-1-olease-1"
    link.parent.mkdir()
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symbolic links are unavailable: {error}")

    successor = system.defer("request", "successor").data

    generated = next(item for item in successor.members if item.generated)
    assert Path(generated.effective_path).name == "repo-1-olease-2"
    assert link.is_symlink()


def test_repeated_lock_is_a_compatible_noop(tmp_path: Path) -> None:
    system, _, _ = _system(tmp_path)
    _space(system, "child-a", "a")
    first = system.lock("child-a")
    second = system.lock("child-a")

    assert first.data == second.data
    assert second.outcome == "compatible_noop"
    assert second.changed is False


def test_reconciliation_dispatches_only_selected_callbacks_in_event_order(
    tmp_path: Path,
) -> None:
    observed: list[tuple[CallbackEvent, str | None, str | None, object]] = []

    def observe(invocation):
        observed.append(
            (
                invocation.event.event,
                invocation.event.repository_id,
                invocation.event.cohort_id,
                invocation.input,
            )
        )

    registration = ExtensionRegistration(
        ExtensionManifest("zpp.behave"),
        operations=(ExtensionOperation("verify", observe),),
        callbacks=(
            ExtensionCallback(
                CallbackEvent.RECONCILE_BEFORE_REPOSITORY,
                "verify",
                (CallbackMode.OBSERVE, CallbackMode.GATE),
            ),
            ExtensionCallback(CallbackEvent.RECONCILE_AFTER_REPOSITORY, "verify"),
            ExtensionCallback(CallbackEvent.RECONCILE_AFTER_COHORT, "verify"),
        ),
    )
    system, repos, _ = _system(
        tmp_path,
        extensions=(registration,),
    )
    _space(system, "blocker", "a")
    system.lock("blocker")
    _space(system, "request", "a")
    successor = system.defer("request", "successor").data
    system.release("blocker")
    system.set_handoff_disposition("blocker", "abandoned")
    system.lock("successor")
    generated = next(item for item in successor.members if item.generated)
    worktree = Path(generated.effective_path)
    (worktree / "change.txt").write_text("change", encoding="utf-8")
    _git(worktree, "add", "change.txt")
    _git(worktree, "commit", "--quiet", "-m", "change")
    system.release("successor")
    selection = ReconcileSelection(
        "repo-1",
        _git(repos["repo-1"], "branch", "--show-current"),
        IntegrationStrategy.MERGE,
    )

    callbacks = (
        CallbackSelection(
            "zpp.behave",
            "verify",
            CallbackEvent.RECONCILE_BEFORE_REPOSITORY,
            CallbackMode.GATE,
            "repo-1",
            {"phase": "before"},
        ),
        CallbackSelection(
            "zpp.behave",
            "verify",
            CallbackEvent.RECONCILE_AFTER_REPOSITORY,
            CallbackMode.OBSERVE,
            "repo-1",
            {"phase": "after"},
        ),
        CallbackSelection(
            "zpp.behave",
            "verify",
            CallbackEvent.RECONCILE_AFTER_COHORT,
            CallbackMode.OBSERVE,
            input={"command": "bdd", "complete": True},
        ),
    )
    result = system.reconcile_apply("successor", (selection,), callbacks)

    assert result.data["completed"] == ["repo-1"]
    assert observed == [
        (
            CallbackEvent.RECONCILE_BEFORE_REPOSITORY,
            "repo-1",
            "successor",
            {"phase": "before"},
        ),
        (
            CallbackEvent.RECONCILE_AFTER_REPOSITORY,
            "repo-1",
            "successor",
            {"phase": "after"},
        ),
        (
            CallbackEvent.RECONCILE_AFTER_COHORT,
            "repo-1",
            "successor",
            {"command": "bdd", "complete": True},
        ),
    ]
