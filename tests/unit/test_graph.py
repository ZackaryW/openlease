import pytest

from openlease.core.graph import (
    AccessRole,
    AffectedClaim,
    AuthorityGraph,
    Dependency,
    GraphError,
    Lease,
    ParentRelationship,
    audit_authority_boundaries,
    conflicting_leases,
    resolve_affected_claim,
    validate_graph,
)
from openlease.core.state_codec import AuthorityRecord, RepositoryRecord


def test_rejects_a_parent_cycle() -> None:
    graph = AuthorityGraph(
        repositories=(RepositoryRecord("repo-1", "C:/repo1"),),
        authorities=(
            AuthorityRecord("a", "repo-1", "A/openspec"),
            AuthorityRecord("b", "repo-1", "B/openspec"),
        ),
        parents=(ParentRelationship("a", "b"), ParentRelationship("b", "a")),
    )

    with pytest.raises(GraphError, match="cycle"):
        validate_graph(graph)


def test_rejects_a_dependency_cycle() -> None:
    graph = AuthorityGraph(
        repositories=(RepositoryRecord("repo-1", "C:/repo1"),),
        authorities=(
            AuthorityRecord("a", "repo-1", "A/openspec"),
            AuthorityRecord("b", "repo-1", "B/openspec"),
        ),
        dependencies=(
            Dependency("a", "b", AccessRole.WRITABLE),
            Dependency("b", "a", AccessRole.READ_ONLY),
        ),
    )

    with pytest.raises(GraphError, match="dependency graph contains a cycle"):
        validate_graph(graph)


def test_resolves_only_the_affected_writable_closure() -> None:
    graph = AuthorityGraph(
        repositories=(
            RepositoryRecord("repo-1", "C:/repo1"),
            RepositoryRecord("repo-2", "C:/repo2"),
            RepositoryRecord("repo-3", "C:/repo3"),
        ),
        authorities=(
            AuthorityRecord("root", "repo-1", "openspec"),
            AuthorityRecord("a", "repo-1", "A/openspec"),
            AuthorityRecord("b", "repo-1", "B/openspec"),
            AuthorityRecord("shared", "repo-3", "openspec"),
        ),
        parents=(ParentRelationship("a", "root"), ParentRelationship("b", "root")),
        dependencies=(Dependency("repo-2", "shared", AccessRole.WRITABLE),),
    )

    plan = resolve_affected_claim(
        graph, AffectedClaim(repository_ids=("repo-2",), authority_ids=("a",))
    )

    assert plan.held_authorities == ("a", "shared")
    assert plan.work_repositories == ("repo-1", "repo-2", "repo-3")
    assert conflicting_leases(graph, plan, (Lease("b", "other"),)) == ()
    assert [
        item.authority_id
        for item in conflicting_leases(graph, plan, (Lease("root", "root-owner"),))
    ] == ["root"]


def test_audits_changed_openspec_paths_outside_held_authorities() -> None:
    graph = AuthorityGraph(
        repositories=(RepositoryRecord("repo-1", "C:/repo1"),),
        authorities=(
            AuthorityRecord("a", "repo-1", "A/openspec"),
            AuthorityRecord("b", "repo-1", "B/openspec"),
        ),
    )
    plan = resolve_affected_claim(graph, AffectedClaim(authority_ids=("a",)))

    audit = audit_authority_boundaries(
        graph,
        plan,
        {"repo-1": ("A/openspec/spec.md", "B/openspec/spec.md", "src/app.py")},
    )

    assert [(item.authority_id, item.path) for item in audit.violations] == [
        ("b", "B/openspec/spec.md")
    ]
