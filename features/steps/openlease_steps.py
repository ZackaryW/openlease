from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from behave import given, then, when
from support import blocked_successor, ensure_repositories, ensure_topology, git, space
from typer.testing import CliRunner

from openlease import (
    AuthorityConflict,
    BranchSelection,
    InvalidRequest,
    OpenLease,
    OwnershipConflict,
    PreparationFailed,
    ReconcileSelection,
)
from openlease.cli import app
from openlease.core.graph import AccessRole
from openlease.utils.git_adapter import IntegrationStrategy
from openlease.utils.openspec_adapter import OpenSpecWorkset


def capture(context, operation) -> None:
    context.error = None
    context.result = None
    try:
        context.result = operation()
    except Exception as error:
        context.error = error


def member(context, space_id: str, repository_id: str):
    current = next(
        item for item in context.system.snapshot().spaces if item.identifier == space_id
    )
    return next(item for item in current.members if item.repository_id == repository_id)


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


@given(
    "a space has associated repositories but no complete explicit authority "
    "graph or affected claim"
)
def incomplete_claim(context) -> None:
    ensure_repositories(context)
    context.system.register_repository("repo-1", context.repos["repo-1"])
    context.system.create_space("selected")
    context.system.associate("selected", ("repo-1",))
    context.selected = "selected"


@when("the owner runs lockable or lock")
def run_incomplete_lock(context) -> None:
    capture(context, lambda: context.system.lockable("selected"))
    context.first_error = context.error
    capture(context, lambda: context.system.lock("selected"))


@then("OpenLease rejects acquisition without inferring or persisting relationships")
def incomplete_rejected(context) -> None:
    assert isinstance(context.first_error, InvalidRequest)
    assert isinstance(context.error, InvalidRequest)
    assert context.system.snapshot().authorities == ()


@given("repo 2 is affected")
def repo2_affected(context) -> None:
    ensure_topology(context)
    space(context, "selected", repositories=("repo-2",))
    context.selected = "selected"


@given("repo 2 has an explicit writable dependency on the authority hosted by repo 3")
def repo2_writable_dependency(context) -> None:
    assert any(
        item.consumer_id == "repo-2" and item.access == "writable"
        for item in context.system.snapshot().dependencies
    )


@when("OpenLease plans the affected closure")
def plan_closure(context) -> None:
    context.result = context.system.plan(context.selected)


@then("the closure includes the repo 3 hosted authority")
def closure_has_shared(context) -> None:
    assert "shared" in context.result.data.held_authorities


@then("excludes unrelated associated repositories")
def closure_excludes_unrelated(context) -> None:
    assert "repo-1" not in context.result.data.work_repositories


@given("two spaces associate the same authority only as read-only context")
def shared_read_only(context) -> None:
    ensure_topology(context)
    space(context, "one", authorities=("a",))
    space(context, "two", authorities=("b",))


@when("both spaces acquire their affected writable closures")
@when("both spaces atomically acquire their closures")
def lock_two_spaces(context) -> None:
    context.results = (context.system.lock("one"), context.system.lock("two"))


@then("neither acquires the shared read-only authority")
def no_shared_lease(context) -> None:
    assert "shared" not in {
        item.authority_id for item in context.system.snapshot().leases
    }


@then("the read-only overlap does not conflict")
def read_only_no_conflict(context) -> None:
    assert all(result.outcome == "success" for result in context.results)


@given("the repo 1 root authority is unleased")
def root_unleased(context) -> None:
    ensure_topology(context)


@given("one space affects child A")
def one_affects_a(context) -> None:
    space(context, "one", authorities=("a",))


@given("another space affects child B")
def another_affects_b(context) -> None:
    space(context, "two", authorities=("b",))


@then("both acquisitions succeed")
def acquisitions_succeed(context) -> None:
    assert [result.outcome for result in context.results] == ["success", "success"]


@then("neither space holds the root or its sibling authority")
def siblings_hold_exact(context) -> None:
    leases = {
        (item.owner_id, item.authority_id) for item in context.system.snapshot().leases
    }
    assert leases == {("one", "a"), ("two", "b")}


@then("physical checkout overlap alone is not reported as a conflict")
def checkout_overlap_not_conflict(context) -> None:
    assert context.system.lockable("one").data["lockable"]


@given("one space holds the repo 1 root authority")
def root_held(context) -> None:
    ensure_topology(context)
    space(context, "owner", authorities=("root",))
    context.system.lock("owner")
    space(context, "request", authorities=("a",))


@when("another space requests child A")
def child_requested(context) -> None:
    context.result = context.system.lockable("request")


