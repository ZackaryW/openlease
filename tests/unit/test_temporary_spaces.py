from __future__ import annotations

from pathlib import Path

import pytest

from openlease.core.state_codec import (
    RepositoryRecord,
    SpaceRecord,
    TemporarySpaceDescriptor,
)
from openlease.core.temporary_spaces import (
    fingerprint_session_token,
    resolve_registered_worktree,
    temporary_space_matches,
)
from openlease.utils.git_adapter import GitCheckout


def test_fingerprints_a_nonblank_session_token_without_returning_it() -> None:
    first = fingerprint_session_token("opaque-session-token")
    second = fingerprint_session_token("opaque-session-token")

    assert first == second
    assert first != "opaque-session-token"
    with pytest.raises(ValueError, match="non-empty"):
        fingerprint_session_token("   ")


def test_resolves_a_linked_worktree_by_registered_common_directory() -> None:
    checkout = GitCheckout(
        Path("/work/repo-linked"),
        Path("/work/repo/.git"),
        "head",
        "branch",
        None,
        False,
    )
    repository = RepositoryRecord("repo", "/work/repo", "/work/repo/.git")

    assert resolve_registered_worktree(checkout, (repository,)) == repository
    assert checkout.root == Path("/work/repo-linked")


def test_matches_temporary_ownership_by_worktree_and_optional_session() -> None:
    space = SpaceRecord(
        "repo-temporary-1",
        temporary=TemporarySpaceDescriptor("repo", "/work/repo", "session-a"),
    )

    assert temporary_space_matches(
        space,
        repository_id="repo",
        worktree_path=Path("/work/repo"),
        session_fingerprint="session-a",
    )
    assert temporary_space_matches(
        space,
        repository_id="repo",
        worktree_path=Path("/work/repo"),
    )
    assert not temporary_space_matches(
        space,
        repository_id="repo",
        worktree_path=Path("/work/repo"),
        session_fingerprint="session-b",
    )
