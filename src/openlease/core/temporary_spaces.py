from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from openlease.core.state_codec import RepositoryRecord, SpaceRecord
from openlease.utils.git_adapter import GitCheckout


def fingerprint_session_token(token: str) -> str:
    if not token.strip():
        raise ValueError("session token must be non-empty")
    return sha256(token.encode("utf-8")).hexdigest()


def resolve_registered_worktree(
    checkout: GitCheckout,
    repositories: tuple[RepositoryRecord, ...],
) -> RepositoryRecord:
    common_dir = checkout.common_dir.resolve()
    matches = tuple(
        repository
        for repository in repositories
        if repository.common_dir is not None
        and Path(repository.common_dir).resolve() == common_dir
    )
    if len(matches) != 1:
        raise ValueError("worktree must match exactly one registered repository")
    return matches[0]


def temporary_space_matches(
    space: SpaceRecord,
    *,
    repository_id: str,
    worktree_path: Path,
    session_fingerprint: str | None = None,
) -> bool:
    temporary = space.temporary
    return bool(
        temporary is not None
        and temporary.repository_id == repository_id
        and Path(temporary.worktree_path).resolve() == worktree_path.resolve()
        and (
            session_fingerprint is None
            or temporary.session_fingerprint == session_fingerprint
        )
    )