@then("lockable returns false")
def lockable_false(context) -> None:
    assert context.result.data["lockable"] is False


@then("reports the held root, requested child, hierarchical conflict, and owning space")
def hierarchy_conflict_reported(context) -> None:
    conflict = context.result.data["conflicts"][0]
    assert (
        conflict.authority_id,
        conflict.requested_authority_id,
        conflict.owner_id,
    ) == (
        "root",
        "a",
        "owner",
    )


@given("one active space holds child A and the shared repo 3 authority")
def holds_a_and_shared(context) -> None:
    ensure_topology(context)
    space(context, "one", authorities=("a", "shared"))
    context.system.lock("one")


@given("another affected closure contains child B and the same repo 3 authority")
def requests_b_and_shared(context) -> None:
    space(context, "two", authorities=("b", "shared"))


@when("the second space runs lockable")
def second_lockable(context) -> None:
    context.result = context.system.lockable("two")


@then("child B is reported as compatible")
def b_compatible(context) -> None:
    assert all(
        item.requested_authority_id != "b" for item in context.result.data["conflicts"]
    )


@then("the shared repo 3 authority is reported as the conflict")
def shared_conflict(context) -> None:
    assert {
        item.requested_authority_id for item in context.result.data["conflicts"]
    } == {"shared"}


@then("no part of the second closure is leased")
def losing_claim_unleased(context) -> None:
    assert not any(item.owner_id == "two" for item in context.system.snapshot().leases)


@given("two processes request closures containing the same logical authority")
def competing_spaces(context) -> None:
    ensure_topology(context)
    space(context, "one", authorities=("a",))
    space(context, "two", authorities=("a",))


@when("they attempt lock concurrently")
def concurrent_lock(context) -> None:
    def attempt(name: str):
        try:
            return context.system.lock(name)
        except Exception as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        context.results = tuple(pool.map(attempt, ("one", "two")))


@then("exactly one complete closure becomes locked")
def one_winner(context) -> None:
    assert sum(not isinstance(item, Exception) for item in context.results) == 1
    assert len(context.system.snapshot().leases) == 1


@then("the other request receives the winning owner and complete conflict set")
def loser_gets_owner(context) -> None:
    failure = next(item for item in context.results if isinstance(item, Exception))
    assert isinstance(failure, AuthorityConflict)
    assert failure.details[0].owner_id in {"one", "two"}


@then("no partial losing lease remains")
def no_partial_lease(context) -> None:
    owners = {item.owner_id for item in context.system.snapshot().leases}
    assert len(owners) == 1


@given("another space holds an affected logical authority")
def another_holds_authority(context) -> None:
    ensure_topology(context)
    space(context, "owner", authorities=("a",))
    context.system.lock("owner")
    space(context, "request", authorities=("a",))


@when("the requesting space substitutes a different worktree of the same repository")
def substitute_worktree(context) -> None:
    source = context.system.git.inspect(context.repos["repo-1"])
    from openlease.utils.git_adapter import WorktreeRequest

    context.substitute = context.system.git.create_worktree(
        source,
        WorktreeRequest(context.root / "substitute", "substitute", source.head),
    )
    assert (
        context.system.resolve_authority(context.substitute.root, "A/openspec") == "a"
    )
    context.result = context.system.lockable("request")


@then("lockable remains false for the same authority")
@then("lockable remains false for that authority")
def same_authority_blocked(context) -> None:
    assert context.result.data["lockable"] is False
    assert context.result.data["conflicts"][0].authority_id == "a"


@given("a selected space already holds the exact accepted affected closure")
def exact_lock_held(context) -> None:
    ensure_topology(context)
    space(context, "selected", authorities=("a",))
    context.first = context.system.lock("selected")
    context.before = context.system.snapshot()


@when("the owner repeats lock")
def repeat_lock(context) -> None:
    context.result = context.system.lock("selected")


@then("OpenLease returns the existing structured result")
def noop_result(context) -> None:
    assert context.result.outcome == "compatible_noop"
    assert context.result.data == context.first.data


@then("does not replace identity, starting commits, leases, or projection")
def no_lock_replacement(context) -> None:
    assert context.system.snapshot() == context.before


@given("a space holds only child A")
def holds_only_a(context) -> None:
    ensure_topology(context)
    space(context, "selected", authorities=("a",))
    context.system.lock("selected")
    context.selected = "selected"


@given("its branch changes an OpenSpec file under child B")
def change_child_b(context) -> None:
    target = context.repos["repo-1"] / "B" / "openspec" / "spec.md"
    target.parent.mkdir(parents=True)
    target.write_text("outside boundary", encoding="utf-8")


