# Relational Workset Lifecycle Specification

## Purpose

Provides a codespace lifecycle that relates Git checkouts to nested and shared OpenSpec authorities while remaining interoperable with ordinary OpenSpec worksets.

## Requirements

### Requirement: Authority graph relationship kinds
The system SHALL model selected Git checkouts and the logical OpenSpec roots or stores they can mutate as one codespace authority graph. It SHALL represent containment between a repository-root OpenSpec authority and its nested subproject authorities as directed parent-child relationships. It SHALL separately represent a project that uses an OpenSpec authority hosted by another repository as a directed dependency relationship. The system SHALL NOT infer one relationship kind solely from the presence of the other.

#### Scenario: Resolve nested monorepo authorities
- **WHEN** a selected monorepo contains a repository-root OpenSpec authority and nested subproject authorities A and B
- **THEN** the system represents the root authority as parent of the distinct A and B child authorities

#### Scenario: Resolve an externally hosted authority
- **WHEN** a selected project without its own OpenSpec root uses an OpenSpec authority hosted by another selected repository
- **THEN** the system represents a dependency from that project's work target to the hosted logical authority without treating the repositories as a parent-child hierarchy

### Requirement: Valid deterministic authority graph
The authority graph SHALL be acyclic, each child authority SHALL have at most one containment parent, and every relationship endpoint SHALL resolve to an explicitly registered node of the required kind. Registration SHALL assign or accept a stable repository identity; repository-local authorities SHALL combine that identity with a normalized repository-relative OpenSpec path, while registered stores SHALL retain their stable store identity. Worktrees sharing one Git common directory SHALL resolve through the same registered repository identity. A separate clone SHALL remain distinct unless the owner explicitly registers it with the existing identity.

#### Scenario: Reject an ambiguous or cyclic graph
- **WHEN** a relationship would introduce a cycle, a second containment parent, a missing endpoint, or an unclassifiable authority
- **THEN** the system rejects the relationship without changing the accepted graph generation

#### Scenario: Preserve authority identity across worktrees
- **WHEN** two worktrees share one registered Git common directory and contain the same normalized OpenSpec-relative path
- **THEN** the system resolves them to one logical authority identity with separate physical contexts

### Requirement: Branch-independent logical authority
The system SHALL distinguish a physical checkout path from the logical identity of an OpenSpec authority. Branches and worktrees derived from the same repository SHALL resolve the corresponding repository-local OpenSpec root to the same logical authority, while distinct nested OpenSpec roots SHALL remain distinct authority nodes.

#### Scenario: Match one authority across branches
- **WHEN** branch A and branch B use different physical checkouts of the same repository and both contain the corresponding OpenSpec root
- **THEN** the system reports one shared logical authority identity with two physical checkout contexts

### Requirement: Complete relational inspection
The system SHALL expose every selected checkout, logical OpenSpec authority, effective physical authority path, access role, and relationship when a caller inspects a relational workset. It SHALL NOT flatten the authority graph into an untyped folder list in its own status output.

#### Scenario: Inspect a relational workset
- **WHEN** a caller requests the status of an existing relational workset
- **THEN** the system reports all accepted checkout and authority nodes plus all parent-child and dependency relationships needed to reconstruct that workset

### Requirement: Explicit topology command surface
The command SHALL use `register` to define stable repository and authority nodes, `relate parent <parent> <child>` to define authority containment, and `relate dependency <consumer> <authority>` with an explicit writable or read-only access role to define shared authority use. These topology commands SHALL NOT acquire a checkout claim or authority lease. Predicate-style names beginning with `is` SHALL remain available for inspection rather than mutation.

#### Scenario: Bootstrap topology before locking
- **WHEN** a caller registers repository-root, nested, and externally hosted authorities and relates them before starting work
- **THEN** the system persists one inspectable topology without acquiring any lease or changing an OpenSpec workset projection

