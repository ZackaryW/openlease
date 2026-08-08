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