@when("the owner releases or reconciles the space")
def release_with_boundary(context) -> None:
    capture(context, lambda: context.system.release("selected"))


@then("OpenLease reports the child B path outside the held boundary")
def boundary_violation_reported(context) -> None:
    assert isinstance(context.error, InvalidRequest)
    assert context.error.details.violations[0].authority_id == "b"


@then("does not represent the cohort as collision-safe")
def still_locked_after_boundary(context) -> None:
    assert (
        next(
            item
            for item in context.system.snapshot().spaces
            if item.identifier == "selected"
        ).status
        == "locked"
    )


@given("child A is lockable while child B work uses the canonical repo 1 checkout")
def isolate_setup(context) -> None:
    ensure_topology(context)
    space(context, "child-b", authorities=("b",))
    context.system.lock("child-b")
    space(context, "child-a", authorities=("a",))
    context.before_b = context.system.status("child-b").data["spaces"][0]


@when("the owner isolates the child A space with a successor name")
def isolate_a(context) -> None:
    context.result = context.system.isolate("child-a", "successor")
    context.selected = "successor"


@then("OpenLease creates one repo 1 worktree for the affected child A claim")
def one_repo1_generated(context) -> None:
    generated = [item for item in context.result.data.members if item.generated]
    assert [item.repository_id for item in generated] == ["repo-1"]
    assert Path(generated[0].effective_path).exists()


@then("atomically locks child A in the successor")
def successor_locks_a(context) -> None:
    assert {
        (item.owner_id, item.authority_id) for item in context.system.snapshot().leases
    } >= {("successor", "a")}


@then("leaves child B's space and checkout unchanged")
def b_unchanged(context) -> None:
    after = context.system.status("child-b").data["spaces"][0]
    assert after == context.before_b


@given("repo 1, repo 2, and repo 3 are associated")
def associated_for_defer(context) -> None:
    ensure_topology(context)
    space(context, "request")
    context.selected = "request"


@given("the affected closure contains only child A in repo 1")
def deferred_affect_a(context) -> None:
    context.system.set_affected("request", authority_ids=("a",))


@given("the selected space is non-lockable")
def make_selected_nonlockable(context) -> None:
    if not any(
        item.identifier == "blocker" for item in context.system.snapshot().spaces
    ):
        requested = context.system.plan(context.selected).data.held_authorities
        space(context, "blocker", authorities=(requested[0],))
        context.system.lock("blocker")
    assert context.system.lockable(context.selected).data["lockable"] is False


@when("the owner defers it with an unused successor name")
def defer_unused(context) -> None:
    context.result = context.system.defer(context.selected, "successor")
    context.selected = "successor"


@then("OpenLease creates one branch and linked worktree for repo 1")
def generated_repo1(context) -> None:
    one_repo1_generated(context)
    assert context.result.data.members[0].branch == "successor"


@then("records repo 2 and repo 3 as pinned context without generated worktrees")
def pinned_repo2_repo3(context) -> None:
    pinned = {
        item.repository_id for item in context.result.data.members if not item.generated
    }
    assert pinned == {"repo-2", "repo-3"}


@then("publishes a distinct deferred successor space with no leases")
def deferred_no_lease(context) -> None:
    assert context.result.data.status == "deferred"
    assert not any(
        item.owner_id == "successor" for item in context.system.snapshot().leases
    )


@given("affected repo 2 requires writable use of the authority hosted by repo 3")
def external_defer_setup(context) -> None:
    ensure_topology(context)
    space(context, "request", repositories=("repo-2",))
    context.selected = "request"


@when("the owner defers it")
def defer_default(context) -> None:
    context.source_snapshot = context.system.snapshot()
    context.result = context.system.defer(context.selected, "successor")
    context.selected = "successor"


@then("OpenLease creates affected worktrees for repo 2 and repo 3")
def external_worktrees(context) -> None:
    assert {
        item.repository_id for item in context.result.data.members if item.generated
    } == {"repo-2", "repo-3"}


@then("wires repo 2 to the authority path in the repo 3 successor worktree")
def external_authority_remapped(context) -> None:
    repo3 = member(context, "successor", "repo-3")
    assert context.system.authority_path("successor", "shared") == (
        Path(repo3.effective_path) / "openspec"
    )


@then("leaves the source space and shared OpenSpec registration unchanged")
def source_and_registration_unchanged(context) -> None:
    source = next(
        item
        for item in context.system.snapshot().spaces
        if item.identifier == "request"
    )
    prior = next(
        item for item in context.source_snapshot.spaces if item.identifier == "request"
    )
    assert source == prior
    assert context.system.snapshot().authorities == context.source_snapshot.authorities


