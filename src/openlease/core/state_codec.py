from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
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
class TemporarySpaceDescriptor:
    repository_id: str
    worktree_path: str
    session_fingerprint: str


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
    temporary: TemporarySpaceDescriptor | None = None


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
class ExtensionRootPolicyRecord:
    extension_id: str
    product_root: str | None = None
    configuration_root: str | None = None
    data_root: str | None = None
    cache_root: str | None = None


@dataclass(frozen=True, slots=True)
class ConfigurationPackRecord:
    identifier: str
    extension_id: str


@dataclass(frozen=True, slots=True)
class ConfigurationSourceRecord:
    identifier: str
    extension_id: str
    scope_kind: str
    scope_id: str | None
    source_kind: str
    path: str
    repository_id: str | None = None
    codec: str = ""
    layout: str = ""
    writable: bool = False
    order: int = 0
    revision: int = 0


@dataclass(frozen=True, slots=True)
class SpacePackAttachmentRecord:
    space_id: str
    extension_id: str
    pack_id: str
    order: int = 0


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
    configuration_generation: int = 0
    extension_roots: tuple[ExtensionRootPolicyRecord, ...] = ()
    configuration_packs: tuple[ConfigurationPackRecord, ...] = ()
    configuration_sources: tuple[ConfigurationSourceRecord, ...] = ()
    space_pack_attachments: tuple[SpacePackAttachmentRecord, ...] = ()
    schema_version: int = 4


