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
class ParentRecord:
    child_id: str
    parent_id: str


@dataclass(frozen=True, slots=True)
class DependencyRecord:
    consumer_id: str
    authority_id: str
    access: str


@dataclass(frozen=True, slots=True)
class SpaceMemberRecord:
    repository_id: str
    source_path: str
    effective_path: str
    starting_commit: str
    branch: str | None = None
    generated: bool = False
    upstream: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedArtifactRecord:
    repository_id: str
    path: str
    branch: str
    created_head: str


@dataclass(frozen=True, slots=True)
class SpaceRecord:
    identifier: str
    status: str = "draft"
    associated_repository_ids: tuple[str, ...] = ()
    affected_repository_ids: tuple[str, ...] = ()
    affected_authority_ids: tuple[str, ...] = ()
    held_authority_ids: tuple[str, ...] = ()
    members: tuple[SpaceMemberRecord, ...] = ()
    blockers: tuple[str, ...] = ()
    source_space_id: str | None = None
    graph_generation: int = 0
    projection_name: str | None = None
    projection_fingerprint: str | None = None
    preparation_artifacts: tuple[PreparedArtifactRecord, ...] = ()
    handoff_disposition: str | None = None


@dataclass(frozen=True, slots=True)
class LeaseRecord:
    authority_id: str
    owner_id: str


@dataclass(frozen=True, slots=True)
class ReconciliationRecord:
    space_id: str
    repository_id: str
    destination_ref: str | None = None
    destination_commit: str | None = None
    strategy: str | None = None
    status: str = "pending"
    result_commit: str | None = None


@dataclass(frozen=True, slots=True)
class OpenLeaseState:
    generation: int = 0
    repositories: tuple[RepositoryRecord, ...] = ()
    authorities: tuple[AuthorityRecord, ...] = ()
    graph_generation: int = 0
    parents: tuple[ParentRecord, ...] = ()
    dependencies: tuple[DependencyRecord, ...] = ()
    spaces: tuple[SpaceRecord, ...] = ()
    leases: tuple[LeaseRecord, ...] = ()
    reconciliations: tuple[ReconciliationRecord, ...] = ()
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
        value,
        {
            "schema_version",
            "generation",
            "repositories",
            "authorities",
            "graph_generation",
            "parents",
            "dependencies",
            "spaces",
            "leases",
            "reconciliations",
        },
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
    graph_generation = value.get("graph_generation", 0)
    if not isinstance(graph_generation, int) or graph_generation < 0:
        raise StateFormatError("invalid graph generation")
    parents = tuple(
        _parent(item) for item in _object_list(value.get("parents", []), "parents")
    )
    dependencies = tuple(
        _dependency(item)
        for item in _object_list(value.get("dependencies", []), "dependencies")
    )
    spaces = tuple(
        _space(item) for item in _object_list(value.get("spaces", []), "spaces")
    )
    leases = tuple(
        _lease(item) for item in _object_list(value.get("leases", []), "leases")
    )
    reconciliations = tuple(
        _reconciliation(item)
        for item in _object_list(value.get("reconciliations", []), "reconciliations")
    )
    return validate_state(
        OpenLeaseState(
            generation=generation,
            repositories=repositories,
            authorities=authorities,
            graph_generation=graph_generation,
            parents=parents,
            dependencies=dependencies,
            spaces=spaces,
            leases=leases,
            reconciliations=reconciliations,
        )
    )


def encode_state(state: OpenLeaseState) -> bytes:
    state = validate_state(state)
    document = {
        "schema_version": state.schema_version,
        "generation": state.generation,
        "repositories": [asdict(item) for item in state.repositories],
        "authorities": [asdict(item) for item in state.authorities],
        "graph_generation": state.graph_generation,
        "parents": [asdict(item) for item in state.parents],
        "dependencies": [asdict(item) for item in state.dependencies],
        "spaces": [asdict(item) for item in state.spaces],
        "leases": [asdict(item) for item in state.leases],
        "reconciliations": [asdict(item) for item in state.reconciliations],
    }
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def validate_state(state: OpenLeaseState) -> OpenLeaseState:
    repository_ids = [item.identifier for item in state.repositories]
    authority_ids = [item.identifier for item in state.authorities]
    space_ids = [item.identifier for item in state.spaces]
    if len(repository_ids) != len(set(repository_ids)):
        raise StateFormatError("duplicate repository identifier")
    if len(authority_ids) != len(set(authority_ids)):
        raise StateFormatError("duplicate authority identifier")
    if len(space_ids) != len(set(space_ids)):
        raise StateFormatError("duplicate space identifier")
    known_repositories = set(repository_ids)
    for authority in state.authorities:
        if authority.repository_id not in known_repositories:
            raise StateFormatError(
                f"authority {authority.identifier} has a missing repository"
            )
    known_authorities = set(authority_ids)
    known_spaces = set(space_ids)
    for parent in state.parents:
        if (
            parent.child_id not in known_authorities
            or parent.parent_id not in known_authorities
        ):
            raise StateFormatError("parent relationship has a missing authority")
    for dependency in state.dependencies:
        if dependency.consumer_id not in known_repositories | known_authorities:
            raise StateFormatError("dependency has a missing consumer")
        if dependency.authority_id not in known_authorities:
            raise StateFormatError("dependency has a missing authority")
    for space in state.spaces:
        if not set(space.associated_repository_ids) <= known_repositories:
            raise StateFormatError(f"space {space.identifier} has a missing repository")
        if not set(space.affected_authority_ids) <= known_authorities:
            raise StateFormatError(f"space {space.identifier} has a missing authority")
    for lease in state.leases:
        if (
            lease.authority_id not in known_authorities
            or lease.owner_id not in known_spaces
        ):
            raise StateFormatError("lease has a missing endpoint")
    if len({item.authority_id for item in state.leases}) != len(state.leases):
        raise StateFormatError("duplicate authority lease")
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


