from __future__ import annotations

from behave import given, then, when

from features.support.openlease_support import (
    blocked_successor,
    capture,
    ensure_repositories,
    ensure_topology,
    repository,
    space,
)
from openlease import (
    InvalidRequest,
    OpenLease,
    OwnershipConflict,
)
from openlease.core.graph import AccessRole
from openlease.utils.openspec_adapter import OpenSpecWorkset


@given("repo 1 contains a root OpenSpec authority and child authorities A and B")
def given_nested_topology(context) -> None:
    ensure_repositories(context)


@given("repo 2 consumes an OpenSpec authority hosted by repo 3")
def given_external_topology(context) -> None:
    ensure_repositories(context)


@when("the owner registers those repositories and authorities")
def register_nodes(context) -> None:
    for name, path in context.repos.items():
        context.system.register_repository(name, path)
    context.system.register_authority("root", "repo-1")
    context.system.register_authority("a", "repo-1", "A/openspec")
    context.system.register_authority("b", "repo-1", "B/openspec")
    context.system.register_authority("shared", "repo-3")


@when("relates A and B as children of the repo 1 root")
def relate_children(context) -> None:
    context.system.relate_parent("a", "root")
    context.system.relate_parent("b", "root")


@when("relates repo 2 as a consumer of the repo 3 authority")
def relate_external(context) -> None:
    context.system.relate_dependency("repo-2", "shared")


@then("status reports the complete typed authority graph")
def graph_is_complete(context) -> None:
    data = context.system.status().data
    assert len(data["repositories"]) == 3
    assert len(data["authorities"]) == 4
    assert {(item.child_id, item.parent_id) for item in data["parents"]} == {
        ("a", "root"),
        ("b", "root"),
    }
    assert data["dependencies"][0].access == "writable"


@then("no lease or OpenSpec workset projection is created")
@then("no lease or projection changes")
def no_lease_or_projection(context) -> None:
    assert context.system.snapshot().leases == ()
    assert context.openspec.worksets == {}


@given("a valid registered authority graph")
def valid_graph(context) -> None:
    ensure_topology(context)
    invalid = context.active_outline["invalid relationship"]
    if invalid == "a dependency cycle":
        context.system.relate_dependency("a", "b", AccessRole.READ_ONLY)
    context.graph_generation = context.system.snapshot().graph_generation


@when("the owner attempts to add {invalid_relationship}")
def add_invalid_relationship(context, invalid_relationship: str) -> None:
    operations = {
        "a containment cycle": lambda: context.system.relate_parent("root", "a"),
        "a dependency cycle": lambda: context.system.relate_dependency(
            "b", "a", AccessRole.READ_ONLY
        ),
        "a second containment parent": lambda: context.system.relate_parent("a", "b"),
        "a missing relationship endpoint": lambda: context.system.relate_parent(
            "missing", "root"
        ),
        "an endpoint of the wrong kind": lambda: context.system.relate_parent(
            "repo-1", "root"
        ),
    }
    capture(context, operations[invalid_relationship])


@then("the relationship is rejected")
def relationship_rejected(context) -> None:
    assert isinstance(context.error, InvalidRequest)


@then("the accepted graph generation is unchanged")
def graph_generation_unchanged(context) -> None:
    assert context.system.snapshot().graph_generation == context.graph_generation


@given("a registered repository contains a repository-relative OpenSpec authority")
def registered_single_authority(context) -> None:
    ensure_repositories(context)
    context.system.register_repository("repo-1", context.repos["repo-1"])
    context.system.register_authority("root", "repo-1")


@given("two linked worktrees share that repository's Git common directory")
def linked_worktrees(context) -> None:
    source = context.system.git.inspect(context.repos["repo-1"])
    context.linked = context.system.git.create_worktree(
        source,
        __import__(
            "openlease.utils.git_adapter", fromlist=["WorktreeRequest"]
        ).WorktreeRequest(context.root / "linked", "linked", source.head),
    ).root


