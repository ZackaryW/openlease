from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from openlease.core.state_codec import (
    OpenLeaseState,
    RepositoryRecord,
    StateFormatError,
)
from openlease.utils import state_repository
from openlease.utils.state_repository import StaleStateError, StateRepository


def test_loads_empty_state_when_index_is_absent(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path)

    assert repository.load() == OpenLeaseState()


def test_atomically_commits_one_generation_and_rejects_a_stale_writer(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path)

    updated = repository.mutate(
        0,
        lambda current: OpenLeaseState(
            generation=current.generation,
            repositories=(RepositoryRecord("repo-1", "C:/repo1"),),
        ),
    )

    assert updated.generation == 1
    assert repository.load() == updated
    with pytest.raises(StaleStateError, match="generation"):
        repository.mutate(0, lambda current: current)


def test_rejects_an_old_index_without_migration_or_rewrite(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path)
    version_one = b'{"schema_version":1,"generation":4}\n'
    repository.index_path.write_bytes(version_one)

    with pytest.raises(StateFormatError, match="reinitialize"):
        repository.mutate(4, lambda current: current)

    assert repository.index_path.read_bytes() == version_one
    assert not (tmp_path / "state.v1.json").exists()


def test_preserves_the_previous_index_when_replacement_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = StateRepository(tmp_path)
    original = repository.mutate(0, lambda current: current)

    def fail_replace(source, destination):
        del source, destination
        raise OSError("injected replacement failure")

    monkeypatch.setattr(state_repository.os, "replace", fail_replace)

    with pytest.raises(OSError, match="injected"):
        repository.mutate(original.generation, lambda current: current)

    assert repository.load() == original


def test_serializes_competing_mutations_and_rejects_the_stale_writer(
    tmp_path: Path,
) -> None:
    repository = StateRepository(tmp_path)
    first_entered = Event()
    release_first = Event()
    second_transform_entered = Event()

    def first_transform(current: OpenLeaseState) -> OpenLeaseState:
        first_entered.set()
        assert release_first.wait(timeout=5)
        return current

    def second_transform(current: OpenLeaseState) -> OpenLeaseState:
        second_transform_entered.set()
        return current

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(repository.mutate, 0, first_transform)
        assert first_entered.wait(timeout=5)
        second = pool.submit(repository.mutate, 0, second_transform)
        assert not second_transform_entered.wait(timeout=0.2)
        release_first.set()
        assert first.result(timeout=5).generation == 1
        with pytest.raises(StaleStateError):
            second.result(timeout=5)

    assert not second_transform_entered.is_set()
