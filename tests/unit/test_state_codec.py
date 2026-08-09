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
    with pytest.raises(StateFormatError, match="reinitialize"):
        decode_state(b'{"schema_version":2,"generation":0}')


def test_rejects_old_state_without_a_compatibility_decoder() -> None:
    with pytest.raises(StateFormatError, match="reinitialize"):
        decode_state(b'{"schema_version":1,"generation":4}')


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


def test_round_trips_current_configuration_binding_records() -> None:
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
                codec="yaml",
                layout="dedicated",
                writable=True,
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
                codec="yaml",
                layout="dedicated",
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
                codec="yaml",
                layout="dedicated",
            ),
        )
    )

    with pytest.raises(StateFormatError, match=r"external.*absolute"):
        encode_state(state)


def test_rejects_an_authority_with_a_missing_repository() -> None:
    with pytest.raises(StateFormatError, match="missing repository"):
        encode_state(
            OpenLeaseState(
                authorities=(AuthorityRecord("authority-a", "missing", "openspec"),)
            )
        )


def test_rejects_unknown_state_fields() -> None:
    with pytest.raises(StateFormatError, match="unknown"):
        decode_state(b'{"schema_version":3,"generation":0,"extra":true}')


def test_structural_keys_are_canonical_for_equivalent_values() -> None:
    assert structural_key({"b": (2, 3), "a": 1}) == structural_key(
        {"a": 1, "b": [2, 3]}
    )