@when("OpenLease inspects the authority through both worktrees")
def inspect_linked_authorities(context) -> None:
    context.identities = (
        context.system.resolve_authority(context.repos["repo-1"], "openspec"),
        context.system.resolve_authority(context.linked, "openspec"),
    )


@then("both physical contexts resolve to one logical authority identity")
def linked_identity_same(context) -> None:
    assert context.identities == ("root", "root")


@given("two clones have separate Git common directories")
def separate_clones(context) -> None:
    ensure_repositories(context)
    context.clone_a = context.repos["repo-1"]
    context.clone_b = context.repos["repo-2"]


@given("the owner has not registered them with one shared repository identity")
def register_one_clone(context) -> None:
    context.system.register_repository("clone-a", context.clone_a)
    context.system.register_authority("clone-a-root", "clone-a")


@when("OpenLease inspects corresponding OpenSpec paths in both clones")
def inspect_clones(context) -> None:
    context.identities = (
        context.system.resolve_authority(context.clone_a, "openspec"),
        context.system.resolve_authority(context.clone_b, "openspec"),
    )


@then("the paths resolve to distinct logical authorities")
def clone_identities_distinct(context) -> None:
    assert context.identities == ("clone-a-root", None)


@given("a durable OpenLease space is selected in a terminal environment")
def selected_durable_space(context) -> None:
    ensure_topology(context)
    space(context, "selected", authorities=("a",))
    context.selected = "selected"


@when("commands run from successive processes in that terminal")
def successive_processes(context) -> None:
    second = OpenLease(
        context.root / "state",
        worktree_base=context.root / "worktrees",
        openspec=context.openspec,
    )
    context.process_results = (
        context.system.status(context.selected),
        second.status(context.selected),
    )


@then("they target the same selected space identity")
def same_selected_space(context) -> None:
    assert all(
        result.data["spaces"][0].identifier == "selected"
        for result in context.process_results
    )


@then("no process or TTY identity owns its leases")
def leases_owned_by_space(context) -> None:
    context.system.lock(context.selected)
    assert {item.owner_id for item in context.system.snapshot().leases} == {"selected"}


@given("a terminal selected a locked OpenLease space")
def terminal_locked_space(context) -> None:
    ensure_topology(context)
    space(context, "selected", authorities=("a",))
    context.system.lock("selected")
    context.selected = "selected"


@when("the terminal exits without releasing it")
def terminal_exits(context) -> None:
    context.system = OpenLease(
        context.root / "state",
        worktree_base=context.root / "worktrees",
        openspec=context.openspec,
    )


@then("the space and its leases remain durable")
def locked_state_durable(context) -> None:
    assert context.system.status("selected").data["spaces"][0].status == "locked"
    assert context.system.snapshot().leases


@then("later commands can inspect or explicitly recover it")
def can_recover(context) -> None:
    assert context.system.status("selected").data
    assert context.system.recover("selected", force=True).data.status == "released"


@given("repo 1, repo 2, and repo 3 are associated with one space")
def all_repos_associated(context) -> None:
    ensure_topology(context)
    space(context, "selected")
    context.selected = "selected"


@when("the owner marks only repo 1 child A as affected")
def affect_only_a(context) -> None:
    context.system.set_affected("selected", authority_ids=("a",))
    context.result = context.system.status("selected")


@then("status reports all three repositories as associated context")
def all_context_reported(context) -> None:
    assert context.result.data["spaces"][0].associated_repository_ids == (
        "repo-1",
        "repo-2",
        "repo-3",
    )


@then("reports only child A in the direct affected claim")
def direct_claim_a(context) -> None:
    assert context.result.data["spaces"][0].affected_authority_ids == ("a",)


@then("reports the resolved writable authority closure separately")
def closure_separate(context) -> None:
    assert context.result.data["affected_plan"].held_authorities == ("a",)


