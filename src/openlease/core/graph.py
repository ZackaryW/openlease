from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from openlease.core.state_codec import AuthorityRecord, RepositoryRecord


class GraphError(ValueError):
    """An authority graph violates a structural invariant."""


class AccessRole(StrEnum):
    READ_ONLY = "read_only"
    WRITABLE = "writable"


@dataclass(frozen=True, slots=True)
class ParentRelationship:
    child_id: str
    parent_id: str


@dataclass(frozen=True, slots=True)
class Dependency:
    consumer_id: str
    authority_id: str
    access: AccessRole


@dataclass(frozen=True, slots=True)
class AuthorityGraph:
    repositories: tuple[RepositoryRecord, ...] = ()
    authorities: tuple[AuthorityRecord, ...] = ()
    parents: tuple[ParentRelationship, ...] = ()
    dependencies: tuple[Dependency, ...] = ()


@dataclass(frozen=True, slots=True)
class AffectedClaim:
    repository_ids: tuple[str, ...] = ()
    authority_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AffectedPlan:
    direct_repositories: tuple[str, ...]
    direct_authorities: tuple[str, ...]
    work_repositories: tuple[str, ...]
    held_authorities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Lease:
    authority_id: str
    owner_id: str


@dataclass(frozen=True, slots=True)
class LeaseConflict:
    authority_id: str
    owner_id: str
    requested_authority_id: str


@dataclass(frozen=True, slots=True)
class BoundaryViolation:
    repository_id: str
    authority_id: str
    path: str


@dataclass(frozen=True, slots=True)
class BoundaryAudit:
    violations: tuple[BoundaryViolation, ...]


def validate_graph(graph: AuthorityGraph) -> AuthorityGraph:
    repositories = {item.identifier for item in graph.repositories}
    authorities = {item.identifier for item in graph.authorities}
    if len(repositories) != len(graph.repositories):
        raise GraphError("duplicate repository")
    if len(authorities) != len(graph.authorities):
        raise GraphError("duplicate authority")
    parent_by_child: dict[str, str] = {}
    for relationship in graph.parents:
        if (
            relationship.child_id not in authorities
            or relationship.parent_id not in authorities
        ):
            raise GraphError("parent relationship has a missing authority")
        if relationship.child_id in parent_by_child:
            raise GraphError("authority has multiple containment parents")
        parent_by_child[relationship.child_id] = relationship.parent_id
    for start in parent_by_child:
        seen: set[str] = set()
        cursor = start
        while cursor in parent_by_child:
            if cursor in seen:
                raise GraphError("authority graph contains a cycle")
            seen.add(cursor)
            cursor = parent_by_child[cursor]
    for dependency in graph.dependencies:
        if dependency.consumer_id not in repositories | authorities:
            raise GraphError("dependency has a missing consumer")
        if dependency.authority_id not in authorities:
            raise GraphError("dependency has a missing authority")
    dependency_targets: dict[str, set[str]] = {}
    for dependency in graph.dependencies:
        if dependency.consumer_id in authorities:
            dependency_targets.setdefault(dependency.consumer_id, set()).add(
                dependency.authority_id
            )
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(authority_id: str) -> None:
        if authority_id in visiting:
            raise GraphError("dependency graph contains a cycle")
        if authority_id in visited:
            return
        visiting.add(authority_id)
        for target_id in dependency_targets.get(authority_id, ()):
            visit(target_id)
        visiting.remove(authority_id)
        visited.add(authority_id)

    for authority_id in authorities:
        visit(authority_id)
    return graph


def resolve_affected_claim(graph: AuthorityGraph, claim: AffectedClaim) -> AffectedPlan:
    validate_graph(graph)
    repositories = {item.identifier: item for item in graph.repositories}
    authorities = {item.identifier: item for item in graph.authorities}
    unknown_repositories = set(claim.repository_ids) - set(repositories)
    unknown_authorities = set(claim.authority_ids) - set(authorities)
    if unknown_repositories or unknown_authorities:
        raise GraphError("affected claim contains an unknown target")
    held = set(claim.authority_ids)
    affected_nodes = set(claim.repository_ids) | held
    changed = True
    while changed:
        changed = False
        for dependency in graph.dependencies:
            if (
                dependency.access is AccessRole.WRITABLE
                and dependency.consumer_id in affected_nodes
                and dependency.authority_id not in held
            ):
                held.add(dependency.authority_id)
                affected_nodes.add(dependency.authority_id)
                changed = True
    work_repositories = set(claim.repository_ids)
    work_repositories.update(authorities[item].repository_id for item in held)
    return AffectedPlan(
        tuple(sorted(set(claim.repository_ids))),
        tuple(sorted(set(claim.authority_ids))),
        tuple(sorted(work_repositories)),
        tuple(sorted(held)),
    )


def conflicting_leases(
    graph: AuthorityGraph,
    plan: AffectedPlan,
    leases: tuple[Lease, ...],
) -> tuple[LeaseConflict, ...]:
    validate_graph(graph)
    parent_by_child = {item.child_id: item.parent_id for item in graph.parents}

    def ancestors(authority_id: str) -> set[str]:
        result: set[str] = set()
        cursor = authority_id
        while cursor in parent_by_child:
            cursor = parent_by_child[cursor]
            result.add(cursor)
        return result

    results: list[LeaseConflict] = []
    for lease in leases:
        for requested in plan.held_authorities:
            if (
                lease.authority_id == requested
                or lease.authority_id in ancestors(requested)
                or requested in ancestors(lease.authority_id)
            ):
                results.append(
                    LeaseConflict(lease.authority_id, lease.owner_id, requested)
                )
                break
    return tuple(sorted(results, key=lambda item: (item.authority_id, item.owner_id)))


def audit_authority_boundaries(
    graph: AuthorityGraph,
    plan: AffectedPlan,
    changed_paths: dict[str, tuple[str, ...]],
) -> BoundaryAudit:
    held = set(plan.held_authorities)
    by_repository: dict[str, list[AuthorityRecord]] = {}
    for authority in graph.authorities:
        by_repository.setdefault(authority.repository_id, []).append(authority)
    violations: list[BoundaryViolation] = []
    for repository_id, paths in changed_paths.items():
        authorities = sorted(
            by_repository.get(repository_id, ()),
            key=lambda item: len(PurePosixPath(item.relative_path).parts),
            reverse=True,
        )
        for path in paths:
            normalized = PurePosixPath(path.replace("\\", "/")).as_posix()
            matched = next(
                (
                    authority
                    for authority in authorities
                    if normalized == PurePosixPath(authority.relative_path).as_posix()
                    or normalized.startswith(
                        PurePosixPath(authority.relative_path).as_posix() + "/"
                    )
                ),
                None,
            )
            if matched is not None and matched.identifier not in held:
                violations.append(
                    BoundaryViolation(repository_id, matched.identifier, normalized)
                )
    return BoundaryAudit(
        tuple(
            sorted(
                violations,
                key=lambda item: (item.repository_id, item.path, item.authority_id),
            )
        )
    )
