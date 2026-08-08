import pytest

from openlease.core.state_codec import (
    AuthorityRecord,
    ConfigurationPackRecord,
    ConfigurationSourceRecord,
    ExtensionRootPolicyRecord,
    OpenLeaseState,
    RepositoryRecord,
    SpacePackAttachmentRecord,
    SpaceRecord,
    StateFormatError,
    decode_state,
    encode_state,
    structural_key,
)


def test_rejects_an_unsupported_state_version() -> None:
    with pytest.raises(StateFormatError, match="unsupported"):
        decode_state(b'{"schema_version":3,"generation":0}')


def test_decodes_version_one_as_empty_version_two_configuration() -> None:
    state = decode_state(b'{"schema_version":1,"generation":4}')

    assert state.schema_version == 2
    assert state.generation == 4
    assert state.configuration_generation == 0
    assert state.extension_roots == ()
    assert state.configuration_packs == ()
    assert state.configuration_sources == ()
    assert state.space_pack_attachments == ()


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


def test_round_trips_normalized_version_two_configuration_records() -> None:
    state = OpenLeaseState(
        configuration_generation=7,
        repositories=(RepositoryRecord("repo-1", "C:/work/repo1"),),
        authorities=(AuthorityRecord("child-a", "repo-1", "A/openspec"),),
        spaces=(SpaceRecord("work-a", associated_repository_ids=("repo-1",)),),
        extension_roots=(
            ExtensionRootPolicyRecord("zpp", product_root="C:/Users/me/.zpp"),
        ),
        configuration_packs=(ConfigurationPackRecord("default", "zpp"),),
        configuration_sources=(
            ConfigurationSourceRecord(
                "machine",
                "zpp",
                "machine",
                None,
                "external",
                "C:/Users/me/.zpp/traits.md",
                order=1,
                revision=2,
            ),
            ConfigurationSourceRecord(
                "child",
                "zpp",
                "authority",
                "child-a",
                "repository",
                ".zpp/traits.md",
                repository_id="repo-1",
            ),
        ),
        space_pack_attachments=(
            SpacePackAttachmentRecord("work-a", "zpp", "default", 3),
        ),
    )

    assert decode_state(encode_state(state)) == state


def test_rejects_a_relative_external_configuration_source() -> None:
    state = OpenLeaseState(
        configuration_sources=(
            ConfigurationSourceRecord(
                "machine",
                "zpp",
                "machine",
                None,
                "external",
                "relative/traits.md",
            ),
        )
    )

    with pytest.raises(StateFormatError, match=r"external.*absolute"):
        encode_state(state)


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