@given("a space has atomically locked its complete affected closure")
def locked_complete_space(context) -> None:
    ensure_topology(context)
    space(context, "selected", authorities=("a",))
    context.system.lock("selected")
    context.before = context.system.snapshot()


@when("the owner tries to add one association or affected target incrementally")
def mutate_locked_shape(context) -> None:
    capture(
        context, lambda: context.system.affect_add("selected", authority_ids=("b",))
    )


@then("OpenLease rejects the mutation")
def mutation_rejected(context) -> None:
    assert isinstance(context.error, InvalidRequest)


@then("preserves the accepted shape and complete lease set")
def locked_shape_preserved(context) -> None:
    after = context.system.snapshot()
    assert after.spaces == context.before.spaces
    assert after.leases == context.before.leases


@given("a locked space owns one complete authority component")
def locked_component(context) -> None:
    ensure_topology(context)
    space(context, "selected", authorities=("a",))
    context.system.lock("selected")
    context.before = context.system.snapshot()


@when(
    "the owner explicitly registers a distinct repository and authority without "
    "relating them to that component"
)
@when("the owner explicitly registers a disconnected repository and authority")
def register_disconnected_component(context) -> None:
    path = repository(context.root / "repo-4")
    context.system.register_repository("repo-4", path)
    context.system.register_authority("detached", "repo-4")


@then("OpenLease accepts the disconnected authority component atomically")
def disconnected_component_accepted(context) -> None:
    state = context.system.snapshot()
    assert any(item.identifier == "repo-4" for item in state.repositories)
    assert any(item.identifier == "detached" for item in state.authorities)


@then("preserves the locked space's accepted shape and complete lease set")
def unrelated_locked_shape_preserved(context) -> None:
    after = context.system.snapshot()
    before_space = next(
        item for item in context.before.spaces if item.identifier == "selected"
    )
    after_space = next(item for item in after.spaces if item.identifier == "selected")
    assert after_space == before_space
    assert after.leases == context.before.leases


@given("a deferred space retains its current accepted topology baseline")
def deferred_current_baseline(context) -> None:
    blocked_successor(context)


@then("the deferred space remains eligible for promotion after its blockers clear")
def deferred_remains_promotable(context) -> None:
    context.system.release("blocker")
    context.system.set_handoff_disposition("blocker", "abandoned")
    result = context.system.lock("successor")
    assert result.data.status == "locked"


@when("an accepted topology addition changes its affected closure or conflict coverage")
def change_deferred_topology(context) -> None:
    context.system.release("blocker")
    context.system.set_handoff_disposition("blocker", "abandoned")
    context.system.relate_dependency("a", "shared", AccessRole.WRITABLE)


@then("OpenLease retains scoped topology drift for that space")
def deferred_drift_retained(context) -> None:
    state = context.system.snapshot()
    successor = next(item for item in state.spaces if item.identifier == "successor")
    assert successor.graph_generation != state.graph_generation


@then("rejects its promotion until it is explicitly replanned or replaced")
def stale_deferred_promotion_rejected(context) -> None:
    capture(context, lambda: context.system.lock("successor"))
    assert isinstance(context.error, InvalidRequest)
    assert "authority graph changed after deferral" in context.error.details


@given("an accepted space has associated affected and pinned members")
def accepted_space(context) -> None:
    ensure_topology(context)
    space(context, "selected", authorities=("a",))
    context.system.lock("selected")
    context.selected = "selected"


@when("the owner opens the space")
def owner_opens(context) -> None:
    context.result = context.system.open(context.selected)


@then("OpenLease creates or reuses one owned OpenSpec workset projection")
def projection_owned(context) -> None:
    assert len(context.openspec.worksets) == 1
    assert context.result.data.projection_fingerprint