def structural_key(value: object) -> str:
    """Return a stable key for a closed JSON-compatible value structure."""

    def normalize(item: object) -> object:
        if hasattr(item, "__dataclass_fields__"):
            return normalize(asdict(item))
        if isinstance(item, Enum):
            return normalize(item.value)
        if isinstance(item, Path):
            return item.as_posix()
        if isinstance(item, datetime):
            return {"$managed": "datetime", "value": item.isoformat()}
        if isinstance(item, date):
            return {"$managed": "date", "value": item.isoformat()}
        if isinstance(item, time):
            return {"$managed": "time", "value": item.isoformat()}
        if isinstance(item, Mapping):
            return {str(key): normalize(child) for key, child in item.items()}
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
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
    schema_version = value.get("schema_version")
    common_keys = {
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
    }
    current_keys = common_keys | {
        "configuration_generation",
        "extension_roots",
        "configuration_packs",
        "configuration_sources",
        "space_pack_attachments",
    }
    if schema_version not in {3, 4}:
        raise StateFormatError(
            "unsupported OpenLease state schema; reinitialize OpenLease state"
        )
    _require_keys(value, current_keys)
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
    configuration_generation = _nonnegative_int(
        value.get("configuration_generation", 0), "configuration generation"
    )
    extension_roots = tuple(
        _extension_root(item)
        for item in _object_list(value.get("extension_roots", []), "extension roots")
    )
    configuration_packs = tuple(
        _configuration_pack(item)
        for item in _object_list(
            value.get("configuration_packs", []), "configuration packs"
        )
    )
    configuration_sources = tuple(
        _configuration_source(item)
        for item in _object_list(
            value.get("configuration_sources", []), "configuration sources"
        )
    )
    space_pack_attachments = tuple(
        _space_pack_attachment(item)
        for item in _object_list(
            value.get("space_pack_attachments", []), "space pack attachments"
        )
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
            configuration_generation=configuration_generation,
            extension_roots=extension_roots,
            configuration_packs=configuration_packs,
            configuration_sources=configuration_sources,
            space_pack_attachments=space_pack_attachments,
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
        "configuration_generation": state.configuration_generation,
        "extension_roots": [asdict(item) for item in state.extension_roots],
        "configuration_packs": [asdict(item) for item in state.configuration_packs],
        "configuration_sources": [asdict(item) for item in state.configuration_sources],
        "space_pack_attachments": [
            asdict(item) for item in state.space_pack_attachments
        ],
    }
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def validate_state(state: OpenLeaseState) -> OpenLeaseState:
    if state.schema_version != 4:
        raise StateFormatError(
            "unsupported OpenLease state schema; reinitialize OpenLease state"
        )
    _nonnegative_int(state.configuration_generation, "configuration generation")
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
        if space.temporary is not None:
            if space.temporary.repository_id not in known_repositories:
                raise StateFormatError(
                    f"space {space.identifier} temporary repository is missing"
                )
            if not Path(space.temporary.worktree_path).is_absolute():
                raise StateFormatError("temporary worktree path must be absolute")
            _string(
                space.temporary.session_fingerprint,
                "temporary session fingerprint",
            )
    for lease in state.leases:
        if (
            lease.authority_id not in known_authorities
            or lease.owner_id not in known_spaces
        ):
            raise StateFormatError("lease has a missing endpoint")
    if len({item.authority_id for item in state.leases}) != len(state.leases):
        raise StateFormatError("duplicate authority lease")
    root_extension_ids = [item.extension_id for item in state.extension_roots]
    if len(root_extension_ids) != len(set(root_extension_ids)):
        raise StateFormatError("duplicate extension root policy")
    pack_keys = [
        (item.extension_id, item.identifier) for item in state.configuration_packs
    ]
    if len(pack_keys) != len(set(pack_keys)):
        raise StateFormatError("duplicate configuration pack")
    source_keys = [
        (item.extension_id, item.identifier) for item in state.configuration_sources
    ]
    if len(source_keys) != len(set(source_keys)):
        raise StateFormatError("duplicate configuration source")
    known_packs = set(pack_keys)
    physical_sources: dict[tuple[str, str | None, str], ConfigurationSourceRecord] = {}
    for source in state.configuration_sources:
        if source.scope_kind not in {
            "machine",
            "pack",
            "space",
            "repository",
            "authority",
        }:
            raise StateFormatError("invalid configuration source scope")
        if source.source_kind not in {"repository", "external"}:
            raise StateFormatError("invalid configuration source kind")
        _nonnegative_int(source.order, "configuration source order")
        _nonnegative_int(source.revision, "configuration source revision")
        if not source.codec:
            raise StateFormatError(
                "configuration source is missing its current codec; reinitialize state"
            )
        if source.layout not in {"shared", "dedicated"}:
            raise StateFormatError(
                "configuration source is missing its current layout; reinitialize state"
            )
        if not isinstance(source.writable, bool):
            raise StateFormatError("invalid configuration source write authority")
        if source.scope_kind == "machine" and source.scope_id is not None:
            raise StateFormatError("machine source cannot have a scope identifier")
        if source.scope_kind != "machine" and source.scope_id is None:
            raise StateFormatError(
                "configuration source scope is missing an identifier"
            )
        if (
            source.scope_kind == "pack"
            and (
                source.extension_id,
                source.scope_id,
            )
            not in known_packs
        ):
            raise StateFormatError("configuration source has a missing pack")
        if source.scope_kind == "space" and source.scope_id not in known_spaces:
            raise StateFormatError("configuration source has a missing space")
        if (
            source.scope_kind == "repository"
            and source.scope_id not in known_repositories
        ):
            raise StateFormatError("configuration source has a missing repository")
        if (
            source.scope_kind == "authority"
            and source.scope_id not in known_authorities
        ):
            raise StateFormatError("configuration source has a missing authority")
        if source.source_kind == "repository":
            if source.repository_id not in known_repositories:
                raise StateFormatError("configuration source repository is missing")
            relative = Path(source.path)
            if relative.is_absolute() or ".." in relative.parts:
                raise StateFormatError("repository configuration path must be relative")
        else:
            if source.repository_id is not None:
                raise StateFormatError("external configuration source has a repository")
            if not Path(source.path).is_absolute():
                raise StateFormatError(
                    "external configuration source path must be absolute"
                )
        physical_key = (source.source_kind, source.repository_id, source.path)
        existing_physical = physical_sources.get(physical_key)
        if existing_physical is not None:
            if "dedicated" in {existing_physical.layout, source.layout}:
                raise StateFormatError(
                    "dedicated configuration document has multiple bindings"
                )
            if existing_physical.codec != source.codec:
                raise StateFormatError(
                    "shared configuration document has incompatible codecs"
                )
        else:
            physical_sources[physical_key] = source
    attachment_keys = [
        (item.space_id, item.extension_id, item.pack_id)
        for item in state.space_pack_attachments
    ]
    if len(attachment_keys) != len(set(attachment_keys)):
        raise StateFormatError("duplicate space pack attachment")
    for attachment in state.space_pack_attachments:
        _nonnegative_int(attachment.order, "space pack attachment order")
        if attachment.space_id not in known_spaces:
            raise StateFormatError("space pack attachment has a missing space")
        if (attachment.extension_id, attachment.pack_id) not in known_packs:
            raise StateFormatError("space pack attachment has a missing pack")
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


