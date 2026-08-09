from __future__ import annotations

import io
import json
import math
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import StrEnum
from typing import Protocol, TypeAlias

import tomlkit
from ruamel.yaml import YAML


class CodecError(ValueError):
    """A configuration document violates its declared codec contract."""


class ConfigurationLayout(StrEnum):
    SHARED = "shared"
    DEDICATED = "dedicated"


ManagedScalar: TypeAlias = str | int | float | bool | date | time | datetime
ManagedValue: TypeAlias = (
    ManagedScalar | tuple["ManagedValue", ...] | Mapping[str, "ManagedValue"]
)


@dataclass(slots=True)
class RoundTripDocument:
    codec: str
    value: object
    trailing_newline: bool = True


class ConfigurationCodec(Protocol):
    name: str

    def decode(self, content: bytes) -> RoundTripDocument: ...

    def new_document(self, value: Mapping[str, ManagedValue]) -> RoundTripDocument: ...

    def root_mapping(
        self, document: RoundTripDocument
    ) -> Mapping[str, ManagedValue]: ...

    def replace_root_mapping(
        self,
        document: RoundTripDocument,
        value: Mapping[str, ManagedValue],
    ) -> RoundTripDocument: ...

    def encode(self, document: RoundTripDocument) -> bytes: ...


