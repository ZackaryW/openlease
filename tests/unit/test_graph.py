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
    snapshot_space_graph,
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


def test_space_graph_snapshot_ignores_a_disconnected_component() -> None:
    graph = AuthorityGraph(
        repositories=(RepositoryRecord("repo-1", "C:/repo1"),),
        authorities=(AuthorityRecord("a", "repo-1", "openspec"),),
    )
    expanded = AuthorityGraph(
        repositories=(
            *graph.repositories,
            RepositoryRecord("repo-2", "C:/repo2"),
        ),
        authorities=(
            *graph.authorities,
            AuthorityRecord("b", "repo-2", "openspec"),
        ),
    )

    assert snapshot_space_graph(
        graph, ("repo-1",), AffectedClaim(authority_ids=("a",))
    ) == snapshot_space_graph(
        expanded, ("repo-1",), AffectedClaim(authority_ids=("a",))
    )


def test_space_graph_snapshot_is_canonical_and_detects_relevant_topology() -> None:
    repositories = (
        RepositoryRecord("repo-1", "C:/repo1"),
        RepositoryRecord("repo-2", "C:/repo2"),
    )
    authorities = (
        AuthorityRecord("root", "repo-1", "openspec"),
        AuthorityRecord("a", "repo-1", "A/openspec"),
        AuthorityRecord("shared", "repo-2", "openspec"),
    )
    graph = AuthorityGraph(
        repositories=repositories,
        authorities=authorities,
        parents=(ParentRelationship("a", "root"),),
        dependencies=(Dependency("repo-1", "shared", AccessRole.READ_ONLY),),
    )
    reordered = AuthorityGraph(
        repositories=tuple(reversed(repositories)),
        authorities=tuple(reversed(authorities)),
        parents=tuple(reversed(graph.parents)),
        dependencies=tuple(reversed(graph.dependencies)),
    )
    claim = AffectedClaim(authority_ids=("a",))
    baseline = snapshot_space_graph(graph, ("repo-1",), claim)

    assert baseline == snapshot_space_graph(reordered, ("repo-1",), claim)

    with_authority = AuthorityGraph(
        repositories=graph.repositories,
        authorities=(
            *graph.authorities,
            AuthorityRecord("b", "repo-1", "B/openspec"),
        ),
        parents=graph.parents,
        dependencies=graph.dependencies,
    )
    with_dependency = AuthorityGraph(
        repositories=graph.repositories,
        authorities=graph.authorities,
        parents=graph.parents,
        dependencies=(
            *graph.dependencies,
            Dependency("a", "shared", AccessRole.WRITABLE),
        ),
    )

    assert baseline != snapshot_space_graph(with_authority, ("repo-1",), claim)
    assert baseline != snapshot_space_graph(with_dependency, ("repo-1",), claim)


def test_space_graph_snapshot_detects_expanded_conflict_coverage() -> None:
    graph = AuthorityGraph(
        repositories=(RepositoryRecord("repo-1", "C:/repo1"),),
        authorities=(
            AuthorityRecord("a", "repo-1", "A/openspec"),
            AuthorityRecord("b", "repo-1", "B/openspec"),
        ),
    )
    claim = AffectedClaim(authority_ids=("a",))
    baseline = snapshot_space_graph(graph, (), claim)
    expanded = snapshot_space_graph(
        AuthorityGraph(
            repositories=graph.repositories,
            authorities=graph.authorities,
            parents=(ParentRelationship("b", "a"),),
        ),
        (),
        claim,
    )

    assert baseline.conflict_authority_ids == ("a",)
    assert expanded.conflict_authority_ids == ("a", "b")
    assert baseline != expanded


def test_space_graph_snapshot_reuses_writable_dependency_closure() -> None:
    graph = AuthorityGraph(
        repositories=(
            RepositoryRecord("repo-1", "C:/repo1"),
            RepositoryRecord("repo-2", "C:/repo2"),
        ),
        authorities=(AuthorityRecord("shared", "repo-2", "openspec"),),
        dependencies=(Dependency("repo-1", "shared", AccessRole.WRITABLE),),
    )
    claim = AffectedClaim(repository_ids=("repo-1",))

    snapshot = snapshot_space_graph(graph, ("repo-1",), claim)

    assert snapshot.plan == resolve_affected_claim(graph, claim)
    assert snapshot.plan.held_authorities == ("shared",)
    assert snapshot.plan.work_repositories == ("repo-1", "repo-2")


def test_space_graph_snapshot_rejects_an_unknown_associated_repository() -> None:
    graph = AuthorityGraph(
        repositories=(RepositoryRecord("repo-1", "C:/repo1"),),
        authorities=(AuthorityRecord("a", "repo-1", "openspec"),),
    )

    with pytest.raises(GraphError, match="associated repositories"):
        snapshot_space_graph(graph, ("missing",), AffectedClaim(authority_ids=("a",)))