def _parent(value: dict[str, Any]) -> ParentRecord:
    _require_keys(value, {"child_id", "parent_id"})
    return ParentRecord(
        _string(value.get("child_id"), "parent child"),
        _string(value.get("parent_id"), "parent authority"),
    )


def _dependency(value: dict[str, Any]) -> DependencyRecord:
    _require_keys(value, {"consumer_id", "authority_id", "access"})
    return DependencyRecord(
        _string(value.get("consumer_id"), "dependency consumer"),
        _string(value.get("authority_id"), "dependency authority"),
        _string(value.get("access"), "dependency access"),
    )


def _space_member(value: dict[str, Any]) -> SpaceMemberRecord:
    _require_keys(
        value,
        {
            "repository_id",
            "source_path",
            "effective_path",
            "starting_commit",
            "branch",
            "generated",
            "upstream",
        },
    )
    generated = value.get("generated")
    if not isinstance(generated, bool):
        raise StateFormatError("invalid generated member flag")
    return SpaceMemberRecord(
        _string(value.get("repository_id"), "member repository"),
        _string(value.get("source_path"), "member source path"),
        _string(value.get("effective_path"), "member effective path"),
        _string(value.get("starting_commit"), "member starting commit"),
        _optional_string(value.get("branch"), "member branch"),
        generated,
        _optional_string(value.get("upstream"), "member upstream"),
    )


def _prepared_artifact(value: dict[str, Any]) -> PreparedArtifactRecord:
    _require_keys(value, {"repository_id", "path", "branch", "created_head"})
    return PreparedArtifactRecord(
        _string(value.get("repository_id"), "artifact repository"),
        _string(value.get("path"), "artifact path"),
        _string(value.get("branch"), "artifact branch"),
        _string(value.get("created_head"), "artifact head"),
    )


def _space(value: dict[str, Any]) -> SpaceRecord:
    allowed = {
        "identifier",
        "status",
        "associated_repository_ids",
        "affected_repository_ids",
        "affected_authority_ids",
        "held_authority_ids",
        "members",
        "blockers",
        "source_space_id",
        "graph_generation",
        "projection_name",
        "projection_fingerprint",
        "preparation_artifacts",
        "handoff_disposition",
    }
    _require_keys(value, allowed)
    return SpaceRecord(
        identifier=_string(value.get("identifier"), "space identifier"),
        status=_string(value.get("status", "draft"), "space status"),
        associated_repository_ids=_string_tuple(
            value.get("associated_repository_ids", []), "associated repositories"
        ),
        affected_repository_ids=_string_tuple(
            value.get("affected_repository_ids", []), "affected repositories"
        ),
        affected_authority_ids=_string_tuple(
            value.get("affected_authority_ids", []), "affected authorities"
        ),
        held_authority_ids=_string_tuple(
            value.get("held_authority_ids", []), "held authorities"
        ),
        members=tuple(
            _space_member(item)
            for item in _object_list(value.get("members", []), "space members")
        ),
        blockers=_string_tuple(value.get("blockers", []), "space blockers"),
        source_space_id=_optional_string(value.get("source_space_id"), "source space"),
        graph_generation=_nonnegative_int(
            value.get("graph_generation", 0), "space graph generation"
        ),
        projection_name=_optional_string(
            value.get("projection_name"), "projection name"
        ),
        projection_fingerprint=_optional_string(
            value.get("projection_fingerprint"), "projection fingerprint"
        ),
        preparation_artifacts=tuple(
            _prepared_artifact(item)
            for item in _object_list(
                value.get("preparation_artifacts", []), "preparation artifacts"
            )
        ),
        handoff_disposition=_optional_string(
            value.get("handoff_disposition"), "handoff disposition"
        ),
    )


def _lease(value: dict[str, Any]) -> LeaseRecord:
    _require_keys(value, {"authority_id", "owner_id"})
    return LeaseRecord(
        _string(value.get("authority_id"), "lease authority"),
        _string(value.get("owner_id"), "lease owner"),
    )


def _reconciliation(value: dict[str, Any]) -> ReconciliationRecord:
    allowed = {
        "space_id",
        "repository_id",
        "destination_ref",
        "destination_commit",
        "strategy",
        "status",
        "result_commit",
    }
    _require_keys(value, allowed)
    return ReconciliationRecord(
        _string(value.get("space_id"), "reconciliation space"),
        _string(value.get("repository_id"), "reconciliation repository"),
        _optional_string(value.get("destination_ref"), "reconciliation destination"),
        _optional_string(
            value.get("destination_commit"), "reconciliation destination commit"
        ),
        _optional_string(value.get("strategy"), "reconciliation strategy"),
        _string(value.get("status", "pending"), "reconciliation status"),
        _optional_string(value.get("result_commit"), "reconciliation result commit"),
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


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise StateFormatError(f"invalid {name}")
    return tuple(_string(item, name) for item in value)


def _nonnegative_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise StateFormatError(f"invalid {name}")
    return value