@then("the projection contains the distinct effective member folders in planned order")
def projection_ordered(context) -> None:
    actual = next(iter(context.openspec.worksets.values()))
    assert len(actual.members) == len(dict.fromkeys(actual.members))
    assert actual.members[0] == context.repos["repo-1"].resolve()


@then(
    "OpenLease status retains the relationships omitted by the OpenSpec workset format"
)
def status_retains_relationships(context) -> None:
    status = context.system.status(context.selected).data
    assert status["parents"] and status["dependencies"]


@given("an OpenLease-owned projection no longer matches its recorded generation")
def modified_projection(context) -> None:
    accepted_space(context)
    context.system.open("selected")
    owned = context.openspec.worksets["openlease-selected"]
    context.openspec.worksets[owned.name] = OpenSpecWorkset(
        owned.name, owned.members[:-1]
    )
    context.openspec.worksets["user-workset"] = OpenSpecWorkset(
        "user-workset", (context.root,)
    )


@when("a lifecycle operation would replace or remove that projection")
def remove_modified_projection(context) -> None:
    capture(context, lambda: context.system.release("selected"))


@then("OpenLease reports an ownership conflict")
def ownership_conflict(context) -> None:
    assert isinstance(context.error, OwnershipConflict)


@then("preserves the modified projection and unrelated user worksets")
def projections_preserved(context) -> None:
    assert set(context.openspec.worksets) == {"openlease-selected", "user-workset"}


@given("a registered repository has no matching temporary space")
def registered_repo_without_temporary_space(context) -> None:
    ensure_topology(context)


@when(
    "successive commands omit explicit space selection from directories within "
    "its worktree and use one host-session token"
)
def resolve_repeated_cwd_selection(context) -> None:
    nested = context.repos["repo-1"] / "nested"
    nested.mkdir()
    context.temporary_results = (
        context.system.resolve_session_space(nested, "host-session"),
        context.system.resolve_session_space(context.repos["repo-1"], "host-session"),
    )
    context.selected = context.temporary_results[-1].data.identifier


@then("OpenLease selects one temporary draft associated with that repository")
def one_temporary_draft_selected(context) -> None:
    first, second = (result.data for result in context.temporary_results)
    assert first.identifier == second.identifier
    assert second.associated_repository_ids == ("repo-1",)
    assert len(context.system.snapshot().spaces) == 1


@then("the draft has no affected claim or lease")
def temporary_draft_has_no_claim_or_lease(context) -> None:
    selected = context.system.status(context.selected).data["spaces"][0]
    assert selected.affected_repository_ids == ()
    assert selected.affected_authority_ids == ()
    assert selected.held_authority_ids == ()
    assert context.system.snapshot().leases == ()


@then("no topology is inferred from the working directory")
def cwd_infers_no_topology(context) -> None:
    state = context.system.snapshot()
    assert len(state.repositories) == 3
    assert len(state.authorities) == 4


@given("a host-session token and cwd could select a temporary space")
def implicit_selection_context(context) -> None:
    ensure_topology(context)


@given("a durable space is explicitly selected")
def explicit_durable_selection(context) -> None:
    space(context, "durable")
    context.selected = "durable"


@when("OpenLease resolves the command context")
def resolve_explicit_command_context(context) -> None:
    context.result = context.system.select_space(context.selected)


@then("it selects the explicit durable space")
def explicit_space_selected(context) -> None:
    assert context.result.data["space"] == "durable"


@then("creates or reclaims no temporary space")
def no_temporary_space_created(context) -> None:
    assert all(item.temporary is None for item in context.system.snapshot().spaces)


@given("cwd does not resolve uniquely to one registered Git worktree")
def unresolved_cwd(context) -> None:
    ensure_repositories(context)
    context.cwd = context.repos["repo-1"]


@when("a command omits explicit space selection")
def resolve_unselected_command(context) -> None:
    capture(
        context,
        lambda: context.system.resolve_session_space(context.cwd, "host-session"),
    )


