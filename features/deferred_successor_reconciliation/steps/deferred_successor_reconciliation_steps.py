from __future__ import annotations

from pathlib import Path

from behave import given, then, when

from features.support.openlease_support import (
    blocked_successor,
    capture,
    ensure_topology,
    git,
    member,
    new_system,
    space,
)
from openlease import (
    AuthorityConflict,
    BranchSelection,
    CallbackEvent,
    CallbackMode,
    CallbackSelection,
    ExtensionCallback,
    ExtensionManifest,
    ExtensionOperation,
    ExtensionRegistration,
    HandlerStatus,
    InvalidRequest,
    PreparationFailed,
    ReconcileSelection,
)
from openlease.utils.git_adapter import IntegrationStrategy


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


@then(
    "OpenLease creates one adjacent repo 1-olease-1 worktree for the affected "
    "child A claim"
)
def one_repo1_generated(context) -> None:
    generated = [item for item in context.result.data.members if item.generated]
    assert [item.repository_id for item in generated] == ["repo-1"]
    destination = Path(generated[0].effective_path)
    assert destination == (context.repos["repo-1"].parent / "repo-1-olease-1").resolve()
    assert destination.exists()


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


@then("OpenLease creates one adjacent repo 1-olease-1 branch worktree")
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


@then("places each generated worktree beside its own source repository")
def external_worktrees_are_local(context) -> None:
    generated = {
        item.repository_id: Path(item.effective_path)
        for item in context.result.data.members
        if item.generated
    }
    assert generated == {
        "repo-2": (context.repos["repo-2"].parent / "repo-2-olease-1").resolve(),
        "repo-3": (context.repos["repo-3"].parent / "repo-3-olease-1").resolve(),
    }


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
        context.expected_upstream = None
    elif branch_selection == "an available local":
        git(repo, "branch", "available", head)
        selection = BranchSelection("local", "available")
        context.expected_branch = "available"
        context.expected_upstream = None
    else:
        git(repo, "update-ref", "refs/remotes/origin/topic", head)
        selection = BranchSelection("remote", "refs/remotes/origin/topic")
        context.expected_branch = "topic"
        context.expected_upstream = None
    context.result = context.system.defer(
        "request", "successor", branches={"repo-1": selection}
    )


@then("OpenLease creates the worktree using {branch_result}")
def branch_result(context, branch_result: str) -> None:
    del branch_result
    generated = member(context, "successor", "repo-1")
    assert generated.branch == context.expected_branch
    assert generated.upstream == context.expected_upstream


@given("repo 1-olease-1 is occupied by an unmanaged directory")
def occupied_first_destination(context) -> None:
    branch_selection_setup(context)
    context.collision = context.repos["repo-1"].parent / "repo-1-olease-1"
    context.collision.mkdir(parents=True)
    context.marker = context.collision / "unmanaged.txt"
    context.marker.write_text("unmanaged", encoding="utf-8")
    context.source_before = context.system.status("request").data["spaces"][0]


@when("the owner defers the affected repo 1 claim")
def defer_affected_repo1(context) -> None:
    context.result = context.system.defer("request", "successor")


@then("OpenLease leaves repo 1-olease-1 unchanged")
def unmanaged_destination_unchanged(context) -> None:
    assert context.marker.read_text(encoding="utf-8") == "unmanaged"


@then("creates and records repo 1-olease-2 as the managed worktree")
def second_destination_created(context) -> None:
    generated = member(context, "successor", "repo-1")
    assert (
        Path(generated.effective_path)
        == (context.repos["repo-1"].parent / "repo-1-olease-2").resolve()
    )
    assert Path(generated.effective_path).exists()


@given("an explicit worktree base and an affected repo 1 claim")
def explicit_base_setup(context) -> None:
    context.explicit_base = context.root / "automation-worktrees"
    context.system = new_system(context, worktree_base=context.explicit_base)
    branch_selection_setup(context)


