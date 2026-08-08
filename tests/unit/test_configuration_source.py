from pathlib import Path

import pytest

from openlease.core.configuration import ConfigurationError, PlannedSource
from openlease.utils.configuration_source import ConfigurationSourceReader


def test_rereads_current_bytes_and_changes_the_observed_generation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "traits.md"
    path.write_bytes(b"first")
    source = PlannedSource(
        identifier="machine",
        extension_id="zpp",
        scope_kind="machine",
        scope_id=None,
        resolved_path=path,
        repository_id=None,
        order=0,
        binding_revision=3,
    )
    reader = ConfigurationSourceReader()

    first = reader.read(source)
    path.write_bytes(b"second")
    second = reader.read(source)

    assert first.content == b"first"
    assert second.content == b"second"
    assert first.content_digest != second.content_digest
    assert first.observed_generation != second.observed_generation


def test_retries_when_a_source_is_replaced_during_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "traits.md"
    path.write_bytes(b"first")
    source = PlannedSource(
        "machine", "zpp", "machine", None, path, None, 0, 1
    )
    original_read = Path.read_bytes
    replaced = False

    def replace_after_read(candidate: Path) -> bytes:
        nonlocal replaced
        content = original_read(candidate)
        if candidate == path and not replaced:
            replaced = True
            candidate.write_bytes(b"second-content")
        return content

    monkeypatch.setattr(Path, "read_bytes", replace_after_read)

    document = ConfigurationSourceReader().read(source)

    assert replaced
    assert document.content == b"second-content"


def test_does_not_fall_back_after_a_previously_read_source_disappears(
    tmp_path: Path,
) -> None:
    path = tmp_path / "traits.md"
    path.write_bytes(b"current")
    source = PlannedSource(
        "machine", "zpp", "machine", None, path, None, 0, 1
    )
    reader = ConfigurationSourceReader()
    reader.read(source)
    path.unlink()

    with pytest.raises(ConfigurationError, match="unavailable"):
        reader.read(source)
