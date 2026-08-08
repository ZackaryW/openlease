from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from openlease.utils.processes import ProcessRunner, SubprocessRunner, require_success


@dataclass(frozen=True, slots=True)
class GitCheckout:
    root: Path
    common_dir: Path
    head: str
    branch: str | None
    upstream: str | None
    dirty: bool


@dataclass(frozen=True, slots=True)
class WorktreeRequest:
    destination: Path
    branch: str
    start_commit: str
    create_branch: bool = True


class IntegrationStrategy(StrEnum):
    MERGE = "merge"
    REBASE = "rebase"


@dataclass(frozen=True, slots=True)
class ChangedPath:
    path: str


@dataclass(frozen=True, slots=True)
class MergeLeg:
    checkout: Path
    source_ref: str
    destination_ref: str
    strategy: IntegrationStrategy


@dataclass(frozen=True, slots=True)
class MergePreview:
    source_commit: str
    destination_commit: str
    merge_base: str
    ahead: int
    behind: int
    likely_conflicts: bool


@dataclass(frozen=True, slots=True)
class IntegrationResult:
    strategy: IntegrationStrategy
    head: str


class GitAdapter:
    def __init__(self, runner: ProcessRunner | None = None) -> None:
        self.runner = runner or SubprocessRunner()

    def _git(self, checkout: Path, *arguments: str):
        return self.runner.run(("git", "-C", str(checkout), *arguments))

    def inspect(self, path: Path) -> GitCheckout:
        target = path if path.is_dir() else path.parent
        root = Path(
            require_success(
                self._git(target, "rev-parse", "--show-toplevel"),
                "Git checkout inspection",
            ).stdout.strip()
        ).resolve()
        head = require_success(
            self._git(root, "rev-parse", "--verify", "HEAD"),
            "Git HEAD inspection",
        ).stdout.strip()
        common_dir = Path(
            require_success(
                self._git(
                    root,
                    "rev-parse",
                    "--path-format=absolute",
                    "--git-common-dir",
                ),
                "Git common-directory inspection",
            ).stdout.strip()
        ).resolve()
        branch_result = self._git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
        upstream_result = self._git(
            root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
        )
        upstream = (
            upstream_result.stdout.strip() if upstream_result.returncode == 0 else None
        )
        status = require_success(
            self._git(root, "status", "--porcelain=v1", "--untracked-files=normal"),
            "Git dirty-state inspection",
        )
        return GitCheckout(
            root, common_dir, head, branch, upstream, bool(status.stdout)
        )

    def create_worktree(
        self, source: GitCheckout, request: WorktreeRequest
    ) -> GitCheckout:
        if request.destination.exists() or request.destination.is_symlink():
            raise FileExistsError(request.destination)
        arguments = ["worktree", "add"]
        if request.create_branch:
            branch_exists = self._git(
                source.root,
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{request.branch}",
            )
            if branch_exists.returncode == 0:
                raise ValueError(f"branch already exists: {request.branch}")
            arguments.extend(("-b", request.branch))
            target = request.start_commit
        else:
            branch_ref = f"refs/heads/{request.branch}"
            branch_head = require_success(
                self._git(source.root, "rev-parse", "--verify", branch_ref),
                "Git existing-branch inspection",
            ).stdout.strip()
            expected_head = require_success(
                self._git(source.root, "rev-parse", "--verify", request.start_commit),
                "Git starting-commit inspection",
            ).stdout.strip()
            if branch_head != expected_head:
                raise ValueError(
                    f"branch {request.branch} moved from its recorded starting commit"
                )
            target = request.branch
        arguments.extend((str(request.destination), target))
        require_success(
            self._git(source.root, *arguments),
            "Git worktree creation",
        )
        return self.inspect(request.destination)

    def remove_worktree(self, source: GitCheckout, path: Path) -> None:
        require_success(
            self._git(source.root, "worktree", "remove", str(path)),
            "Git worktree removal",
        )

    def changed_paths(
        self, checkout: GitCheckout, base: str, head: str
    ) -> tuple[ChangedPath, ...]:
        result = require_success(
            self._git(
                checkout.root,
                "diff",
                "--name-only",
                "--diff-filter=ACDMRTUXB",
                base,
                head,
                "--",
            ),
            "Git changed-path inspection",
        )
        return tuple(ChangedPath(line) for line in result.stdout.splitlines() if line)

    def preview_integration(self, leg: MergeLeg) -> MergePreview:
        source = require_success(
            self._git(leg.checkout, "rev-parse", "--verify", leg.source_ref),
            "Git source-ref inspection",
        ).stdout.strip()
        destination = require_success(
            self._git(leg.checkout, "rev-parse", "--verify", leg.destination_ref),
            "Git destination-ref inspection",
        ).stdout.strip()
        merge_base = require_success(
            self._git(leg.checkout, "merge-base", destination, source),
            "Git merge-base inspection",
        ).stdout.strip()
        divergence = require_success(
            self._git(
                leg.checkout,
                "rev-list",
                "--left-right",
                "--count",
                f"{destination}...{source}",
            ),
            "Git divergence inspection",
        ).stdout.split()
        if len(divergence) != 2:
            raise ValueError("Git divergence output is invalid")
        merge_tree = self._git(
            leg.checkout,
            "merge-tree",
            "--write-tree",
            destination,
            source,
        )
        if merge_tree.returncode not in (0, 1):
            require_success(merge_tree, "Git merge-tree preview")
        return MergePreview(
            source,
            destination,
            merge_base,
            ahead=int(divergence[1]),
            behind=int(divergence[0]),
            likely_conflicts=merge_tree.returncode == 1,
        )

    def apply_integration(self, leg: MergeLeg) -> IntegrationResult:
        checkout = self.inspect(leg.checkout)
        if checkout.dirty:
            raise ValueError(f"Git checkout is dirty: {checkout.root}")
        if leg.strategy is IntegrationStrategy.MERGE:
            require_success(
                self._git(checkout.root, "merge", "--no-edit", leg.source_ref),
                "Git merge",
            )
        else:
            if checkout.branch != leg.source_ref:
                raise ValueError("rebase checkout is not on the source branch")
            require_success(
                self._git(checkout.root, "rebase", leg.destination_ref),
                "Git rebase",
            )
        return IntegrationResult(leg.strategy, self.inspect(checkout.root).head)