@then("OpenLease creates repo 1-olease-1 beneath the explicit base")
def explicit_base_destination(context) -> None:
    generated = member(context, "successor", "repo-1")
    assert (
        Path(generated.effective_path)
        == (context.explicit_base / "repo-1-olease-1").resolve()
    )
    assert Path(generated.effective_path).exists()


@then("keeps machine-local state outside that generated worktree")
def state_outside_generated_worktree(context) -> None:
    generated = Path(member(context, "successor", "repo-1").effective_path)
    assert not context.system.state_root.is_relative_to(generated)


@given("the complete affected closure has reserved its exact worktree destinations")
def install_late_destination_race(context) -> None:
    ensure_topology(context)
    space(context, "blocker", authorities=("shared",))
    context.system.lock("blocker")
    space(context, "request", repositories=("repo-2",))
    context.source_before = context.system.status("request").data["spaces"][0]
    delegate = context.system.git

    class OccupyReservedDestination:
        def __getattr__(self, name):
            return getattr(delegate, name)

        def create_worktree(self, source, request):
            successor = next(
                item
                for item in context.system.snapshot().spaces
                if item.identifier == "successor"
            )
            assert successor.status == "preparing"
            context.reserved_paths = tuple(
                Path(item.effective_path)
                for item in successor.members
                if item.generated
            )
            assert request.destination in context.reserved_paths
            if context.occupy_reserved_destination:
                request.destination.mkdir(parents=True)
                context.race_marker = request.destination / "external.txt"
                context.race_marker.write_text("external", encoding="utf-8")
                context.occupy_reserved_destination = False
            return delegate.create_worktree(source, request)

    context.system.git = OccupyReservedDestination()


@given("an external process occupies one destination before Git creation")
def enable_late_destination_race(context) -> None:
    context.occupy_reserved_destination = True


@when("the owner defers the complete affected closure")
def defer_collision(context) -> None:
    capture(context, lambda: context.system.defer("request", "successor"))


@then("OpenLease does not overwrite or adopt the collision")
def collision_preserved(context) -> None:
    assert isinstance(context.error, PreparationFailed)
    assert context.race_marker.read_text(encoding="utf-8") == "external"


@then("leaves the source space unchanged")
def source_unchanged(context) -> None:
    assert context.system.status("request").data["spaces"][0] == context.source_before


@then("records the reserved paths in a non-writable preparation-failed successor")
def reserved_paths_remain_journaled(context) -> None:
    successor = next(
        item
        for item in context.system.snapshot().spaces
        if item.identifier == "successor"
    )
    assert successor.status == "preparation_failed"
    assert (
        tuple(Path(item.effective_path) for item in successor.members if item.generated)
        == context.reserved_paths
    )


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


@then("successor lockable remains false for that authority")
def successor_same_authority_blocked(context) -> None:
    assert context.result.data["lockable"] is False
    assert context.result.data["conflicts"][0].authority_id == "a"


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


@given(
    "an existing successor records a generated worktree beneath the former "
    "centralized base"
)
def existing_centralized_successor(context) -> None:
    context.former_base = context.root / "former-centralized-worktrees"
    context.system = new_system(context, worktree_base=context.former_base)
    blocked_successor(context, locked=True)
    context.system.release("successor")
    context.recorded_member = member(context, "successor", "repo-1")
    context.recorded_path = Path(context.recorded_member.effective_path)
    assert context.recorded_path.is_relative_to(context.former_base.resolve())
    context.system.worktree_base = None


@when("the owner inspects and reconciles that generated member")
def inspect_and_plan_recorded_member(context) -> None:
    inspected = context.system.status("successor").data["spaces"][0]
    selected = next(
        item
        for item in inspected.members
        if item.repository_id == context.recorded_member.repository_id
    )
    context.inspected_path = Path(selected.effective_path)
    destination_branch = git(Path(selected.source_path), "branch", "--show-current")
    context.system.reconcile_plan(
        "successor",
        (
            ReconcileSelection(
                selected.repository_id,
                destination_branch,
                IntegrationStrategy.MERGE,
            ),
        ),
    )


@then("OpenLease continues using the exact recorded worktree path")
def exact_recorded_path_retained(context) -> None:
    assert context.inspected_path == context.recorded_path
    assert context.recorded_path.exists()


