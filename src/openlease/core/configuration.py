from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from openlease.core.state_codec import ConfigurationSourceRecord, OpenLeaseState


class ConfigurationError(ValueError):
    """Configuration metadata or source content cannot be resolved safely."""


class RootProvenance(StrEnum):
    DEFAULT = "default"
    PRODUCT_ROOT = "product_root"
    EXPLICIT = "explicit"


class SourceKind(StrEnum):
    REPOSITORY = "repository"
    EXTERNAL = "external"


class TargetKind(StrEnum):
    REPOSITORY = "repository"
    AUTHORITY = "authority"


@dataclass(frozen=True, slots=True)
class ExtensionRootPolicy:
    product_root: Path | None = None
    configuration_root: Path | None = None
    data_root: Path | None = None
    cache_root: Path | None = None


@dataclass(frozen=True, slots=True)
class ResolvedRoot:
    path: Path
    provenance: RootProvenance


@dataclass(frozen=True, slots=True)
class ExtensionRoots:
    configuration: ResolvedRoot
    data: ResolvedRoot
    cache: ResolvedRoot


@dataclass(frozen=True, slots=True)
class RepositoryLocation:
    identifier: str
    path: Path


@dataclass(frozen=True, slots=True)
class MemberLocation:
    repository_id: str
    effective_path: Path


@dataclass(frozen=True, slots=True)
class BoundSource:
    kind: SourceKind
    path: Path
    repository_id: str | None = None


@dataclass(frozen=True, slots=True)
class ConfigurationTarget:
    kind: TargetKind
    identifier: str

    @classmethod
    def repository(cls, identifier: str) -> ConfigurationTarget:
        return cls(TargetKind.REPOSITORY, identifier)

    @classmethod
    def authority(cls, identifier: str) -> ConfigurationTarget:
        return cls(TargetKind.AUTHORITY, identifier)


@dataclass(frozen=True, slots=True)
class PlannedSource:
    identifier: str
    extension_id: str
    scope_kind: str
    scope_id: str | None
    resolved_path: Path
    repository_id: str | None
    order: int
    binding_revision: int


def resolve_extension_roots(
    state_root: Path,
    extension_id: str,
    policy: ExtensionRootPolicy,
) -> ExtensionRoots:
    if not extension_id or extension_id in {".", ".."} or any(
        separator in extension_id for separator in ("/", "\\")
    ):
        raise ConfigurationError("extension identifier must be one path segment")
    state_namespace = state_root.resolve() / "extensions" / extension_id
    product_namespace = (
        policy.product_root.resolve() / "extensions" / extension_id
        if policy.product_root is not None
        else None
    )

    def select(explicit: Path | None, role: str) -> ResolvedRoot:
        if explicit is not None:
            return ResolvedRoot(explicit.resolve(), RootProvenance.EXPLICIT)
        if product_namespace is not None:
            return ResolvedRoot(
                (product_namespace / role).resolve(), RootProvenance.PRODUCT_ROOT
            )
        return ResolvedRoot(
            (state_namespace / role).resolve(), RootProvenance.DEFAULT
        )

    return ExtensionRoots(
        configuration=select(policy.configuration_root, "configuration"),
        data=select(policy.data_root, "data"),
        cache=select(policy.cache_root, "cache"),
    )


def bind_configuration_source(
    source: Path,
    repositories: tuple[RepositoryLocation, ...],
) -> BoundSource:
    canonical = _readable_document(source)
    matches: list[tuple[int, RepositoryLocation, Path]] = []
    for repository in repositories:
        root = repository.path.resolve()
        try:
            relative = canonical.relative_to(root)
        except ValueError:
            continue
        matches.append((len(root.parts), repository, relative))
    if not matches:
        return BoundSource(SourceKind.EXTERNAL, canonical)
    _, repository, relative = max(matches, key=lambda item: item[0])
    return BoundSource(SourceKind.REPOSITORY, relative, repository.identifier)


