## MODIFIED Requirements

### Requirement: Explicit cohort reconciliation
The first release SHALL provide an explicit `reconcile` command that is never triggered implicitly by lock, release, close, cleanup, recovery, projection removal, finalization, extension registration, configuration presence, operation registration, or callback availability. The owner SHALL supply the integration path after work is ready as an ordered mapping from each selected generated source branch to destination ref; `defer` SHALL NOT predetermine that path.

A read-only reconciliation plan SHALL record destination refs and observed commits, inspect every selected generated member together, and report missing paths or branches, dirty worktrees, source and destination commits, divergence, likely textual conflicts, dependency-informed integration order, intrinsic OpenLease safety checks, and the exact optional extension callbacks selected for each event. Each callback selection SHALL name extension identity, operation, event, mode, repository or cohort target, and immutable owner-supplied input. The callback drift evidence SHALL cover that captured input together with registration and target context. A registered callback that is not selected SHALL not appear as required work.

Applying the accepted plan SHALL use only the recorded integration path, require an explicit merge or rebase strategy for every repository, process one repository at a time, and stop at the first Git conflict without touching later repositories. Callback code SHALL NOT choose or change a source, destination, strategy, staging action, commit, merge/rebase operation, conflict resolution, result record, or finalization disposition.

The event `reconcile.before_repository` SHALL run after plan revalidation and immediately before OpenLease mutates that repository. It MAY be observational or MAY be explicitly selected as a gate. Failure of a gating callback SHALL stop before that repository's Git mutation and leave later repositories untouched. The event `reconcile.after_repository` SHALL run only after OpenLease completes the repository's integration and records its ordinary `reconciled` result. Both repository events SHALL receive the selected callback input and a repository event identifying the cohort and selected repository.

The event `reconcile.after_cohort` SHALL begin only after every selected member completes and is recorded according to the ordinary contract. Each selected after-cohort callback SHALL then be invoked once for each completed repository, in deterministic reconciliation order, using a freshly resolved extension context bound to only that repository and an immutable event identifying both the cohort and repository. Every invocation SHALL receive the same captured input from that callback selection and SHALL produce a distinct repository-specific outcome. All post-mutation callback invocations SHALL be observational in this release.

Failure of an observational callback SHALL be recorded and reported separately without rolling back, downgrading, blocking finalization of, or otherwise reinterpreting the completed reconciliation result. Reconciliation SHALL retain only the existing member statuses `pending`, `reconciled`, and `abandoned`; this change SHALL NOT add integrated-but-unverified, callback-retry, or callback-gated-finalization state. Supporting a post-mutation gate requires a separate lifecycle change.

The accepted plan SHALL bind callback selection to the current compatible registration, captured input, and target-context evidence. Apply SHALL reject callback registration, input, or target drift before any Git mutation. With no selected callbacks, reconciliation SHALL follow the same explicit Git integration and intrinsic safety path without invoking extension code.

#### Scenario: Specify the merge path after work is ready
- **WHEN** a released successor has generated branches and the owner invokes `reconcile` with an ordered destination mapping
- **THEN** OpenLease plans exactly those source-to-destination legs against current commits without deriving any path, strategy, or callback input from extension configuration

#### Scenario: Plan an explicit ZPP verification command
- **WHEN** the owner selects a reconciliation callback with input `{"command": "bdd", "complete": true}`
- **THEN** the read-only plan reports that captured input and its drift evidence before mutation

#### Scenario: Reconcile provider before consumer by default
- **WHEN** repo 2 depends on a writable OpenSpec authority hosted by repo 3 and no owner override changes plan order
- **THEN** the plan places repo 3 before repo 2 and displays that integration order plus any explicitly selected callbacks before mutation

#### Scenario: Stop a cohort on the first Git conflict
- **WHEN** one repository integration encounters a Git conflict
- **THEN** OpenLease preserves the conflict for explicit resolution, leaves later repositories untouched and pending, and invokes no post-repository or after-cohort callback for the incomplete cohort

#### Scenario: Require an explicit complete integration path
- **WHEN** apply lacks a destination or merge/rebase strategy for any selected generated member
- **THEN** OpenLease rejects mutation and reports missing legs without selecting defaults from callback or extension configuration

#### Scenario: Reconcile without extension callbacks
- **WHEN** an accepted plan selects no extension callbacks
- **THEN** OpenLease performs explicit integration and intrinsic safety checks without invoking any registered extension operation

#### Scenario: Stop at an explicitly selected pre-integration gate
- **WHEN** a gating `reconcile.before_repository` callback fails
- **THEN** OpenLease records its repository-specific outcome, does not mutate that repository, and leaves all later unprocessed repositories untouched

#### Scenario: Report an observational repository callback failure
- **WHEN** a selected `reconcile.after_repository` callback fails after successful integration
- **THEN** OpenLease preserves the ordinary reconciled result, reports the repository-specific callback failure separately, and introduces no unverified status

#### Scenario: Dispatch cohort callbacks through isolated repository contexts
- **WHEN** repo 3 and repo 2 complete in that reconciliation order and one `reconcile.after_cohort` callback is selected
- **THEN** OpenLease invokes it first with repo 3's bound context and then with repo 2's bound context, with both cohort and repository identity in each event and the selected input in each invocation

#### Scenario: Report one failed cohort invocation without suppressing the rest
- **WHEN** a selected observational after-cohort callback fails for repo 3 and succeeds for repo 2
- **THEN** OpenLease reports both repository-specific outcomes, preserves every member result and ordinary finalization eligibility, and does not reinterpret either integration

#### Scenario: Reject an unsupported post-mutation gate
- **WHEN** a request selects gating mode for `reconcile.after_repository` or `reconcile.after_cohort`
- **THEN** planning rejects the unsupported mode before Git mutation

#### Scenario: Reject callback drift before integration
- **WHEN** an accepted plan's selected callback registration, captured input, or target context changes before apply
- **THEN** OpenLease rejects the stale plan before staging, committing, merging, rebasing, or changing reconciliation state