def validate_managed_value(value: object, *, path: str = "$") -> None:
    if value is None:
        raise CodecError(f"unsupported null managed value at {path}")
    if isinstance(value, float) and not math.isfinite(value):
        raise CodecError(f"non-finite managed value at {path}")
    if isinstance(value, (str, int, float, bool, date, time, datetime)):
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CodecError(f"managed mapping key is not a string at {path}")
            validate_managed_value(child, path=f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            validate_managed_value(child, path=f"{path}[{index}]")
        return
    raise CodecError(f"unsupported managed value at {path}: {type(value).__name__}")


def immutable_managed_value(value: object) -> ManagedValue:
    validate_managed_value(value)
    if isinstance(value, Mapping):
        from types import MappingProxyType

        return MappingProxyType(
            {str(key): immutable_managed_value(child) for key, child in value.items()}
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(immutable_managed_value(child) for child in value)
    return value  # type: ignore[return-value]


def plain_managed_value(value: object) -> object:
    if hasattr(value, "unwrap"):
        value = value.unwrap()
    if isinstance(value, Mapping):
        return {str(key): plain_managed_value(child) for key, child in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [plain_managed_value(child) for child in value]
    return value


def to_plain_managed_value(value: ManagedValue) -> object:
    """Copy a supported managed value into ordinary mutable containers."""
    validate_managed_value(value)
    if isinstance(value, Mapping):
        return {key: to_plain_managed_value(child) for key, child in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_plain_managed_value(child) for child in value]
    return value


class YamlCodec:
    name = "yaml"

    @staticmethod
    def _yaml() -> YAML:
        yaml = YAML(typ="rt")
        yaml.allow_duplicate_keys = False
        yaml.preserve_quotes = True
        yaml.version = (1, 2)
        return yaml

    def decode(self, content: bytes) -> RoundTripDocument:
        try:
            text = content.decode("utf-8")
            documents = list(self._yaml().load_all(text))
        except Exception as error:
            raise CodecError(f"invalid yaml configuration: {error}") from error
        if len(documents) != 1:
            raise CodecError("yaml configuration must contain exactly one document")
        value = documents[0]
        if not isinstance(value, Mapping):
            raise CodecError("yaml configuration requires a root mapping")
        self._reject_yaml_ambiguity(value)
        validate_managed_value(plain_managed_value(value))
        return RoundTripDocument(self.name, value, text.endswith("\n"))

    def _reject_yaml_ambiguity(self, value: object) -> None:
        tag = getattr(value, "tag", None)
        tag_value = str(tag) if tag is not None else ""
        if tag_value.startswith("!"):
            raise CodecError(f"custom yaml tag is not permitted: {tag_value}")
        if isinstance(value, Mapping):
            if getattr(value, "merge", None):
                raise CodecError("yaml merge keys are not permitted")
            for key, child in value.items():
                if not isinstance(key, str):
                    raise CodecError("yaml mapping keys must be strings")
                self._reject_yaml_ambiguity(child)
        elif isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            for child in value:
                self._reject_yaml_ambiguity(child)

    def new_document(self, value: Mapping[str, ManagedValue]) -> RoundTripDocument:
        validate_managed_value(value)
        return self.decode(self._render_plain(value))

    def _render_plain(self, value: Mapping[str, ManagedValue]) -> bytes:
        stream = io.StringIO()
        self._yaml().dump(deepcopy(dict(value)), stream)
        return stream.getvalue().encode("utf-8")

    def root_mapping(self, document: RoundTripDocument) -> Mapping[str, ManagedValue]:
        _require_document(document, self.name)
        value = plain_managed_value(document.value)
        if not isinstance(value, Mapping):
            raise CodecError("yaml configuration requires a root mapping")
        return value  # type: ignore[return-value]

    def replace_root_mapping(
        self, document: RoundTripDocument, value: Mapping[str, ManagedValue]
    ) -> RoundTripDocument:
        validate_managed_value(value)
        _update_mapping(document.value, value)
        return document

    def encode(self, document: RoundTripDocument) -> bytes:
        _require_document(document, self.name)
        self._reject_yaml_ambiguity(document.value)
        validate_managed_value(plain_managed_value(document.value))
        stream = io.StringIO()
        self._yaml().dump(document.value, stream)
        rendered = stream.getvalue()
        if not document.trailing_newline:
            rendered = rendered.rstrip("\n")
        return rendered.encode("utf-8")


class TomlCodec:
    name = "toml"

    def decode(self, content: bytes) -> RoundTripDocument:
        try:
            text = content.decode("utf-8")
            value = tomlkit.parse(text)
        except Exception as error:
            raise CodecError(f"invalid toml configuration: {error}") from error
        validate_managed_value(plain_managed_value(value))
        return RoundTripDocument(self.name, value, text.endswith("\n"))

    def new_document(self, value: Mapping[str, ManagedValue]) -> RoundTripDocument:
        validate_managed_value(value)
        document = tomlkit.document()
        for key, child in value.items():
            document.add(key, tomlkit.item(deepcopy(child)))
        return RoundTripDocument(self.name, document)

    def root_mapping(self, document: RoundTripDocument) -> Mapping[str, ManagedValue]:
        _require_document(document, self.name)
        value = plain_managed_value(document.value)
        if not isinstance(value, Mapping):
            raise CodecError("toml configuration requires a root mapping")
        return value  # type: ignore[return-value]

    def replace_root_mapping(
        self, document: RoundTripDocument, value: Mapping[str, ManagedValue]
    ) -> RoundTripDocument:
        validate_managed_value(value)
        _update_mapping(document.value, value, toml=True)
        return document

    def encode(self, document: RoundTripDocument) -> bytes:
        _require_document(document, self.name)
        validate_managed_value(plain_managed_value(document.value))
        rendered = tomlkit.dumps(document.value)
        if document.trailing_newline and rendered and not rendered.endswith("\n"):
            rendered += "\n"
        if not document.trailing_newline:
            rendered = rendered.rstrip("\n")
        return rendered.encode("utf-8")


class JsonCodec:
    name = "json"

    def decode(self, content: bytes) -> RoundTripDocument:
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise CodecError(f"duplicate json key: {key}")
                result[key] = value
            return result

        def reject_constant(value: str):
            raise CodecError(f"non-finite json number: {value}")

        try:
            text = content.decode("utf-8")
            decoder = json.JSONDecoder(
                object_pairs_hook=pairs, parse_constant=reject_constant
            )
            value, end = decoder.raw_decode(text.lstrip())
            offset = len(text) - len(text.lstrip())
            if text[offset + end :].strip():
                raise CodecError("trailing json content")
        except CodecError:
            raise
        except Exception as error:
            raise CodecError(f"invalid json configuration: {error}") from error
        if not isinstance(value, dict):
            raise CodecError("json configuration requires a root mapping")
        validate_managed_value(value)
        return RoundTripDocument(self.name, value, text.endswith("\n"))

    def new_document(self, value: Mapping[str, ManagedValue]) -> RoundTripDocument:
        validate_managed_value(value)
        return RoundTripDocument(self.name, deepcopy(dict(value)))

    def root_mapping(self, document: RoundTripDocument) -> Mapping[str, ManagedValue]:
        _require_document(document, self.name)
        value = document.value
        if not isinstance(value, Mapping):
            raise CodecError("json configuration requires a root mapping")
        return deepcopy(dict(value))  # type: ignore[return-value]

    def replace_root_mapping(
        self, document: RoundTripDocument, value: Mapping[str, ManagedValue]
    ) -> RoundTripDocument:
        validate_managed_value(value)
        document.value = deepcopy(dict(value))
        return document

    def encode(self, document: RoundTripDocument) -> bytes:
        _require_document(document, self.name)
        validate_managed_value(document.value)
        rendered = json.dumps(
            document.value,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        if document.trailing_newline:
            rendered += "\n"
        return rendered.encode("utf-8")


class CodecRegistry:
    def __init__(self, additional: tuple[ConfigurationCodec, ...] = ()) -> None:
        codecs: dict[str, ConfigurationCodec] = {
            "yaml": YamlCodec(),
            "toml": TomlCodec(),
            "json": JsonCodec(),
        }
        for codec in additional:
            name = getattr(codec, "name", None)
            if not isinstance(name, str) or not name:
                raise CodecError("custom codec requires a non-empty name")
            if name in codecs:
                raise CodecError(f"duplicate configuration codec: {name}")
            codecs[name] = codec
        self._codecs = codecs

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._codecs)

    def require(self, name: str) -> ConfigurationCodec:
        try:
            return self._codecs[name]
        except KeyError as error:
            raise CodecError(
                f"configuration codec is not registered: {name}"
            ) from error


def project_namespace(
    codec: ConfigurationCodec,
    document: RoundTripDocument,
    extension_id: str,
    layout: ConfigurationLayout,
) -> dict[str, ManagedValue]:
    root = codec.root_mapping(document)
    if layout is ConfigurationLayout.DEDICATED:
        selected: object = root
    else:
        selected = root.get(extension_id, {})
    if not isinstance(selected, Mapping):
        raise CodecError(
            f"{layout.value} configuration namespace is not a mapping: {extension_id}"
        )
    value = plain_managed_value(selected)
    validate_managed_value(value)
    return deepcopy(dict(value))  # type: ignore[arg-type]


def replace_namespace(
    codec: ConfigurationCodec,
    document: RoundTripDocument,
    extension_id: str,
    layout: ConfigurationLayout,
    value: Mapping[str, ManagedValue],
) -> RoundTripDocument:
    validate_managed_value(value)
    if layout is ConfigurationLayout.DEDICATED:
        return codec.replace_root_mapping(document, value)
    raw_root = document.value
    if not isinstance(raw_root, Mapping):
        raise CodecError("configuration requires a root mapping")
    selected = raw_root.get(extension_id)
    if selected is None:
        raw_root[extension_id] = _container_value(value, codec.name)  # type: ignore[index]
    elif not isinstance(selected, Mapping):
        raise CodecError(
            f"shared configuration namespace is not a mapping: {extension_id}"
        )
    else:
        _update_mapping(selected, value, toml=codec.name == "toml")
    return document


def _container_value(value: object, codec_name: str) -> object:
    return tomlkit.item(deepcopy(value)) if codec_name == "toml" else deepcopy(value)


def _update_mapping(
    target: object, value: Mapping[str, ManagedValue], *, toml=False
) -> None:
    if not hasattr(target, "keys"):
        raise CodecError("configuration requires a mutable root mapping")
    for key in tuple(target.keys()):
        if key not in value:
            del target[key]
    for key, child in value.items():
        existing = target.get(key)
        if isinstance(existing, Mapping) and isinstance(child, Mapping):
            _update_mapping(existing, child, toml=toml)
        else:
            target[key] = _container_value(child, "toml" if toml else "")


def _require_document(document: RoundTripDocument, codec: str) -> None:
    if document.codec != codec:
        raise CodecError(
            f"codec mismatch: document is {document.codec}, requested {codec}"
        )