@then("OpenLease rejects implicit selection")
def implicit_selection_rejected(context) -> None:
    assert isinstance(context.error, InvalidRequest)


@then("creates no space or topology")
def no_space_or_topology_created(context) -> None:
    state = context.system.snapshot()
    assert state.spaces == ()
    assert state.repositories == ()
    assert state.authorities == ()


@given("an ended host session left a clean temporary draft for one canonical worktree")
def abandoned_clean_temporary_draft(context) -> None:
    ensure_topology(context)
    context.abandoned = context.system.resolve_session_space(
        context.repos["repo-1"], "session-a"
    ).data


@when("a new host session implicitly selects that worktree")
def new_session_selects_worktree(context) -> None:
    context.result = context.system.resolve_session_space(
        context.repos["repo-1"], "session-b"
    )


@then("OpenLease rebinds the existing draft to the new session atomically")
def abandoned_draft_rebound(context) -> None:
    assert context.result.data.identifier == context.abandoned.identifier
    assert context.result.data.temporary != context.abandoned.temporary


@then("preserves its space identity and complete draft shape")
def reclaimed_shape_preserved(context) -> None:
    assert context.result.data.associated_repository_ids == (
        context.abandoned.associated_repository_ids
    )
    assert context.result.data.affected_authority_ids == (
        context.abandoned.affected_authority_ids
    )


@given("a prior matching space carries lease, configuration, or recovery evidence")
def retained_matching_space(context) -> None:
    ensure_topology(context)
    temporary = context.system.resolve_session_space(
        context.repos["repo-1"], "session-a"
    ).data
    context.system.set_affected(temporary.identifier, authority_ids=("a",))
    context.retained = context.system.lock(temporary.identifier).data


@then("OpenLease preserves the prior space and its evidence unchanged")
def retained_space_preserved(context) -> None:
    current = context.system.status(context.retained.identifier).data["spaces"][0]
    assert current == context.retained
    assert current.held_authority_ids == ("a",)


@then("scaffolds a distinct temporary draft for the new session")
def distinct_temporary_draft_created(context) -> None:
    assert context.result.data.identifier != context.retained.identifier
    assert context.result.data.temporary is not None


@given("a host session owns a temporary space that remains fully disposable")
def host_owns_disposable_space(context) -> None:
    ensure_topology(context)
    context.temporary_space = context.system.resolve_session_space(
        context.repos["repo-1"], "host-session"
    ).data


@when("that host session closes")
def close_host_session(context) -> None:
    context.result = context.system.close_temporary_session("host-session")


@then("OpenLease removes only that temporary space")
def removes_only_temporary_space(context) -> None:
    assert context.result.data["removed"] == (context.temporary_space.identifier,)
    assert context.system.snapshot().spaces == ()


@then("preserves registered topology and every other space")
def topology_preserved_after_temporary_close(context) -> None:
    state = context.system.snapshot()
    assert len(state.repositories) == 3
    assert len(state.authorities) == 4


@given("a host session owns a temporary space with a complete explicit affected claim")
def temporary_space_with_complete_claim(context) -> None:
    ensure_topology(context)
    temporary = context.system.resolve_session_space(
        context.repos["repo-1"], "host-session"
    ).data
    context.system.set_affected(temporary.identifier, authority_ids=("a",))
    context.selected = temporary.identifier


@when("the space atomically acquires its complete lease set")
def temporary_space_locks(context) -> None:
    context.result = context.system.lock(context.selected)


@then("OpenLease clears its temporary ownership in the same transition")
def temporary_ownership_cleared(context) -> None:
    assert context.result.data.temporary is None


@then("retains it as a durable locked space after the host session disappears")
def promoted_lock_remains_durable(context) -> None:
    assert context.system.close_temporary_session("host-session").changed is False
    retained = context.system.status(context.selected).data["spaces"][0]
    assert retained.status == "locked"
    assert retained.held_authority_ids == ("a",)