@given("a non-lockable affected repository needs a successor worktree")
def branch_selection_setup(context) -> None:
    ensure_topology(context)
    space(context, "blocker", authorities=("a",))
    context.system.lock("blocker")
    space(context, "request", authorities=("a",))
    context.selected = "request"


@when("the owner defers it with {branch_selection}")
def defer_branch_selection(context, branch_selection: str) -> None:
    repo = context.repos["repo-1"]
    head = git(repo, "rev-parse", "HEAD")
    if branch_selection == "no branch":
        selection = BranchSelection()
        context.expected_branch = "successor"
    elif branch_selection == "an available local":
        git(repo, "branch", "available", head)
        selection = BranchSelection("local", "available")
        context.expected_branch = "available"
    else:
        git(repo, "update-ref", "refs/remotes/origin/topic", head)
        selection = BranchSelection("remote", "refs/remotes/origin/topic")
        context.expected_branch = "topic"
    context.result = context.system.defer(
        "request", "successor", branches={"repo-1": selection}
    )


@then("OpenLease creates the worktree using {branch_result}")
def branch_result(context, branch_result: str) -> None:
    del branch_result
    assert member(context, "successor", "repo-1").branch == context.expected_branch


@given("one affected repository's derived path or selected branch is unavailable")
def destination_collision(context) -> None:
    branch_selection_setup(context)
    collision = context.root / "worktrees" / "successor" / "repo-1-successor"
    collision.mkdir(parents=True)
    context.source_before = context.system.status("request").data["spaces"][0]


@when("the owner defers the complete affected closure")
def defer_collision(context) -> None:
    capture(context, lambda: context.system.defer("request", "successor"))


@then("OpenLease does not overwrite or reuse the collision")
def collision_preserved(context) -> None:
    assert isinstance(context.error, PreparationFailed)
    assert (context.root / "worktrees" / "successor" / "repo-1-successor").exists()


@then("leaves the source space unchanged")
def source_unchanged(context) -> None:
    assert context.system.status("request").data["spaces"][0] == context.source_before


@then("publishes no usable deferred successor")
def no_usable_successor(context) -> None:
    successor = next(
        (
            item
            for item in context.system.snapshot().spaces
            if item.identifier == "successor"
        ),
        None,
    )
    assert successor is None or successor.status == "preparation_failed"


@given("deferral created one affected worktree before a later repository failed")
def partial_preparation(context) -> None:
    ensure_topology(context)
    space(context, "blocker", authorities=("shared",))
    context.system.lock("blocker")
    space(context, "request", repositories=("repo-2",))
    delegate = context.system.git

    class FailSecondCreation:
        def __init__(self) -> None:
            self.created = 0

        def __getattr__(self, name):
            return getattr(delegate, name)

        def create_worktree(self, source, request):
            self.created += 1
            if self.created == 2:
                raise RuntimeError("injected later repository failure")
            return delegate.create_worktree(source, request)

    context.system.git = FailSecondCreation()
    capture(context, lambda: context.system.defer("request", "successor"))
    assert isinstance(context.error, PreparationFailed)


@given("OpenLease cannot prove that every created artifact is unchanged and clean")
def make_prepared_artifact_uncertain(context) -> None:
    successor = next(
        item
        for item in context.system.snapshot().spaces
        if item.identifier == "successor"
    )
    if successor.members:
        (Path(successor.members[0].effective_path) / "dirty.txt").write_text(
            "dirty", encoding="utf-8"
        )


@when("preparation recovery runs")
def preparation_recovery(context) -> None:
    context.result = context.system.rollback_preparation("successor")


@then("OpenLease preserves the uncertain artifacts")
def uncertain_retained(context) -> None:
    assert context.result.data["retained"]


@then("records a non-writable preparation-failed successor")
def prep_failed_record(context) -> None:
    successor = next(
        item
        for item in context.system.snapshot().spaces
        if item.identifier == "successor"
    )
    assert successor.status == "preparation_failed"
    assert not any(
        item.owner_id == "successor" for item in context.system.snapshot().leases
    )


@then("supports explicit resume or rollback")
def preparation_controls(context) -> None:
    result = context.system.resume_preparation("successor")
    assert "resumable" in result.data


@given("a deferred successor uses different worktree paths from its blocker")
def deferred_from_blocker(context) -> None:
    blocked_successor(context)
    assert (
        member(context, "successor", "repo-1").effective_path
        != member(context, "blocker", "repo-1").effective_path
    )