def resolve_bound_source(
    source: BoundSource,
    members: tuple[MemberLocation, ...],
) -> Path:
    if source.kind is SourceKind.EXTERNAL:
        return _readable_document(source.path)
    member = next(
        (item for item in members if item.repository_id == source.repository_id), None
    )
    if member is None:
        raise ConfigurationError(
            f"configuration repository member not found: {source.repository_id}"
        )
    if source.path.is_absolute() or ".." in source.path.parts:
        raise ConfigurationError("repository configuration path must be relative")
    return _readable_document(member.effective_path.resolve() / source.path)


def _readable_document(path: Path) -> Path:
    canonical = path.resolve()
    if not canonical.is_file():
        raise ConfigurationError(f"configuration source is not a file: {canonical}")
    try:
        with canonical.open("rb"):
            pass
    except OSError as error:
        raise ConfigurationError(
            f"configuration source is not readable: {canonical}"
        ) from error
    return canonical


def plan_configuration_sources(
    state: OpenLeaseState,
    extension_id: str,
    space_id: str,
    target: ConfigurationTarget,
) -> tuple[PlannedSource, ...]:
    space = next((item for item in state.spaces if item.identifier == space_id), None)
    if space is None:
        raise ConfigurationError(f"space not found: {space_id}")
    repository_id: str
    authority_chain: tuple[str, ...] = ()
    if target.kind is TargetKind.REPOSITORY:
        repository = next(
            (
                item
                for item in state.repositories
                if item.identifier == target.identifier
            ),
            None,
        )
        if repository is None:
            raise ConfigurationError(f"repository not found: {target.identifier}")
        repository_id = repository.identifier
    else:
        authority = next(
            (
                item
                for item in state.authorities
                if item.identifier == target.identifier
            ),
            None,
        )
        if authority is None:
            raise ConfigurationError(f"authority not found: {target.identifier}")
        repository_id = authority.repository_id
        parents = {item.child_id: item.parent_id for item in state.parents}
        ancestry: list[str] = [authority.identifier]
        while ancestry[-1] in parents:
            ancestry.append(parents[ancestry[-1]])
        authority_chain = tuple(reversed(ancestry))
    if repository_id not in space.associated_repository_ids:
        raise ConfigurationError(
            f"target repository is not associated with space: {repository_id}"
        )

    sources = tuple(
        item
        for item in state.configuration_sources
        if item.extension_id == extension_id
    )

    def in_scope(
        kind: str, identifier: str | None
    ) -> tuple[ConfigurationSourceRecord, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in sources
                    if item.scope_kind == kind and item.scope_id == identifier
                ),
                key=lambda item: (item.order, item.identifier),
            )
        )

    ordered: list[ConfigurationSourceRecord] = list(in_scope("machine", None))
    attachments = sorted(
        (
            item
            for item in state.space_pack_attachments
            if item.space_id == space_id and item.extension_id == extension_id
        ),
        key=lambda item: (item.order, item.pack_id),
    )
    for attachment in attachments:
        ordered.extend(in_scope("pack", attachment.pack_id))
    ordered.extend(in_scope("space", space_id))
    ordered.extend(in_scope("repository", repository_id))
    for authority_id in authority_chain:
        ordered.extend(in_scope("authority", authority_id))
    return tuple(_planned_source(state, space_id, item) for item in ordered)


def _planned_source(
    state: OpenLeaseState,
    space_id: str,
    source: ConfigurationSourceRecord,
) -> PlannedSource:
    if source.source_kind == SourceKind.EXTERNAL.value:
        resolved = Path(source.path).resolve()
    else:
        space = next(item for item in state.spaces if item.identifier == space_id)
        member = next(
            (
                item
                for item in space.members
                if item.repository_id == source.repository_id
            ),
            None,
        )
        if member is not None:
            root = Path(member.effective_path)
        else:
            repository = next(
                item
                for item in state.repositories
                if item.identifier == source.repository_id
            )
            root = Path(repository.path)
        resolved = (root.resolve() / source.path).resolve()
    return PlannedSource(
        identifier=source.identifier,
        extension_id=source.extension_id,
        scope_kind=source.scope_kind,
        scope_id=source.scope_id,
        resolved_path=resolved,
        repository_id=source.repository_id,
        order=source.order,
        binding_revision=source.revision,
    )