@then("does not move or rename the existing worktree")
def recorded_worktree_not_moved(context) -> None:
    adjacent = context.repos["repo-1"].parent / "repo-1-olease-1"
    assert not adjacent.exists()


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
    "conflicts, intrinsic safety, and exact callback selections"
)
def reconciliation_evidence(context) -> None:
    leg = context.result.data["legs"][0]
    assert hasattr(leg["preview"], "ahead")
    assert "dirty" in leg
    assert hasattr(leg["preview"], "likely_conflicts")
    assert context.result.data["callbacks"] == ()
    assert context.result.data["callback_evidence"]


@then("does not mutate Git during planning")
def planning_no_mutation(context) -> None:
    current = context.system.status("successor").data["spaces"][0]
    for item in current.members:
        if item.generated:
            assert (
                git(Path(item.source_path), "rev-parse", "HEAD")
                == context.dest_heads[item.repository_id]
            )


def callback_successor(context, event: CallbackEvent, *, fail: bool) -> None:
    def callback(_invocation):
        if fail:
            raise RuntimeError("callback failed")

    modes = (
        (CallbackMode.OBSERVE, CallbackMode.GATE)
        if event is CallbackEvent.RECONCILE_BEFORE_REPOSITORY
        else (CallbackMode.OBSERVE,)
    )
    registration = ExtensionRegistration(
        ExtensionManifest("zpp.behave"),
        operations=(ExtensionOperation("verify", callback),),
        callbacks=(ExtensionCallback(event, "verify", modes),),
    )
    context.system = new_system(context)
    context.system = type(context.system)(
        context.root / "state",
        openspec=context.openspec,
        extensions=(registration,),
    )
    released_with_change(context)
    current = context.system.status("successor").data["spaces"][0]
    generated = next(item for item in current.members if item.generated)
    context.repository_id = generated.repository_id
    context.destination = Path(generated.source_path)
    context.destination_head = git(context.destination, "rev-parse", "HEAD")
    context.selections = (
        ReconcileSelection(
            generated.repository_id,
            git(context.destination, "branch", "--show-current"),
            IntegrationStrategy.MERGE,
        ),
    )


@when("the owner plans reconciliation without selecting callbacks")
def plan_without_callbacks(context) -> None:
    plan_merge_path(context)


@then("no registered or configured extension operation becomes required work")
def no_callback_work(context) -> None:
    assert context.result.data["callbacks"] == ()


@then("intrinsic OpenLease Git and ownership checks remain active")
def intrinsic_checks_remain(context) -> None:
    leg = context.result.data["legs"][0]
    assert "dirty" in leg
    assert hasattr(leg["preview"], "likely_conflicts")


@given("a released successor and a selected reconciliation callback")
def given_selected_reconciliation_callback(context) -> None:
    callback_successor(context, CallbackEvent.RECONCILE_AFTER_COHORT, fail=False)
    context.callback_input = {"command": "bdd", "complete": True}
    context.callback = CallbackSelection(
        "zpp.behave",
        "verify",
        CallbackEvent.RECONCILE_AFTER_COHORT,
        CallbackMode.OBSERVE,
        input=context.callback_input,
    )


@when("the owner supplies the callback input command bdd with complete enabled")
def plan_with_explicit_callback_input(context) -> None:
    context.result = context.system.reconcile_plan(
        "successor", context.selections, (context.callback,)
    )


@then("the read-only plan reports the captured input")
def plan_reports_captured_input(context) -> None:
    assert context.result.data["callbacks"][0]["input"] == {
        "command": "bdd",
        "complete": True,
    }


@then("callback drift evidence covers that input")
def callback_evidence_covers_input(context) -> None:
    changed = CallbackSelection(
        "zpp.behave",
        "verify",
        CallbackEvent.RECONCILE_AFTER_COHORT,
        CallbackMode.OBSERVE,
        input={"command": "bdd", "complete": False},
    )
    changed_plan = context.system.reconcile_plan(
        "successor", context.selections, (changed,)
    )
    assert (
        changed_plan.data["callback_evidence"]
        != context.result.data["callback_evidence"]
    )


