from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any


class StateFormatError(ValueError):
    """Persisted OpenLease state is not a supported strict document."""


@dataclass(frozen=True, slots=True)
class RepositoryRecord:
    identifier: str
    path: str
    common_dir: str | None = None


@dataclass(frozen=True, slots=True)
class AuthorityRecord:
    identifier: str
    repository_id: str
    relative_path: str
    store_id: str | None = None


@dataclass(frozen=True, slots=True)
class OpenLeaseState:
    generation: int = 0
    repositories: tuple[RepositoryRecord, ...] = ()
    authorities: tuple[AuthorityRecord, ...] = ()
    schema_version: int = 1


def structural_key(value: object) -> str:
    """Return a stable key for a closed JSON-compatible value structure."""

    def normalize(item: object) -> object:
        if hasattr(item, "__dataclass_fields__"):
            return normalize(asdict(item))
        if isinstance(item, Enum):
            return normalize(item.value)
        if isinstance(item, Path):
            return item.as_posix()
        if isinstance(item, dict):
            return {str(key): normalize(child) for key, child in item.items()}
        if isinstance(item, (tuple, list)):
            return [normalize(child) for child in item]
        if item is None or isinstance(item, (str, int, float, bool)):
            return item
        raise TypeError(f"unsupported structural-key value: {type(item).__name__}")

    encoded = json.dumps(
        normalize(value), separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def decode_state(source: bytes) -> OpenLeaseState:
    try:
        value = json.loads(source.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise StateFormatError("invalid OpenLease state JSON") from error
    if not isinstance(value, dict):
        raise StateFormatError("OpenLease state must be a JSON object")
    _require_keys(
        value, {"schema_version", "generation", "repositories", "authorities"}
    )
    if value.get("schema_version") != 1:
        raise StateFormatError("unsupported OpenLease state schema")
    generation = value.get("generation")
    if (
        not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation < 0
    ):
        raise StateFormatError("invalid OpenLease state generation")
    repositories = tuple(
        _repository(item)
        for item in _object_list(value.get("repositories", []), "repositories")
    )
    authorities = tuple(
        _authority(item)
        for item in _object_list(value.get("authorities", []), "authorities")
    )
    return validate_state(
        OpenLeaseState(
            generation=generation,
            repositories=repositories,
            authorities=authorities,
        )
    )


def encode_state(state: OpenLeaseState) -> bytes:
    state = validate_state(state)
    document = {
        "schema_version": state.schema_version,
        "generation": state.generation,
        "repositories": [asdict(item) for item in state.repositories],
        "authorities": [asdict(item) for item in state.authorities],
    }
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def validate_state(state: OpenLeaseState) -> OpenLeaseState:
    repository_ids = [item.identifier for item in state.repositories]
    authority_ids = [item.identifier for item in state.authorities]
    if len(repository_ids) != len(set(repository_ids)):
        raise StateFormatError("duplicate repository identifier")
    if len(authority_ids) != len(set(authority_ids)):
        raise StateFormatError("duplicate authority identifier")
    known_repositories = set(repository_ids)
    for authority in state.authorities:
        if authority.repository_id not in known_repositories:
            raise StateFormatError(
                f"authority {authority.identifier} has a missing repository"
            )
    return state


def _repository(value: dict[str, Any]) -> RepositoryRecord:
    _require_keys(value, {"identifier", "path", "common_dir"})
    return RepositoryRecord(
        _string(value.get("identifier"), "repository identifier"),
        _string(value.get("path"), "repository path"),
        _optional_string(value.get("common_dir"), "repository common directory"),
    )


def _authority(value: dict[str, Any]) -> AuthorityRecord:
    _require_keys(value, {"identifier", "repository_id", "relative_path", "store_id"})
    return AuthorityRecord(
        _string(value.get("identifier"), "authority identifier"),
        _string(value.get("repository_id"), "authority repository"),
        _string(value.get("relative_path"), "authority relative path"),
        _optional_string(value.get("store_id"), "authority store id"),
    )


def _object_list(value: object, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise StateFormatError(f"invalid {name}")
    return value


def _require_keys(value: dict[str, Any], allowed: set[str]) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise StateFormatError(f"unknown state field: {sorted(unknown)[0]}")


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise StateFormatError(f"invalid {name}")
    return value


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _string(value, name)