@when("the blocker still owns one requested logical authority")
def blocker_still_owns(context) -> None:
    context.result = context.system.lockable("successor")


@then("the successor cannot perform OpenLease-governed protected mutation")
def deferred_cannot_lock(context) -> None:
    capture(context, lambda: context.system.lock("successor"))
    assert isinstance(context.error, AuthorityConflict)


@given(
    "a blocker releases before its authority changes receive an integrated, "
    "abandoned, or superseded disposition"
)
def blocker_released_without_disposition(context) -> None:
    blocked_successor(context)
    context.system.release("blocker")


@when("the deferred successor runs lockable")
def deferred_lockable(context) -> None:
    context.result = context.system.lockable("successor")


@then("promotion remains unavailable")
def promotion_unavailable(context) -> None:
    assert context.result.data["lockable"] is False


@then("status reports the unresolved blocker handoff")
def unresolved_handoff(context) -> None:
    assert "blocker handoff unresolved" in context.result.data["promotion_issues"][0]


@given("every blocker has an acceptable disposition")
def acceptable_blocker(context) -> None:
    blocked_successor(context)
    context.system.release("blocker")
    context.system.set_handoff_disposition("blocker", "abandoned")


@given("the clean successor baselines include every integrated blocker commit")
def clean_successor(context) -> None:
    assert not context.system.git.inspect(
        Path(member(context, "successor", "repo-1").effective_path)
    ).dirty


@given("the graph and lease generations still match")
def generations_match(context) -> None:
    successor = next(
        item
        for item in context.system.snapshot().spaces
        if item.identifier == "successor"
    )
    assert successor.graph_generation == context.system.snapshot().graph_generation


@when("the owner explicitly runs lock")
def explicit_lock(context) -> None:
    context.result = context.system.lock("successor")


@then("OpenLease atomically acquires the complete affected closure")
def successor_acquires(context) -> None:
    assert {item.authority_id for item in context.system.snapshot().leases} == {"a"}


@then("records the successor as locked")
def successor_locked(context) -> None:
    assert context.result.data.status == "locked"


@given("an unleased deferred worktree contains user changes")
def dirty_deferred(context) -> None:
    blocked_successor(context)
    context.system.release("blocker")
    context.system.set_handoff_disposition("blocker", "abandoned")
    path = Path(member(context, "successor", "repo-1").effective_path) / "dirty.txt"
    path.write_text("user work", encoding="utf-8")
    context.dirty_path = path


@when("the owner attempts lock")
def attempt_promotion(context) -> None:
    capture(context, lambda: context.system.lock("successor"))


@then("OpenLease identifies the dirty member and rejects promotion")
def dirty_promotion_rejected(context) -> None:
    assert isinstance(context.error, InvalidRequest)
    assert "dirty" in str(context.error.details)


@then("preserves all work")
def dirty_work_preserved(context) -> None:
    assert context.dirty_path.read_text(encoding="utf-8") == "user work"


@given("a deferred successor pins unrelated repo 2 context")
def deferred_with_pinned_repo2(context) -> None:
    blocked_successor(context)
    context.system.release("blocker")
    context.system.set_handoff_disposition("blocker", "abandoned")
    assert not member(context, "successor", "repo-2").generated


@given("the pinned repo 2 checkout moves from its recorded commit")
def move_pinned_repo2(context) -> None:
    path = context.repos["repo-2"]
    (path / "drift.txt").write_text("drift", encoding="utf-8")
    git(path, "add", "drift.txt")
    git(path, "commit", "--quiet", "-m", "move pinned context")


@then("status reports the pinned repo 2 drift")
def pinned_drift_reported(context) -> None:
    assert "pinned member drifted: repo-2" in context.result.data["promotion_issues"]


@given("a locked successor has generated branches and worktrees")
def locked_successor(context) -> None:
    blocked_successor(context, locked=True)
    assert any(
        item.generated
        for item in context.system.status("successor").data["spaces"][0].members
    )


@when("the owner releases it")
def release_successor(context) -> None:
    context.before_members = (
        context.system.status("successor").data["spaces"][0].members
    )
    context.result = context.system.release("successor")


@then("OpenLease removes its leases and owned projection")
def release_removes_owned(context) -> None:
    assert not any(
        item.owner_id == "successor" for item in context.system.snapshot().leases
    )
    assert "openlease-successor" not in context.openspec.worksets


@then("preserves every generated affected branch and worktree")
def generated_work_preserved(context) -> None:
    for item in context.before_members:
        if item.generated:
            assert Path(item.effective_path).exists()
            assert (
                git(Path(item.effective_path), "branch", "--show-current")
                == item.branch
            )