### Requirement: Durable terminal-selected sessions
The command SHALL create a durable session identity and allow subsequent operations to select it explicitly with a command option or the terminal's `OPENLEASE_SPACE` environment. `session attach` SHALL return the environment selection to apply; it SHALL NOT claim that a child process directly mutated its parent shell. A process ID, terminal process, or TTY identifier SHALL NOT itself own leases. Loss of the selecting terminal SHALL NOT silently release the durable session.

#### Scenario: Use one terminal as a session context
- **WHEN** a caller starts or attaches a shell to a durable session and then runs commands from that terminal environment
- **THEN** each command targets the selected session identity without treating the shell process as the lease owner

#### Scenario: Preserve a session after terminal loss
- **WHEN** the terminal selecting a locked session exits without an explicit release
- **THEN** the system retains the session and its leases for inspection and explicit recovery

### Requirement: Staged session command lifecycle
The command SHALL provide session start, attach, and close operations; `associate` to compose the selected session's complete context; `affect add`, `affect remove`, and `affect show` to declare and inspect targets expected to change; read-only `plan` and `lockable` operations; atomic `lock`; `isolate` to create and atomically lock an authority-compatible affected successor in separate branches; `defer` to bootstrap the affected non-lockable successor worktree set without leasing it; `reconcile` to plan and apply a later owner-specified merge path; and explicit `status`, `release`, and recovery operations. Registration, relationships, association, and the affected claim SHALL be completed before initial acquisition. An association or affected-claim change to a locked session SHALL either be rejected or replace the complete claimed shape atomically; it SHALL NOT expose incrementally acquired state.

#### Scenario: Acquire a composed session
- **WHEN** a caller selects a durable session, associates its intended targets, verifies its plan, and invokes `lock`
- **THEN** the system attempts one atomic acquisition for the complete resolved session shape

#### Scenario: Reject incremental locked growth
- **WHEN** a caller tries to add one association directly to an already locked session without a complete atomic successor operation
- **THEN** the system rejects the mutation and preserves the existing session shape and leases

#### Scenario: Isolate compatible child work
- **WHEN** child A is authority-compatible with active child B work but requires a different Git branch in their shared repository
- **THEN** `isolate` creates the affected successor worktree set and atomically leases A without treating B's physical checkout as an authority conflict

### Requirement: Affected deferred successor-space bootstrap
The `defer` command SHALL accept one successor name and optional per-repository branch selections for an unleased non-lockable session with an explicit affected claim. It SHALL resolve the complete associated graph and the affected claim's required writable repository and OpenSpec authority closure, deduplicate the affected closure by stable Git repository identity, and derive one linked worktree path for every distinct repository needed by that closure. For each generated repository, an omitted branch selection SHALL create a new branch from the recorded starting commit using the successor name; an existing local branch selection SHALL check out that branch; and a remote branch selection SHALL create and check out a corresponding local branch from that remote reference. Multiple affected OpenSpec roots in one repository SHALL map into that repository's single successor worktree. Unaffected and read-only associated members SHALL remain pinned references and SHALL NOT receive generated worktrees solely for joining the space.

#### Scenario: Defer with a same-named new branch
- **WHEN** a caller defers a non-lockable session whose affected closure spans several repositories with a valid unused successor name and omits branch selections
- **THEN** the system creates one derived linked worktree per distinct affected repository on a new same-named branch in that repository and records them as one deferred successor space

#### Scenario: Defer from an existing branch
- **WHEN** a caller supplies an available local branch or a resolvable remote branch for one repository in the deferred closure
- **THEN** the system creates that repository's linked worktree using the selected local branch or a new local branch derived from the remote reference while applying the default behavior to other repositories

#### Scenario: Reject an unavailable deferred branch
- **WHEN** any selected branch cannot be checked out in a new linked worktree
- **THEN** the system rejects the complete deferral without publishing a usable successor or changing the source session and retains preparation evidence whenever complete rollback cannot be proven

