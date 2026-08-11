from __future__ import annotations

from collections.abc import Collection
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from openlease.core.state_codec import (
    ConfigurationSourceRecord,
    ReconciliationRecord,
    RepositoryRecord,
    SpacePackAttachmentRecord,
    SpaceRecord,
)
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


def is_disposable_temporary_space(
    space: SpaceRecord,
    reconciliations: tuple[ReconciliationRecord, ...],
    configuration_sources: tuple[ConfigurationSourceRecord, ...],
    pack_attachments: tuple[SpacePackAttachmentRecord, ...],
) -> bool:
    return bool(
        space.temporary is not None
        and space.status == "draft"
        and not space.held_authority_ids
        and not any(member.generated for member in space.members)
        and space.projection_name is None
        and space.projection_fingerprint is None
        and not space.preparation_artifacts
        and not space.blockers
        and space.handoff_disposition is None
        and not any(item.space_id == space.identifier for item in reconciliations)
        and not any(
            item.scope_kind == "space" and item.scope_id == space.identifier
            for item in configuration_sources
        )
        and not any(item.space_id == space.identifier for item in pack_attachments)
    )


def next_temporary_space_identifier(
    repository_id: str,
    existing_identifiers: Collection[str],
) -> str:
    index = 1
    while f"{repository_id}-temporary-{index}" in existing_identifiers:
        index += 1
    return f"{repository_id}-temporary-{index}"


def promote_temporary_space(space: SpaceRecord) -> SpaceRecord:
    if space.temporary is None:
        return space
    return replace(space, temporary=None)
