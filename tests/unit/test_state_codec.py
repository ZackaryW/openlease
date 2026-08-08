import pytest

from openlease.core.state_codec import (
    AuthorityRecord,
    OpenLeaseState,
    RepositoryRecord,
    StateFormatError,
    decode_state,
    encode_state,
    structural_key,
)


def test_rejects_an_unsupported_state_version() -> None:
    with pytest.raises(StateFormatError, match="unsupported"):
        decode_state(b'{"schema_version":2,"generation":0}')


def test_round_trips_canonical_registered_state() -> None:
    state = OpenLeaseState(
        generation=3,
        repositories=(RepositoryRecord("repo-1", "C:/work/repo1"),),
        authorities=(AuthorityRecord("authority-a", "repo-1", "A/openspec"),),
    )

    encoded = encode_state(state)

    assert decode_state(encoded) == state
    assert encoded.endswith(b"\n")
    assert b'"authorities"' in encoded


def test_rejects_an_authority_with_a_missing_repository() -> None:
    source = b"""{
      "schema_version": 1,
      "generation": 0,
      "repositories": [],
      "authorities": [{
        "identifier": "authority-a",
        "repository_id": "missing",
        "relative_path": "openspec",
        "store_id": null
      }]
    }"""

    with pytest.raises(StateFormatError, match="missing repository"):
        decode_state(source)


def test_rejects_unknown_state_fields() -> None:
    with pytest.raises(StateFormatError, match="unknown"):
        decode_state(
            b'{"schema_version":1,"generation":0,"repositories":[],"authorities":[],"extra":true}'
        )


def test_structural_keys_are_canonical_for_equivalent_values() -> None:
    assert structural_key({"b": (2, 3), "a": 1}) == structural_key(
        {"a": 1, "b": [2, 3]}
    )