#### Scenario: Detect drift in shared read-only context
- **WHEN** a deferred successor references a read-only repository through an existing checkout and that checkout moves away from its recorded commit
- **THEN** status reports the view as non-reproducible and promotion requires restoring the recorded revision or explicitly replanning the complete space

#### Scenario: Do not materialize unrelated associated repositories
- **WHEN** repo 1, repo 2, and repo 3 are associated but the resolved affected closure requires only child A within repo 1
- **THEN** `defer` creates one repo 1 worktree and records repo 2 and repo 3 as pinned context without creating their branches or worktrees

### Requirement: Repository-adjacent managed worktree placement
For every repository that `isolate` or `defer` materializes, the system SHALL by default place the generated worktree beside that repository's registered source checkout. The destination name SHALL be the source checkout directory name followed by `-olease-` and the lowest available positive integer. Each repository in a multi-repository cohort SHALL resolve its destination independently beside its own source checkout.

#### Scenario: Create the first adjacent managed worktree
- **WHEN** a registered source checkout directory is named `repo1`, no destination candidate is occupied, and an affected successor requires a generated worktree
- **THEN** the generated worktree is its sibling named `repo1-olease-1`

#### Scenario: Increment beside one repository
- **WHEN** `repo1-olease-1` is unavailable and the next candidate is available
- **THEN** the generated worktree destination is `repo1-olease-2` beside the same registered source checkout

#### Scenario: Place a multi-repository cohort locally
- **WHEN** one successor materializes affected repositories whose registered source checkouts have different parent directories
- **THEN** each generated worktree is placed beside its own source checkout rather than collected beneath the machine-local state root

### Requirement: Collision-safe destination allocation
Before any Git side effect, the system SHALL evaluate candidates against every exact generated or reserved path in durable OpenLease state, every existing filesystem entry or symbolic link, and the repository's registered Git worktrees. It SHALL skip an occupied candidate regardless of whether its name resembles an OpenLease path. The system SHALL reserve the complete cohort's exact chosen destinations in the durable preparation record before creating any worktree. Concurrent preparations SHALL NOT reserve or create the same destination, and a destination that becomes occupied after reservation SHALL fail closed through the existing preparation-recovery lifecycle without overwriting or adopting the occupant.

#### Scenario: Skip an unmanaged matching directory
- **WHEN** `repo1-olease-1` exists but has no OpenLease ownership record
- **THEN** the system leaves it unchanged and selects the next available positive suffix

#### Scenario: Skip a state-reserved path before it exists
- **WHEN** another preparing successor has durably reserved `repo1-olease-1` but Git creation has not completed
- **THEN** a new plan treats that exact path as unavailable

#### Scenario: Serialize concurrent allocation
- **WHEN** two processes plan the same lowest available destination from one state generation
- **THEN** at most one complete preparation reserves that destination and the other performs no Git mutation from its stale plan

#### Scenario: Fail on a late external race
- **WHEN** an external process occupies a reserved destination after OpenLease preflight but before Git worktree creation
- **THEN** OpenLease does not overwrite or adopt it and retains the preparation evidence required for safe recovery

### Requirement: Naming is not ownership evidence
The `-olease-<n>` naming pattern SHALL be a human-visible indication of intended management and SHALL NOT establish ownership, lease status, repository identity, or cleanup authority. OpenLease SHALL recognize a managed worktree only from its exact durable path and recorded repository, branch, commit, and preparation provenance. A generated worktree MAY remain deferred, locked, released, or pending reconciliation without being renamed.

#### Scenario: Inspect a matching unmanaged path
- **WHEN** a sibling directory matches the `-olease-<n>` pattern but lacks exact durable provenance
- **THEN** OpenLease treats it as occupied unmanaged work and never removes, reuses, or reports it as owned

#### Scenario: Release without renaming
- **WHEN** an OpenLease-managed worktree moves from locked work to released reconciliation debt
- **THEN** its path remains unchanged while durable status reports its current lifecycle state