@then("records each generated member as pending reconciliation")
def pending_debt(context) -> None:
    generated = {
        item.repository_id for item in context.before_members if item.generated
    }
    pending = {
        item.repository_id
        for item in context.system.snapshot().reconciliations
        if item.space_id == "successor" and item.status == "pending"
    }
    assert pending == generated


def released_with_change(context, *, external: bool = False) -> None:
    blocked_successor(context, external=external, locked=True)
    for item in context.system.status("successor").data["spaces"][0].members:
        if item.generated:
            path = Path(item.effective_path)
            (path / f"{item.repository_id}.txt").write_text("change", encoding="utf-8")
            git(path, "add", ".")
            git(path, "commit", "--quiet", "-m", f"change {item.repository_id}")
    context.system.release("successor")


@given("a released successor has pending generated branches")
def released_pending(context) -> None:
    released_with_change(context)


@when(
    "the owner supplies an ordered destination and merge-or-rebase strategy "
    "for each selected branch"
)
def plan_merge_path(context) -> None:
    current = context.system.status("successor").data["spaces"][0]
    context.dest_heads = {
        item.repository_id: git(Path(item.source_path), "rev-parse", "HEAD")
        for item in current.members
        if item.generated
    }
    selections = tuple(
        ReconcileSelection(
            item.repository_id,
            git(Path(item.source_path), "branch", "--show-current"),
            IntegrationStrategy.MERGE,
        )
        for item in current.members
        if item.generated
    )
    context.result = context.system.reconcile_plan("successor", selections)


@then(
    "reconcile plans every source-to-destination leg against the current "
    "destination commits"
)
def all_legs_planned(context) -> None:
    for leg in context.result.data["legs"]:
        assert (
            leg["preview"].destination_commit
            == context.dest_heads[leg["repository_id"]]
        )


@then(
    "reports divergence, dirty worktrees, missing branches, likely textual "
    "conflicts, and verification"
)
def reconciliation_evidence(context) -> None:
    leg = context.result.data["legs"][0]
    assert hasattr(leg["preview"], "ahead")
    assert "dirty" in leg
    assert hasattr(leg["preview"], "likely_conflicts")
    assert context.result.data["verification"]["cohort"]


@then("does not mutate Git during planning")
def planning_no_mutation(context) -> None:
    current = context.system.status("successor").data["spaces"][0]
    for item in current.members:
        if item.generated:
            assert (
                git(Path(item.source_path), "rev-parse", "HEAD")
                == context.dest_heads[item.repository_id]
            )


@given("repo 2 depends on the affected authority hosted by repo 3")
def external_released(context) -> None:
    released_with_change(context, external=True)


@when("the owner plans reconciliation without overriding dependency order")
def plan_default_order(context) -> None:
    current = context.system.status("successor").data["spaces"][0]
    selections = tuple(
        ReconcileSelection(
            item.repository_id,
            git(Path(item.source_path), "branch", "--show-current"),
            IntegrationStrategy.MERGE,
        )
        for item in current.members
        if item.generated
    )
    context.result = context.system.reconcile_plan("successor", selections)


@then("the visible plan orders repo 3 before repo 2")
def provider_first(context) -> None:
    assert context.result.data["default_order"] == ("repo-3", "repo-2")


@then("the owner may provide a different complete order before applying it")
def explicit_order_supported(context) -> None:
    assert len(context.result.data["legs"]) == 2


@given("an accepted merge path spans several affected repositories")
def conflicting_merge_path(context) -> None:
    blocked_successor(context, external=True, locked=True)
    current = context.system.status("successor").data["spaces"][0]
    for item in current.members:
        if not item.generated:
            continue
        source = Path(item.effective_path)
        destination = Path(item.source_path)
        (source / "conflict.txt").write_text("source", encoding="utf-8")
        git(source, "add", "conflict.txt")
        git(source, "commit", "--quiet", "-m", "source conflict")
        (destination / "conflict.txt").write_text("destination", encoding="utf-8")
        git(destination, "add", "conflict.txt")
        git(destination, "commit", "--quiet", "-m", "destination conflict")
    context.system.release("successor")
    context.selections = tuple(
        ReconcileSelection(
            item.repository_id,
            git(Path(item.source_path), "branch", "--show-current"),
            IntegrationStrategy.MERGE,
        )
        for item in current.members
        if item.generated
    )


@when("one reconciliation leg encounters a Git conflict")
def apply_conflicting_path(context) -> None:
    capture(
        context,
        lambda: context.system.reconcile_apply("successor", context.selections),
    )


