from __future__ import annotations

from datetime import date, datetime, time

import pytest

from openlease.configuration_codec import (
    CodecError,
    CodecRegistry,
    ConfigurationLayout,
    JsonCodec,
    TomlCodec,
    YamlCodec,
    project_namespace,
    replace_namespace,
)


@pytest.fixture(params=[YamlCodec, TomlCodec, JsonCodec])
def codec(request):
    return request.param()


def test_builtin_codecs_round_trip_the_common_managed_graph(codec) -> None:
    value = {
        "enabled": True,
        "count": 3,
        "ratio": 1.25,
        "label": "héllo",
        "nested": {"items": ["a", "b"]},
    }
    document = codec.new_document({"extension-a": value})

    decoded = codec.decode(codec.encode(document))

    assert dict(codec.root_mapping(decoded))["extension-a"] == value


@pytest.mark.parametrize(
    ("codec", "content"),
    [
        (YamlCodec(), b"extension-a:\n  key: one\n  key: two\n"),
        (YamlCodec(), b"extension-a: !unsafe payload\n"),
        (YamlCodec(), b"extension-a:\n  <<: {key: value}\n"),
        (YamlCodec(), b"---\na: {}\n---\nb: {}\n"),
        (JsonCodec(), b'{"extension-a": {}, "extension-a": {}}'),
        (JsonCodec(), b'{"extension-a": NaN}'),
        (JsonCodec(), b"{} {}"),
        (TomlCodec(), b"[extension-a\nkey = 1"),
    ],
)
def test_codecs_reject_ambiguous_or_unsafe_input(codec, content: bytes) -> None:
    with pytest.raises(CodecError):
        codec.decode(content)


@pytest.mark.parametrize("content", [b"[]", b"null", b"1"])
def test_json_requires_an_object_root(content: bytes) -> None:
    with pytest.raises(CodecError, match="root mapping"):
        JsonCodec().decode(content)


def test_shared_layout_uses_an_exact_dotted_identity() -> None:
    codec = TomlCodec()
    document = codec.decode(
        b'[zpp.behave]\nrunner = "wrong"\n\n["zpp.behave"]\nrunner = "right"\n'
    )

    selected = project_namespace(
        codec, document, "zpp.behave", ConfigurationLayout.SHARED
    )
    changed = replace_namespace(
        codec,
        document,
        "zpp.behave",
        ConfigurationLayout.SHARED,
        {"runner": "updated"},
    )
    rendered = codec.encode(changed).decode()

    assert selected == {"runner": "right"}
    assert '["zpp.behave"]' in rendered
    assert "wrong" in rendered


def test_dedicated_layout_owns_the_complete_root() -> None:
    codec = YamlCodec()
    document = codec.decode(b"version: 1\ncommands:\n  bdd: {}\n")

    selected = project_namespace(
        codec, document, "zpp.behave", ConfigurationLayout.DEDICATED
    )

    assert selected == {"version": 1, "commands": {"bdd": {}}}


def test_round_trip_codecs_preserve_unrelated_comments() -> None:
    yaml_codec = YamlCodec()
    yaml_document = yaml_codec.decode(
        b"# heading\nextension-a:\n  key: old # keep\nextension-b:\n  untouched: true\n"
    )
    yaml_changed = replace_namespace(
        yaml_codec,
        yaml_document,
        "extension-a",
        ConfigurationLayout.SHARED,
        {"key": "new"},
    )
    assert "# heading" in yaml_codec.encode(yaml_changed).decode()
    assert "# keep" in yaml_codec.encode(yaml_changed).decode()

    toml_codec = TomlCodec()
    toml_document = toml_codec.decode(
        b'# heading\n[extension-a]\nkey = "old" # keep\n'
        b"[extension-b]\nuntouched = true\n"
    )
    toml_changed = replace_namespace(
        toml_codec,
        toml_document,
        "extension-a",
        ConfigurationLayout.SHARED,
        {"key": "new"},
    )
    assert "# heading" in toml_codec.encode(toml_changed).decode()
    assert "# keep" in toml_codec.encode(toml_changed).decode()


def test_registry_is_explicit_and_rejects_duplicate_or_unknown_codecs() -> None:
    class CustomJson(JsonCodec):
        name = "custom"

    registry = CodecRegistry((CustomJson(),))

    assert registry.require("custom").name == "custom"
    with pytest.raises(CodecError, match="not registered"):
        registry.require("missing")
    with pytest.raises(CodecError, match="duplicate"):
        CodecRegistry((JsonCodec(),))


def test_managed_temporal_values_are_supported_by_toml() -> None:
    codec = TomlCodec()
    values = {
        "date": date(2026, 8, 9),
        "time": time(12, 30),
        "datetime": datetime(2026, 8, 9, 12, 30),
    }

    decoded = codec.decode(codec.encode(codec.new_document(values)))

    assert dict(codec.root_mapping(decoded)) == values
