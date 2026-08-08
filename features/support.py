from __future__ import annotations

import subprocess
from pathlib import Path

from openlease import OpenLease
from openlease.core.graph import AccessRole
from openlease.utils.openspec_adapter import OpenSpecWorkset


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


def git(repo: Path, *arguments: str, check: bool = True) -> str:
    result = subprocess.run(
        ("git", "-C", str(repo), *arguments),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def repository(path: Path) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "--quiet")
    git(path, "config", "user.email", "features@openlease.invalid")
    git(path, "config", "user.name", "OpenLease Features")
    git(path, "commit", "--allow-empty", "--quiet", "-m", "base")
    return path


def ensure_repositories(context) -> None:
    if hasattr(context, "repos"):
        return
    context.repos = {
        name: repository(context.root / name) for name in ("repo-1", "repo-2", "repo-3")
    }


def ensure_topology(context) -> None:
    ensure_repositories(context)
    if context.system.snapshot().repositories:
        return
    for name, path in context.repos.items():
        context.system.register_repository(name, path)
    context.system.register_authority("root", "repo-1")
    context.system.register_authority("a", "repo-1", "A/openspec")
    context.system.register_authority("b", "repo-1", "B/openspec")
    context.system.register_authority("shared", "repo-3")
    context.system.relate_parent("a", "root")
    context.system.relate_parent("b", "root")
    context.system.relate_dependency("repo-2", "shared", AccessRole.WRITABLE)


def space(
    context,
    name: str,
    *,
    authorities: tuple[str, ...] = (),
    repositories: tuple[str, ...] = (),
    associated: tuple[str, ...] = ("repo-1", "repo-2", "repo-3"),
) -> None:
    ensure_topology(context)
    if not any(item.identifier == name for item in context.system.snapshot().spaces):
        context.system.create_space(name)
        context.system.associate(name, associated)
        if authorities or repositories:
            context.system.set_affected(
                name,
                authority_ids=authorities,
                repository_ids=repositories,
            )


def blocked_successor(context, *, external: bool = False, locked: bool = False) -> None:
    ensure_topology(context)
    if external:
        space(context, "blocker", authorities=("shared",))
        space(context, "request", repositories=("repo-2",))
    else:
        space(context, "blocker", authorities=("a",))
        space(context, "request", authorities=("a",))
    context.system.lock("blocker")
    context.system.defer("request", "successor")
    context.selected = "successor"
    if locked:
        context.system.release("blocker")
        context.system.set_handoff_disposition("blocker", "abandoned")
        context.system.lock("successor")


def new_system(context) -> OpenLease:
    return OpenLease(
        context.root / "state",
        worktree_base=context.root / "worktrees",
        openspec=context.openspec,
    )