@then("OpenLease preserves that conflict for explicit resolution")
def conflict_preserved(context) -> None:
    assert context.error is not None
    repo3 = member(context, "successor", "repo-3")
    assert (Path(repo3.source_path) / ".git" / "MERGE_HEAD").exists()


@then("leaves every later repository untouched and pending")
def later_pending(context) -> None:
    pending = {
        item.repository_id
        for item in context.system.snapshot().reconciliations
        if item.space_id == "successor" and item.status == "pending"
    }
    assert "repo-2" in pending


@then("retains the complete cohort record")
def cohort_retained(context) -> None:
    assert (
        len(
            [
                item
                for item in context.system.snapshot().reconciliations
                if item.space_id == "successor"
            ]
        )
        == 2
    )


@given("a released space has generated affected members")
def released_generated(context) -> None:
    blocked_successor(context, locked=True)
    context.system.release("successor")


@when(
    "any branch lacks a reconciled or abandoned disposition or any generated "
    "worktree remains"
)
def finalize_too_early(context) -> None:
    capture(context, lambda: context.system.finalize("successor"))


@then("finalization is rejected with the outstanding members")
def finalization_rejected(context) -> None:
    assert isinstance(context.error, InvalidRequest)
    assert context.error.details["pending"]
    assert context.error.details["worktrees"]


@when("every branch has a disposition and every owned worktree is gone")
def dispose_all(context) -> None:
    current = context.system.status("successor").data["spaces"][0]
    for item in current.members:
        if item.generated:
            context.system.abandon_member("successor", item.repository_id)
            context.system.cleanup_worktree("successor", item.repository_id)


@then("the owner can finalize the released space record")
def finalize_released(context) -> None:
    assert context.system.finalize("successor").data.status == "finalized"


@given("a locked space was abandoned after terminal loss")
def abandoned_locked_space(context) -> None:
    blocked_successor(context, locked=True)


@given("its generated worktrees may contain dirty files")
def dirty_locked_worktree(context) -> None:
    generated = next(
        item
        for item in context.system.status("successor").data["spaces"][0].members
        if item.generated
    )
    context.dirty_path = Path(generated.effective_path) / "dirty.txt"
    context.dirty_path.write_text("preserve", encoding="utf-8")


@when("the owner explicitly force-recovers that space")
def force_recover(context) -> None:
    context.result = context.system.recover("successor", force=True)


@then("OpenLease releases only its owned machine-local leases and intact projection")
def recovery_releases_owned(context) -> None:
    assert not any(
        item.owner_id == "successor" for item in context.system.snapshot().leases
    )
    assert "openlease-successor" not in context.openspec.worksets


@then("preserves its branches, worktrees, dirty files, and reconciliation records")
def recovery_preserves(context) -> None:
    assert context.dirty_path.exists()
    assert any(
        item.space_id == "successor"
        for item in context.system.snapshot().reconciliations
    )


@given("OpenLease is installed without its CLI extra")
def base_install(context) -> None:
    context.import_script = (
        "import sys; import openlease; assert 'typer' not in sys.modules"
    )