### Requirement: Explicit placement override and path compatibility
An explicit worktree-base override SHALL replace repository-adjacent placement for newly generated worktrees while retaining the `<source-directory>-olease-<n>` allocation and collision rules within that base. The machine-local state-root selection SHALL NOT implicitly override default repository-adjacent placement. Existing generated worktrees recorded before this behavior changes SHALL remain at their exact recorded paths and SHALL NOT be moved, renamed, adopted, or discarded automatically.

#### Scenario: Use an automation worktree base
- **WHEN** a caller supplies an explicit automation worktree base for a source checkout directory named `repo1`
- **THEN** the first available destination is `repo1-olease-<n>` directly beneath that base under the same collision rules

#### Scenario: Keep state separate from checkout placement
- **WHEN** the default state root is `~/.openlease` and no worktree-base override is supplied
- **THEN** state remains beneath `~/.openlease` while newly generated worktrees are placed beside their registered source checkouts

#### Scenario: Preserve a previously recorded destination
- **WHEN** existing state records a generated worktree beneath an older centralized worktree base
- **THEN** every lifecycle and reconciliation operation continues using that exact path without relocating it

### Requirement: Atomic deferred successor publication
Before creating any worktree, `defer` SHALL validate the complete successor plan, every deterministic destination collision, repository identity, starting commit, authority path remapping, and OpenSpec projection member. Git SHALL remain the authority for branch availability at creation time because refs and worktree occupancy can race after preflight. The operation SHALL reserve a successor identity and durable preparation journal before side effects, record each planned and completed side effect, and expose the successor as deferred only after every required worktree and its bounded OpenSpec projection are recorded. It SHALL return the successor identity so the terminal can attach explicitly. On failure, it SHALL leave the source session unchanged and remove only unchanged, clean worktrees and branches proven to have been created by that invocation. If any artifact cannot be safely removed or the process is interrupted, it SHALL retain a non-writable `preparation-failed` successor record that supports inspection, resumption, or explicit rollback rather than losing ownership evidence.

#### Scenario: Roll back incomplete multi-repository deferral
- **WHEN** creation succeeds for one repository but fails for a later repository before successor publication
- **THEN** the system exposes no usable deferred successor, rolls back only unchanged clean artifacts created by that invocation, and retains a `preparation-failed` journal whenever complete rollback cannot be proven

### Requirement: Complete deferred successor record
After successful worktree creation, `defer` SHALL create a distinct durable `openlease` space that records its source-space lineage and blocking predecessor identities; its complete associated repository and authority graph; its exact affected claim and resolved writable closure; every parent-child and dependency edge; every affected, writable, or read-only role; every original and effective path; every logical authority and repository identity; the authority-graph generation; every member's exact observed commit; and each generated affected worktree's branch, upstream, exact starting commit, and current head. It SHALL remap affected repository-local OpenSpec authority paths into the appropriate effective worktrees, retain unaffected members as pinned context, create or update only the successor's bounded OpenSpec workset projection, return the successor identity for explicit terminal attachment, and report it as deferred rather than locked. It SHALL NOT require future integration destinations to be selected during deferral.

#### Scenario: Inspect the example successor space
- **WHEN** repo 1 contains root, A, and B OpenSpec authorities, repo 2 consumes repo 3's writable OpenSpec authority, the affected claim names repo 2 and its repo 3 authority closure, and a caller inspects their successfully deferred successor
- **THEN** the system reports repo 2 and repo 3 generated worktrees, repo 3's remapped shared authority, repo 1 as pinned associated context without a generated worktree, the complete relationship graph and branch provenance, every unresolved authority conflict, and the absence of writable authority leases

### Requirement: Successor-local relationship wiring
The deferred successor SHALL preserve the source space's complete association and authority topology while rebinding affected repository-local authorities and affected writable external dependencies to the corresponding effective paths in the successor worktree set. In particular, an affected consumer repository that requires an OpenSpec authority hosted by another repository SHALL resolve that affected authority through the host's successor worktree rather than through the source checkout or shared global OpenSpec registration. Unaffected associations SHALL retain their pinned source paths, and multiple affected parent-child relationships in one repository SHALL resolve within that repository's single successor worktree. The wiring SHALL be bounded to the successor and SHALL NOT mutate another space or the shared global OpenSpec configuration.

