from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from openlease.core.state_codec import (
    ConfigurationSourceRecord,
    PreparedArtifactRecord,
    ReconciliationRecord,
    RepositoryRecord,
    SpaceMemberRecord,
    SpacePackAttachmentRecord,
    SpaceRecord,
    TemporarySpaceDescriptor,
)
from openlease.core.temporary_spaces import (
    fingerprint_session_token,
    is_disposable_temporary_space,
    next_temporary_space_identifier,
    promote_temporary_space,
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


@pytest.mark.parametrize(
    "repositories",
    [
        (),
        (
            RepositoryRecord("repo-a", "/work/a", "/work/repo/.git"),
            RepositoryRecord("repo-b", "/work/b", "/work/repo/.git"),
        ),
    ],
)
def test_rejects_absent_or_ambiguous_registered_worktree_matches(
    repositories: tuple[RepositoryRecord, ...],
) -> None:
    checkout = GitCheckout(
        Path("/work/repo-linked"),
        Path("/work/repo/.git"),
        "head",
        "branch",
        None,
        False,
    )

    with pytest.raises(ValueError, match="exactly one"):
        resolve_registered_worktree(checkout, repositories)


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


def test_classifies_an_empty_temporary_draft_as_disposable() -> None:
    space = SpaceRecord(
        "repo-temporary-1",
        temporary=TemporarySpaceDescriptor("repo", "/work/repo", "session-a"),
    )

    assert is_disposable_temporary_space(space, (), (), ())


def test_never_classifies_a_durable_or_active_space_as_disposable() -> None:
    temporary = TemporarySpaceDescriptor("repo", "/work/repo", "session-a")

    assert not is_disposable_temporary_space(SpaceRecord("durable"), (), (), ())
    assert not is_disposable_temporary_space(
        SpaceRecord("active", status="locked", temporary=temporary), (), (), ()
    )


@pytest.mark.parametrize(
    "retained",
    [
        {"held_authority_ids": ("authority",)},
        {
            "members": (
                SpaceMemberRecord(
                    "repo", "/work/repo", "/work/generated", "head", generated=True
                ),
            )
        },
        {
            "projection_name": "owned-projection",
            "projection_fingerprint": "fingerprint",
        },
        {"preparation_artifacts": (PreparedArtifactRecord("repo", "/work", "b", "h"),)},
        {"blockers": ("owner",)},
        {"handoff_disposition": "integrated"},
    ],
)
def test_rejects_temporary_spaces_with_internal_retention_evidence(
    retained: dict[str, object],
) -> None:
    empty = SpaceRecord(
        "repo-temporary-1",
        temporary=TemporarySpaceDescriptor("repo", "/work/repo", "session-a"),
    )

    assert not is_disposable_temporary_space(replace(empty, **retained), (), (), ())


@pytest.mark.parametrize(
    ("reconciliations", "configuration_sources", "pack_attachments"),
    [
        ((ReconciliationRecord("repo-temporary-1", "repo"),), (), ()),
        (
            (),
            (
                ConfigurationSourceRecord(
                    "source",
                    "extension",
                    "space",
                    "repo-temporary-1",
                    "external",
                    "/work/config.yaml",
                    codec="yaml",
                    layout="dedicated",
                ),
            ),
            (),
        ),
        (
            (),
            (),
            (SpacePackAttachmentRecord("repo-temporary-1", "extension", "pack"),),
        ),
    ],
)
def test_rejects_temporary_spaces_with_external_retention_references(
    reconciliations: tuple[ReconciliationRecord, ...],
    configuration_sources: tuple[ConfigurationSourceRecord, ...],
    pack_attachments: tuple[SpacePackAttachmentRecord, ...],
) -> None:
    space = SpaceRecord(
        "repo-temporary-1",
        temporary=TemporarySpaceDescriptor("repo", "/work/repo", "session-a"),
    )

    assert not is_disposable_temporary_space(
        space,
        reconciliations,
        configuration_sources,
        pack_attachments,
    )


def test_ignores_external_references_owned_by_other_spaces() -> None:
    space = SpaceRecord(
        "repo-temporary-1",
        temporary=TemporarySpaceDescriptor("repo", "/work/repo", "session-a"),
    )
    reconciliation = ReconciliationRecord("other", "repo")
    source = ConfigurationSourceRecord(
        "source",
        "extension",
        "space",
        "other",
        "external",
        "/work/config.yaml",
        codec="yaml",
        layout="dedicated",
    )
    attachment = SpacePackAttachmentRecord("other", "extension", "pack")

    assert is_disposable_temporary_space(
        space, (reconciliation,), (source,), (attachment,)
    )


def test_allocates_the_first_collision_free_temporary_identifier() -> None:
    assert (
        next_temporary_space_identifier(
            "repo", {"repo-temporary-1", "other", "repo-temporary-2"}
        )
        == "repo-temporary-3"
    )


def test_promotes_by_clearing_only_temporary_ownership_idempotently() -> None:
    temporary = SpaceRecord(
        "repo-temporary-1",
        status="locked",
        associated_repository_ids=("repo",),
        held_authority_ids=("authority",),
        temporary=TemporarySpaceDescriptor("repo", "/work/repo", "session-a"),
    )

    promoted = promote_temporary_space(temporary)

    assert promoted == replace(temporary, temporary=None)
    assert promote_temporary_space(promoted) is promoted