@when("a Python consumer imports the public package")
def import_public(context) -> None:
    context.process = subprocess.run(
        (sys.executable, "-c", context.import_script),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@then("the import succeeds without importing Typer")
def import_without_typer(context) -> None:
    assert context.process.returncode == 0, context.process.stderr


@then("the complete public lifecycle is available through the library")
def lifecycle_exported(context) -> None:
    from openlease import OpenLease as ExportedOpenLease

    assert ExportedOpenLease is OpenLease
    assert all(
        hasattr(ExportedOpenLease, name)
        for name in ("lock", "defer", "reconcile_apply")
    )


@given("the optional CLI extra is installed")
def cli_installed(context) -> None:
    context.runner = CliRunner()


@when("a user runs a topology, space, lease, defer, or reconcile command")
def cli_runs_commands(context) -> None:
    ensure_topology(context)
    result = context.runner.invoke(
        app,
        [
            "--state-root",
            str(context.root / "state"),
            "space",
            "create",
            "cli-space",
        ],
    )
    assert result.exit_code == 0
    context.result = context.system.status("cli-space")


@then("the command delegates to the same public library lifecycle")
def cli_shared_lifecycle(context) -> None:
    assert context.result.data["spaces"][0].identifier == "cli-space"


@then("no separate CLI-only state transition occurs")
def no_cli_state(context) -> None:
    assert not (context.root / "cli-state").exists()


@given("a valid noninteractive command")
def valid_cli_command(context) -> None:
    context.runner = CliRunner()
    context.cli_args = [
        "--state-root",
        str(context.root / "state"),
        "--json",
        "status",
    ]


@when("the user requests JSON output")
def request_json(context) -> None:
    context.cli_result = context.runner.invoke(app, context.cli_args)


@then("standard output contains one structured result envelope")
def one_json_envelope(context) -> None:
    assert context.cli_result.exit_code == 0
    context.envelope = json.loads(context.cli_result.stdout)
    assert context.envelope["ok"] is True
    assert context.cli_result.stdout.count("\n") == 1


@then("diagnostics are absent from standard output")
def no_stdout_diagnostics(context) -> None:
    assert context.cli_result.stderr == ""


@given("a command produces {outcome}")
def command_outcome(context, outcome: str) -> None:
    context.runner = CliRunner()
    state = context.root / "outcome-state"
    lifecycle = OpenLease(state, openspec=context.openspec)
    args = ["--state-root", str(state)]
    if outcome == "success":
        context.cli_args = [*args, "status"]
    elif outcome == "invalid request":
        lifecycle.create_space("request")
        context.cli_args = [*args, "--space", "request", "lock"]
    else:
        context.system = lifecycle
        context.root = context.root
        ensure_repositories(context)
        ensure_topology(context)
        if outcome == "compatible no-op":
            space(context, "request", authorities=("a",))
            lifecycle.lock("request")
            context.cli_args = [*args, "--space", "request", "lock"]
        elif outcome == "authority conflict":
            space(context, "owner", authorities=("a",))
            lifecycle.lock("owner")
            space(context, "request", authorities=("a",))
            context.cli_args = [*args, "--space", "request", "lock"]
        else:
            space(context, "request", authorities=("a",))
            lifecycle.lock("request")
            lifecycle.open("request")
            owned = context.openspec.worksets["openlease-request"]
            context.openspec.worksets[owned.name] = OpenSpecWorkset(owned.name, ())
            context.cli_args = [*args, "--space", "request", "release"]


@when("the command exits")
def command_exits(context) -> None:
    context.cli_result = context.runner.invoke(app, context.cli_args)


@then("its process status is {status:d}")
def process_status(context, status: int) -> None:
    assert context.cli_result.exit_code == status


@then("expected domain failures show no implementation traceback")
def no_domain_traceback(context) -> None:
    assert "Traceback" not in context.cli_result.stderr


@given("isolated automation selects an explicit OpenLease state root and worktree base")
def explicit_roots(context) -> None:
    context.explicit_state = context.root / "explicit-state"
    context.explicit_worktrees = context.root / "explicit-worktrees"
    context.system = OpenLease(
        context.explicit_state,
        worktree_base=context.explicit_worktrees,
        openspec=context.openspec,
    )


@when("it runs the public lifecycle")
def run_explicit_lifecycle(context) -> None:
    ensure_topology(context)
    space(context, "blocker", authorities=("a",))
    context.system.lock("blocker")
    space(context, "request", authorities=("a",))
    context.result = context.system.defer("request", "successor")


@then("all OpenLease state and generated destinations remain beneath those selections")
def paths_bounded(context) -> None:
    assert (context.explicit_state / "state.json").exists(), context.explicit_state
    for item in context.result.data.members:
        if item.generated:
            assert os.path.samefile(
                Path(item.effective_path).parent.parent,
                context.system.worktree_base,
            )


@then("the same identity, collision, ownership, and recovery rules apply")
def same_rules_apply(context) -> None:
    assert context.system.lockable("successor").data["lockable"] is False
    assert context.result.data.projection_fingerprint
    assert context.system.recover("successor", force=True).data.status == "released"


@given("two processes plan against one state generation")
def same_generation(context) -> None:
    ensure_topology(context)
    space(context, "selected")
    context.generation = context.system.snapshot().generation


@when("both attempt a mutating lifecycle operation")
def competing_mutations(context) -> None:
    second = OpenLease(
        context.root / "state",
        worktree_base=context.root / "worktrees",
        openspec=context.openspec,
    )

    def mutate(system: OpenLease, repository: str):
        try:
            return system.associate(
                "selected", (repository,), expected_generation=context.generation
            )
        except Exception as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        context.results = tuple(
            pool.map(
                lambda pair: mutate(*pair),
                ((context.system, "repo-1"), (second, "repo-2")),
            )
        )


@then("OpenLease serializes the mutations")
def mutations_serialized(context) -> None:
    assert sum(not isinstance(item, Exception) for item in context.results) == 1


@then("only a process whose observed generation is current may commit its result")
def only_current_commits(context) -> None:
    assert sum(isinstance(item, InvalidRequest) for item in context.results) == 1