@then("extension configuration does not select or alter the command")
def configuration_does_not_select_callback_input(context) -> None:
    assert context.result.data["callbacks"][0]["input"]["command"] == "bdd"


@given("a released successor and a registered failing pre-repository callback")
def given_failing_pre_callback(context) -> None:
    callback_successor(context, CallbackEvent.RECONCILE_BEFORE_REPOSITORY, fail=True)


@when("the owner selects that callback as a gate and applies reconciliation")
def apply_pre_gate(context) -> None:
    callback = CallbackSelection(
        "zpp.behave",
        "verify",
        CallbackEvent.RECONCILE_BEFORE_REPOSITORY,
        CallbackMode.GATE,
        context.repository_id,
    )
    capture(
        context,
        lambda: context.system.reconcile_apply(
            "successor", context.selections, (callback,)
        ),
    )


@then("OpenLease records the failed callback outcome before Git mutation")
def failed_gate_recorded(context) -> None:
    outcomes = context.system.inspect_extension_outcomes("zpp.behave")
    assert outcomes[-1]["handler_status"] == HandlerStatus.FAILED.value
    assert git(context.destination, "rev-parse", "HEAD") == context.destination_head


@then("the repository remains pending and unintegrated")
def gate_leaves_pending(context) -> None:
    record = next(
        item
        for item in context.system.snapshot().reconciliations
        if item.space_id == "successor" and item.repository_id == context.repository_id
    )
    assert record.status == "pending"


@given("a released successor and a registered failing post-repository callback")
def given_failing_post_callback(context) -> None:
    callback_successor(context, CallbackEvent.RECONCILE_AFTER_REPOSITORY, fail=True)


@when("the owner selects that callback observationally and applies reconciliation")
def apply_post_observer(context) -> None:
    callback = CallbackSelection(
        "zpp.behave",
        "verify",
        CallbackEvent.RECONCILE_AFTER_REPOSITORY,
        CallbackMode.OBSERVE,
        context.repository_id,
    )
    context.result = context.system.reconcile_apply(
        "successor", context.selections, (callback,)
    )


@then("the repository remains ordinarily reconciled")
def observer_keeps_reconciled(context) -> None:
    record = next(
        item
        for item in context.system.snapshot().reconciliations
        if item.space_id == "successor" and item.repository_id == context.repository_id
    )
    assert record.status == "reconciled"


@then("the callback failure is reported without an unverified lifecycle state")
def observer_failure_separate(context) -> None:
    outcome = context.result.data["callback_outcomes"][0]
    assert outcome.handler_status is HandlerStatus.FAILED
    assert {item.status for item in context.system.snapshot().reconciliations} <= {
        "pending",
        "reconciled",
        "abandoned",
    }


@given("a released successor and a registered post-repository callback")
def given_post_callback(context) -> None:
    callback_successor(context, CallbackEvent.RECONCILE_AFTER_REPOSITORY, fail=False)


@when("the owner selects that callback as a gate while planning")
def plan_post_gate(context) -> None:
    callback = CallbackSelection(
        "zpp.behave",
        "verify",
        CallbackEvent.RECONCILE_AFTER_REPOSITORY,
        CallbackMode.GATE,
        context.repository_id,
    )
    capture(
        context,
        lambda: context.system.reconcile_plan(
            "successor", context.selections, (callback,)
        ),
    )


@then("OpenLease rejects the unsupported mode before Git mutation")
def post_gate_rejected(context) -> None:
    assert isinstance(context.error, InvalidRequest)
    assert git(context.destination, "rev-parse", "HEAD") == context.destination_head


