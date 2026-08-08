from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from behave import given, then, when

from features.support.openlease_support import (
    capture,
    ensure_repositories,
    ensure_topology,
    space,
)
from openlease import (
    AuthorityConflict,
    InvalidRequest,
)


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


@then("no lease or projection is added")
def no_lease_or_projection(context) -> None:
    assert context.system.snapshot().leases == ()
    assert context.openspec.worksets == {}


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