#### Scenario: Wire repo 2 to repo 3 inside the successor
- **WHEN** repo 2 consumes repo 3's writable OpenSpec authority and `defer` creates successor worktrees for both repositories
- **THEN** the successor maps repo 2's dependency to the authority path inside the repo 3 successor worktree while the source space and shared global registration remain unchanged

### Requirement: Retain branch cohorts for explicit integration
Release, close, recovery, projection removal, and worktree cleanup SHALL NOT merge or delete generated branch work. The system SHALL retain every repository member generated for the affected claim as integration debt with its source and effective paths, branch, starting commit, current head, and reconciled or abandoned disposition until all generated members have an explicit disposition and all owned worktrees are safely removed. Unaffected pinned members SHALL NOT become integration debt. Status SHALL report dirty state and divergence per generated member so a later reconciliation workflow can plan and verify the affected cohort without claiming that separate Git repositories merge atomically.

#### Scenario: Preserve a released multi-repository cohort
- **WHEN** a successor space with generated work across repo 1, repo 2, and repo 3 releases its leases
- **THEN** the system preserves every branch and worktree plus the complete cohort provenance as integration debt and performs no automatic merge

#### Scenario: Refuse premature finalization
- **WHEN** any retained branch lacks a reconciled or abandoned disposition or any generated worktree remains
- **THEN** the system refuses to finalize the successor-space record and reports the outstanding members

### Requirement: Explicit cohort reconciliation
The first release SHALL provide an explicit `reconcile` command that is never triggered implicitly by lock, release, close, cleanup, recovery, projection removal, or finalization. The owner SHALL be able to supply the merge path after work is ready, as an ordered mapping from each selected generated source branch to its destination ref; `defer` SHALL NOT predetermine that path. A read-only reconciliation plan SHALL record the destination refs and their observed commits, inspect every selected generated member together, and report missing paths or branches, dirty worktrees, source and destination commits, divergence, likely textual conflicts, dependency-informed integration order, and required verification. Applying the accepted plan SHALL use the recorded merge path, require an explicit merge or rebase strategy for every repository, process one repository at a time, stop at the first conflict without touching remaining repositories, verify each completed repository, and run change-wide verification only after the full selected cohort is integrated. It SHALL record each member as pending, reconciled with its resulting commit, or explicitly abandoned.

#### Scenario: Specify the merge path after work is ready
- **WHEN** a released successor has generated branches for its affected repositories and the owner invokes `reconcile` with an ordered destination mapping
- **THEN** the system plans exactly those generated source-to-destination legs against current destination commits without requiring destinations for unaffected associated repositories or requiring that merge path to have existed when the successor was deferred

#### Scenario: Reconcile provider before consumer by default
- **WHEN** repo 2 depends on a writable OpenSpec authority hosted by repo 3 and no owner override changes the plan order
- **THEN** the reconciliation plan places repo 3 before repo 2, displays that order before mutation, and runs complete cross-repository verification after both integrations

#### Scenario: Stop a cohort on the first conflict
- **WHEN** one repository reconciliation encounters a Git conflict
- **THEN** the operation preserves the conflict for explicit resolution, leaves all later repositories untouched and pending, and retains the complete cohort record

#### Scenario: Require an explicit complete merge path
- **WHEN** a caller applies `reconcile` without a destination and merge-or-rebase strategy for every selected generated member
- **THEN** the system rejects mutation and reports the missing legs without selecting defaults

### Requirement: OpenSpec workset interoperability
The system SHALL make an accepted relational working view openable through OpenSpec's workset surface. Projection to an OpenSpec workset SHALL preserve the ordered set of distinct member folders while `openlease` retains relationship information that the OpenSpec workset format cannot express.

