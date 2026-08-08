import subprocess
from pathlib import Path

import pytest

from openlease import AuthorityConflict, OpenLease
from openlease.core.graph import AccessRole
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


def _system(tmp_path: Path) -> tuple[OpenLease, dict[str, Path], MemoryOpenSpec]:
    repos = {
        name: _repository(tmp_path / name) for name in ("repo-1", "repo-2", "repo-3")
    }
    openspec = MemoryOpenSpec()
    system = OpenLease(
        tmp_path / "state",
        worktree_base=tmp_path / "worktrees",
        openspec=openspec,  # type: ignore[arg-type]
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


def test_repeated_lock_is_a_compatible_noop(tmp_path: Path) -> None:
    system, _, _ = _system(tmp_path)
    _space(system, "child-a", "a")
    first = system.lock("child-a")
    second = system.lock("child-a")

    assert first.data == second.data
    assert second.outcome == "compatible_noop"
    assert second.changed is False