def cohort_callback_successor(context) -> None:
    context.cohort_invocations = []
    context.fail_repository = None

    def callback(invocation):
        context.cohort_invocations.append(
            {
                "repository_id": invocation.event.repository_id,
                "cohort_id": invocation.event.cohort_id,
                "target": invocation.context.target.identifier,
                "input": invocation.input,
            }
        )
        if invocation.event.repository_id == context.fail_repository:
            raise RuntimeError("repository callback failed")

    registration = ExtensionRegistration(
        ExtensionManifest("zpp.behave"),
        operations=(ExtensionOperation("verify", callback),),
        callbacks=(
            ExtensionCallback(CallbackEvent.RECONCILE_AFTER_COHORT, "verify"),
        ),
    )
    context.system = type(new_system(context))(
        context.root / "state",
        openspec=context.openspec,
        extensions=(registration,),
    )
    released_with_change(context, external=True)
    current = context.system.status("successor").data["spaces"][0]
    context.selections = tuple(
        ReconcileSelection(
            item.repository_id,
            git(Path(item.source_path), "branch", "--show-current"),
            IntegrationStrategy.MERGE,
        )
        for item in current.members
        if item.generated
    )
    plan = context.system.reconcile_plan("successor", context.selections)
    assert plan.data["default_order"] == ("repo-3", "repo-2")
    context.cohort_input = {"command": "bdd", "complete": True}


@given("repo 3 and repo 2 complete reconciliation in dependency order")
def given_cohort_in_dependency_order(context) -> None:
    cohort_callback_successor(context)


@given("repo 3 and repo 2 completed reconciliation")
def given_completed_cohort(context) -> None:
    cohort_callback_successor(context)


@given("one observational after-cohort callback is selected with explicit input")
def given_observational_cohort_callback(context) -> None:
    context.cohort_callback = CallbackSelection(
        "zpp.behave",
        "verify",
        CallbackEvent.RECONCILE_AFTER_COHORT,
        CallbackMode.OBSERVE,
        input=context.cohort_input,
    )


@given("the selected after-cohort callback fails for repo 3")
def given_repo_three_callback_failure(context) -> None:
    context.fail_repository = "repo-3"
    given_observational_cohort_callback(context)


@when("OpenLease dispatches the completed cohort callback")
def dispatch_completed_cohort_callback(context) -> None:
    context.result = context.system.reconcile_apply(
        "successor", context.selections, (context.cohort_callback,)
    )


@then("repo 3 receives one invocation bound only to repo 3")
def repo_three_isolated(context) -> None:
    assert context.cohort_invocations[0]["repository_id"] == "repo-3"
    assert context.cohort_invocations[0]["target"] == "repo-3"


@then("repo 2 receives one invocation bound only to repo 2")
def repo_two_isolated(context) -> None:
    assert context.cohort_invocations[1]["repository_id"] == "repo-2"
    assert context.cohort_invocations[1]["target"] == "repo-2"


@then("both events identify the cohort and their repository")
def cohort_events_identify_scope(context) -> None:
    assert [item["cohort_id"] for item in context.cohort_invocations] == [
        "successor",
        "successor",
    ]
    assert [item["repository_id"] for item in context.cohort_invocations] == [
        "repo-3",
        "repo-2",
    ]


@then("both invocations receive the same captured input")
def cohort_invocations_receive_input(context) -> None:
    assert [item["input"] for item in context.cohort_invocations] == [
        context.cohort_callback.input,
        context.cohort_callback.input,
    ]


@then("repo 2 still receives its repository-specific invocation")
def repo_two_runs_after_failure(context) -> None:
    assert [item["repository_id"] for item in context.cohort_invocations] == [
        "repo-3",
        "repo-2",
    ]


@then("both repository-specific outcomes are reported in reconciliation order")
def repository_outcomes_reported_in_order(context) -> None:
    outcomes = context.result.data["callback_outcomes"]
    assert [item.handler_status for item in outcomes] == [
        HandlerStatus.FAILED,
        HandlerStatus.COMPLETED,
    ]
    assert [item.target for item in outcomes] == ["repository:repo-3", "repository:repo-2"]


@then("every ordinary reconciliation result remains unchanged")
def ordinary_results_remain_reconciled(context) -> None:
    records = [
        item
        for item in context.system.snapshot().reconciliations
        if item.space_id == "successor"
    ]
    assert {item.status for item in records} == {"reconciled"}


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