def _temporary_space_descriptor(value: object) -> TemporarySpaceDescriptor | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise StateFormatError("invalid temporary space descriptor")
    _require_keys(
        value,
        {"repository_id", "worktree_path", "session_fingerprint"},
    )
    return TemporarySpaceDescriptor(
        _string(value.get("repository_id"), "temporary repository"),
        _string(value.get("worktree_path"), "temporary worktree path"),
        _string(value.get("session_fingerprint"), "temporary session fingerprint"),
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
        "temporary",
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
        temporary=_temporary_space_descriptor(value.get("temporary")),
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


def _extension_root(value: dict[str, Any]) -> ExtensionRootPolicyRecord:
    _require_keys(
        value,
        {
            "extension_id",
            "product_root",
            "configuration_root",
            "data_root",
            "cache_root",
        },
    )
    return ExtensionRootPolicyRecord(
        extension_id=_string(value.get("extension_id"), "extension root identifier"),
        product_root=_optional_string(value.get("product_root"), "product root"),
        configuration_root=_optional_string(
            value.get("configuration_root"), "configuration root"
        ),
        data_root=_optional_string(value.get("data_root"), "data root"),
        cache_root=_optional_string(value.get("cache_root"), "cache root"),
    )


def _configuration_pack(value: dict[str, Any]) -> ConfigurationPackRecord:
    _require_keys(value, {"identifier", "extension_id"})
    return ConfigurationPackRecord(
        identifier=_string(value.get("identifier"), "configuration pack identifier"),
        extension_id=_string(value.get("extension_id"), "pack extension identifier"),
    )


def _configuration_source(value: dict[str, Any]) -> ConfigurationSourceRecord:
    _require_keys(
        value,
        {
            "identifier",
            "extension_id",
            "scope_kind",
            "scope_id",
            "source_kind",
            "path",
            "repository_id",
            "codec",
            "layout",
            "writable",
            "order",
            "revision",
        },
    )
    return ConfigurationSourceRecord(
        identifier=_string(value.get("identifier"), "configuration source identifier"),
        extension_id=_string(value.get("extension_id"), "source extension identifier"),
        scope_kind=_string(value.get("scope_kind"), "configuration source scope"),
        scope_id=_optional_string(value.get("scope_id"), "source scope identifier"),
        source_kind=_string(value.get("source_kind"), "configuration source kind"),
        path=_string(value.get("path"), "configuration source path"),
        repository_id=_optional_string(
            value.get("repository_id"), "source repository identifier"
        ),
        codec=_string(value.get("codec"), "configuration source codec"),
        layout=_string(value.get("layout"), "configuration source layout"),
        writable=_boolean(
            value.get("writable"), "configuration source write authority"
        ),
        order=_nonnegative_int(value.get("order", 0), "configuration source order"),
        revision=_nonnegative_int(
            value.get("revision", 0), "configuration source revision"
        ),
    )


def _space_pack_attachment(value: dict[str, Any]) -> SpacePackAttachmentRecord:
    _require_keys(value, {"space_id", "extension_id", "pack_id", "order"})
    return SpacePackAttachmentRecord(
        space_id=_string(value.get("space_id"), "attachment space identifier"),
        extension_id=_string(
            value.get("extension_id"), "attachment extension identifier"
        ),
        pack_id=_string(value.get("pack_id"), "attachment pack identifier"),
        order=_nonnegative_int(value.get("order", 0), "attachment order"),
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


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise StateFormatError(f"invalid {name}")
    return value


def _nonnegative_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise StateFormatError(f"invalid {name}")
    return value