#### Scenario: Open a relational working view
- **WHEN** a caller opens an accepted relational workset
- **THEN** the system opens an OpenSpec workset containing the relational view's distinct member folders in their planned order

### Requirement: Proven-owned bounded projection
Each accepted space SHALL own at most one current bounded OpenSpec workset projection identified by a versioned ownership record and structural generation. Replacement, close, and recovery SHALL mutate or remove a projection only when ownership and expected membership remain intact. An orphaned projection whose OpenLease ownership is still provable MAY be reported and removed at an explicit mutating boundary; ambiguous or user-owned worksets SHALL be preserved.

#### Scenario: Fail closed on a modified projection
- **WHEN** an OpenLease-owned projection's membership no longer matches its recorded structural generation
- **THEN** the system reports an ownership conflict and preserves the projection rather than overwriting or deleting it

### Requirement: Durable versioned local state and explicit recovery
The system SHALL persist graph generations, sessions, affected claims, leases, preparation journals, projection ownership, blockers, and reconciliation debt in a versioned machine-local state root using serialized atomic mutation. Concurrent mutations SHALL be mutually exclusive and compare the state generation observed during planning. Terminal loss SHALL NOT expire a lease. Recovery SHALL require explicit selection and force authority, release only OpenLease-owned leases or projections, and preserve every branch, worktree, dirty file, and unresolved integration record.

#### Scenario: Recover without deleting generated work
- **WHEN** the owner explicitly force-recovers an abandoned locked space
- **THEN** the system releases its machine-local authority leases, preserves all generated branches and worktrees as reconciliation debt, and does not infer liveness from a missing terminal process

### Requirement: Library-first optional CLI distribution
The product SHALL expose the complete lifecycle through an importable Python library returning deterministic structured results. The distribution SHALL declare Python 3.11 as its minimum supported interpreter without imposing an upper version bound. The base library and every required runtime dependency SHALL remain installable and operational on Python 3.11 or newer, and the base installation SHALL NOT require the optional CLI dependency.

The product SHALL provide an optional Typer CLI that is installable on the same declared interpreter range, delegates to the same public lifecycle, supports machine-readable JSON output, maps expected domain failures to stable nonzero statuses without tracebacks, and accepts explicit state-root and destination overrides for isolated automation without weakening ownership checks. Expanding interpreter compatibility SHALL NOT change public APIs, persisted state formats, lifecycle results, CLI semantics, or extension contracts.

#### Scenario: Use the library without CLI dependencies
- **WHEN** a consumer installs and imports the base package without the optional CLI dependency
- **THEN** the public OpenLease lifecycle remains usable without importing Typer

#### Scenario: Install the base library on Python 3.11
- **WHEN** a consumer installs and imports the base OpenLease package with Python 3.11
- **THEN** installation succeeds and the public lifecycle is available with the same observable contract as on a newer supported interpreter

#### Scenario: Use the optional CLI on Python 3.11
- **WHEN** a consumer installs the CLI extra and invokes OpenLease with Python 3.11
- **THEN** the command surface delegates to the public lifecycle and preserves its documented structured and machine-readable results

#### Scenario: Reject an interpreter below the supported floor
- **WHEN** package metadata is evaluated for an interpreter older than Python 3.11
- **THEN** installation is rejected as outside the declared supported range

### Requirement: Non-destructive workset lifecycle
Changing or removing an `openlease` relational workset SHALL NOT delete or modify its member folders. The system SHALL remove or replace only state and OpenSpec workset projections whose `openlease` ownership it can prove and SHALL preserve unrelated user-owned worksets.

#### Scenario: Remove a relational workset
- **WHEN** a caller removes an existing relational workset whose owned state is intact
- **THEN** the system removes only the proven `openlease` state and projection while leaving every member folder and unrelated OpenSpec workset unchanged

#### Scenario: Reject ambiguous projection ownership
- **WHEN** a projection that would be replaced or removed cannot be proven to belong to the selected relational workset
- **THEN** the system rejects that mutation without deleting the ambiguous projection or changing member folders
