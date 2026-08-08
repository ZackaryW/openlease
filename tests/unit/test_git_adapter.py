import subprocess
from pathlib import Path

import pytest

from openlease.utils.git_adapter import (
    GitAdapter,
    IntegrationStrategy,
    MergeLeg,
    WorktreeRequest,
)


def _git(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(repo), *arguments),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _repository(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "--quiet")
    _git(path, "config", "user.email", "tests@openlease.invalid")
    _git(path, "config", "user.name", "OpenLease Tests")
    _git(path, "commit", "--allow-empty", "--quiet", "-m", "base")
    return path


def test_inspects_checkout_identity_head_and_dirty_state(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "repository")
    adapter = GitAdapter()

    clean = adapter.inspect(repository)
    (repository / "changed.txt").write_text("changed", encoding="utf-8")
    dirty = adapter.inspect(repository)

    assert clean.root == repository.resolve()
    assert clean.head == _git(repository, "rev-parse", "HEAD")
    assert clean.common_dir.is_absolute()
    assert clean.dirty is False
    assert dirty.dirty is True


def test_creates_a_new_branch_worktree_from_the_recorded_commit(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "repository")
    adapter = GitAdapter()
    source = adapter.inspect(repository)
    destination = tmp_path / "worktrees" / "successor"

    created = adapter.create_worktree(
        source,
        WorktreeRequest(destination, "successor", source.head),
    )

    assert created.root == destination.resolve()
    assert created.branch == "successor"
    assert created.head == source.head
    assert created.common_dir == source.common_dir
    with pytest.raises(FileExistsError):
        adapter.create_worktree(
            source,
            WorktreeRequest(destination, "other", source.head),
        )


def test_uses_an_existing_local_branch_only_at_its_recorded_commit(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path / "repository")
    adapter = GitAdapter()
    source = adapter.inspect(repository)
    _git(repository, "branch", "existing", source.head)

    created = adapter.create_worktree(
        source,
        WorktreeRequest(
            tmp_path / "existing-worktree",
            "existing",
            source.head,
            create_branch=False,
        ),
    )

    assert created.branch == "existing"
    assert created.head == source.head


def test_creates_a_local_branch_from_an_explicit_remote_ref(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "repository")
    adapter = GitAdapter()
    source = adapter.inspect(repository)
    _git(repository, "update-ref", "refs/remotes/origin/topic", source.head)

    created = adapter.create_worktree(
        source,
        WorktreeRequest(
            tmp_path / "remote-worktree",
            "topic-local",
            "refs/remotes/origin/topic",
        ),
    )

    assert created.branch == "topic-local"
    assert created.head == source.head


def test_reports_changed_paths_and_previews_integration_without_mutation(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path / "repository")
    adapter = GitAdapter()
    source = adapter.inspect(repository)
    feature_path = tmp_path / "feature"
    feature = adapter.create_worktree(
        source, WorktreeRequest(feature_path, "feature", source.head)
    )
    (feature_path / "spec.txt").write_text("feature", encoding="utf-8")
    _git(feature_path, "add", "spec.txt")
    _git(feature_path, "commit", "--quiet", "-m", "feature")
    feature = adapter.inspect(feature_path)

    changed = adapter.changed_paths(feature, source.head, feature.head)
    preview = adapter.preview_integration(
        MergeLeg(
            repository, "feature", source.branch or "master", IntegrationStrategy.MERGE
        )
    )

    assert [item.path for item in changed] == ["spec.txt"]
    assert preview.source_commit == feature.head
    assert preview.destination_commit == source.head
    assert preview.ahead == 1
    assert preview.behind == 0
    assert preview.likely_conflicts is False
    assert adapter.inspect(repository).head == source.head


def test_reports_committed_staged_unstaged_and_untracked_paths(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "repository")
    adapter = GitAdapter()
    baseline = adapter.inspect(repository)
    (repository / "committed.txt").write_text("committed", encoding="utf-8")
    _git(repository, "add", "committed.txt")
    _git(repository, "commit", "--quiet", "-m", "committed")
    (repository / "staged.txt").write_text("staged", encoding="utf-8")
    _git(repository, "add", "staged.txt")
    (repository / "committed.txt").write_text("unstaged", encoding="utf-8")
    (repository / "untracked.txt").write_text("untracked", encoding="utf-8")

    changed = adapter.worktree_changed_paths(adapter.inspect(repository), baseline.head)

    assert [item.path for item in changed] == [
        "committed.txt",
        "staged.txt",
        "untracked.txt",
    ]


def test_applies_an_explicit_merge_leg(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "repository")
    adapter = GitAdapter()
    source = adapter.inspect(repository)
    feature_path = tmp_path / "feature"
    adapter.create_worktree(
        source, WorktreeRequest(feature_path, "feature", source.head)
    )
    (feature_path / "spec.txt").write_text("feature", encoding="utf-8")
    _git(feature_path, "add", "spec.txt")
    _git(feature_path, "commit", "--quiet", "-m", "feature")
    feature_head = _git(feature_path, "rev-parse", "HEAD")

    result = adapter.apply_integration(
        MergeLeg(
            repository,
            "feature",
            source.branch or "master",
            IntegrationStrategy.MERGE,
        )
    )

    assert result.head == feature_head
    assert adapter.inspect(repository).head == feature_head


def test_applies_an_explicit_rebase_leg(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "repository")
    adapter = GitAdapter()
    source = adapter.inspect(repository)
    feature_path = tmp_path / "feature"
    adapter.create_worktree(
        source, WorktreeRequest(feature_path, "feature", source.head)
    )
    (feature_path / "feature.txt").write_text("feature", encoding="utf-8")
    _git(feature_path, "add", "feature.txt")
    _git(feature_path, "commit", "--quiet", "-m", "feature")
    (repository / "destination.txt").write_text("destination", encoding="utf-8")
    _git(repository, "add", "destination.txt")
    _git(repository, "commit", "--quiet", "-m", "destination")

    result = adapter.apply_integration(
        MergeLeg(
            repository,
            "feature",
            source.branch or "master",
            IntegrationStrategy.REBASE,
            source_checkout=feature_path,
            expected_destination_commit=_git(
                repository, "rev-parse", source.branch or "master"
            ),
        )
    )

    assert result.head == _git(feature_path, "rev-parse", "feature")
    assert adapter.inspect(repository).head == result.head
    assert _git(
        feature_path, "merge-base", "feature", source.branch or "master"
    ) == _git(repository, "rev-parse", source.branch or "master")


def test_rejects_rebase_when_the_destination_moved_after_planning(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path / "repository")
    adapter = GitAdapter()
    source = adapter.inspect(repository)
    feature_path = tmp_path / "feature"
    adapter.create_worktree(
        source, WorktreeRequest(feature_path, "feature", source.head)
    )
    (repository / "moved.txt").write_text("moved", encoding="utf-8")
    _git(repository, "add", "moved.txt")
    _git(repository, "commit", "--quiet", "-m", "moved")

    with pytest.raises(ValueError, match="destination moved"):
        adapter.apply_integration(
            MergeLeg(
                repository,
                "feature",
                source.branch or "master",
                IntegrationStrategy.REBASE,
                source_checkout=feature_path,
                expected_destination_commit=source.head,
            )
        )
