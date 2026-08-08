from pathlib import Path

from openlease.core.preparation import (
    ArtifactInspection,
    PreparationMember,
    PreparedArtifact,
    plan_preparation,
    plan_rollback,
)


def test_plans_worktrees_only_for_affected_repositories(tmp_path: Path) -> None:
    members = (
        PreparationMember("repo-1", tmp_path / "repo1", "a" * 40, affected=True),
        PreparationMember("repo-2", tmp_path / "repo2", "b" * 40, affected=False),
        PreparationMember("repo-3", tmp_path / "repo3", "c" * 40, affected=True),
    )

    plan = plan_preparation(members, "successor", tmp_path / "worktrees")

    assert [item.repository_id for item in plan.generated] == ["repo-1", "repo-3"]
    assert [item.repository_id for item in plan.pinned] == ["repo-2"]
    assert all(item.branch == "successor" for item in plan.generated)


def test_plans_the_first_worktree_beside_its_source_by_default(
    tmp_path: Path,
) -> None:
    source = tmp_path / "projects" / "repo1"
    member = PreparationMember("repo-1", source, "a" * 40, affected=True)

    plan = plan_preparation((member,), "successor", None)

    assert plan.generated[0].destination == source.parent / "repo1-olease-1"


def test_skips_occupied_destinations_with_the_lowest_positive_suffix(
    tmp_path: Path,
) -> None:
    source = tmp_path / "projects" / "repo1"
    member = PreparationMember("repo-1", source, "a" * 40, affected=True)
    occupied = frozenset(
        {
            source.parent / "repo1-olease-1",
            source.parent / "repo1-olease-3",
        }
    )

    plan = plan_preparation((member,), "successor", None, occupied)

    assert plan.generated[0].destination == source.parent / "repo1-olease-2"


def test_places_each_repository_beside_its_own_source(tmp_path: Path) -> None:
    first = tmp_path / "team-a" / "repo1"
    second = tmp_path / "team-b" / "repo2"
    members = (
        PreparationMember("repo-1", first, "a" * 40, affected=True),
        PreparationMember("repo-2", second, "b" * 40, affected=True),
    )

    plan = plan_preparation(members, "successor", None)

    assert [item.destination for item in plan.generated] == [
        first.parent / "repo1-olease-1",
        second.parent / "repo2-olease-1",
    ]


def test_uses_the_explicit_base_without_losing_repository_names(
    tmp_path: Path,
) -> None:
    source = tmp_path / "projects" / "repo1"
    base = tmp_path / "managed"
    member = PreparationMember("repo-1", source, "a" * 40, affected=True)

    plan = plan_preparation((member,), "successor", base)

    assert plan.generated[0].destination == base / "repo1-olease-1"


def test_rolls_back_only_proven_unchanged_clean_artifacts(tmp_path: Path) -> None:
    clean = PreparedArtifact("repo-1", tmp_path / "one", "branch", "a" * 40)
    dirty = PreparedArtifact("repo-2", tmp_path / "two", "branch", "b" * 40)

    plan = plan_rollback(
        (clean, dirty),
        {
            "repo-1": ArtifactInspection(clean.path, "a" * 40, dirty=False),
            "repo-2": ArtifactInspection(dirty.path, "b" * 40, dirty=True),
        },
    )

    assert plan.removable == (clean,)
    assert plan.debt == (dirty,)
