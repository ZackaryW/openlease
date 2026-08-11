# Collision-aware Workset Planning Specification

## Purpose

Provides deterministic machine-local leasing and coherent state transitions for codespaces whose branches or repositories can mutate overlapping logical OpenSpec authorities.

## Requirements

### Requirement: Complete preflight before mutation
The system SHALL resolve and validate the complete associated authority graph, the explicit affected claim, and that claim's required writable OpenSpec authority closure before changing `openlease` state or an OpenSpec workset projection.

#### Scenario: Reject an invalid complete shape
- **WHEN** any checkout, authority, relationship, access role, or lease conflict makes the requested codespace shape invalid
- **THEN** the system rejects the complete request without persisting a partial graph or changing an existing projection

### Requirement: Explicit first-release relationship discovery
The first release SHALL resolve authority closure only from explicitly registered nodes and explicit parent or dependency relationships. It SHALL NOT silently persist relationships inferred from OpenSpec context, store, filesystem, or Git metadata. Inspection MAY report a possible missing relationship, but acquisition SHALL require the owner to register it explicitly.

#### Scenario: Do not claim an inferred store relationship
- **WHEN** OpenSpec inspection suggests that an affected project uses an unregistered external store
- **THEN** planning reports the unresolved relationship and rejects acquisition without registering or leasing the store automatically

### Requirement: Explicit affected claim bounds mutation
Before `lock`, `lockable`, or `defer`, the selected session SHALL have an explicit affected claim naming the project or OpenSpec authority targets expected to change. Association alone SHALL provide working context and SHALL NOT imply that every associated repository or writable-capable dependency is affected. The system SHALL expand the affected targets through required writable OpenSpec dependencies and hierarchy conflict coverage, while retaining all other associated members as pinned, non-owning context. A later expansion or reduction of the affected claim SHALL require complete replanning and atomic replacement rather than incremental lease growth.

#### Scenario: Affect one monorepo child
- **WHEN** repo 1 root, child A, and child B are associated but the affected claim names only child A
- **THEN** the requested held set contains A, the parent is used only for conflict coverage, and root and B remain unheld context

#### Scenario: Expand an affected external dependency
- **WHEN** the affected claim names repo 2 and repo 2 requires writable use of the OpenSpec authority hosted by repo 3
- **THEN** the resolved affected closure contains repo 2's work target and repo 3's hosted authority without treating unrelated associated repositories as affected

### Requirement: Exclusive machine-local authority leases
The system SHALL use a durable machine-local registry to ensure that one logical OpenSpec authority has at most one active writable codespace owner. It SHALL arbitrate acquisition atomically so concurrent processes cannot both acquire the same authority after observing it as available. An OpenSpec workset, editor folder set, branch name, or physical path alone SHALL NOT establish or prove lease ownership.

#### Scenario: Reject concurrent branches on one authority
- **WHEN** branch A has an active writable lease for a logical OpenSpec authority and branch B requests writable access to that same authority on the same machine
- **THEN** the system rejects or defers branch B without granting it a concurrent writable lease, even when the branches use different worktree paths

#### Scenario: Claim a shared external authority
- **WHEN** a project depends on an OpenSpec authority hosted by another repository and that authority belongs to the requested writable closure
- **THEN** the system atomically leases the hosted logical authority together with every other writable authority required by the codespace

### Requirement: Hierarchical authority exclusion
Leasing a parent OpenSpec authority SHALL also exclude writable leases for every nested child authority. Leasing one child authority SHALL NOT implicitly lease its parent or sibling authorities, so different sessions MAY work through distinct children when neither session leases their parent.

#### Scenario: Parent lease blocks child work
- **WHEN** one session leases a repository-root OpenSpec authority and another requests writable access to one of its nested child authorities
- **THEN** the second request is not lockable because the parent lease covers that child

#### Scenario: Distinct child leases coexist in one checkout
- **WHEN** separate sessions request writable access to distinct child authorities under one unleased parent, including when both projects belong to the same physical repository checkout
- **THEN** both authority lease sets are compatible and physical checkout overlap alone does not make either request non-lockable

### Requirement: Distinguish held authorities from conflict coverage
The system SHALL record the exact writable authorities held by a space separately from the ancestor and descendant scopes used to test hierarchical conflicts. Holding a child authority SHALL conflict with a request for its parent but SHALL NOT make the holder an owner of that parent or conflict with a sibling child. Status and collision reports SHALL identify both the held authority and the relationship that expands its conflict coverage.

#### Scenario: Child coverage does not become parent ownership
- **WHEN** a space holds child authority A under an unleased root authority
- **THEN** status reports A as held, reports that a root lease would conflict through ancestry, and does not report the root or sibling B as held

### Requirement: Audit OpenSpec authority boundaries
The system SHALL record the repository-relative path boundary of every held OpenSpec authority and audit changed OpenSpec paths against those boundaries before release and reconciliation. If a space holding only a child authority changed a parent, sibling, or otherwise unheld OpenSpec authority, the system SHALL report a boundary violation and SHALL NOT represent that branch cohort as collision-safe until the violation receives an explicit resolution. This audit SHALL NOT claim to prevent arbitrary shell, editor, code, or cross-machine mutations outside OpenLease's observable guarantee.

#### Scenario: Detect a sibling authority edit
- **WHEN** a space holds child authority A but its branch also changes files under child authority B
- **THEN** the boundary audit identifies the B paths as outside the held set and blocks a collision-safe release or reconciliation result

### Requirement: Access-aware dependency closure
A writable dependency SHALL add its target authority to the requested held set and include the target's hierarchy when calculating conflict coverage without acquiring its ancestors. A read-only dependency SHALL remain visible in the codespace graph without acquiring a writable authority lease or conflicting solely because another session owns that authority.

#### Scenario: Expand a writable external dependency
- **WHEN** an associated project has a writable dependency on an authority hosted by another repository
- **THEN** the requested lease closure includes that hosted authority

#### Scenario: Share a read-only dependency
- **WHEN** multiple sessions include the same authority only through read-only dependency relationships
- **THEN** those relationships do not conflict with each other or acquire a writable lease

### Requirement: Read-only lockable preflight
The `lockable` command SHALL resolve the same complete affected claim and logical authority lease set as `lock` without acquiring, releasing, or changing any lease, session, projection, branch, checkout, or worktree. It SHALL return a true outcome when the complete current affected authority set can be acquired atomically and a false outcome with every conflicting authority scope otherwise.

#### Scenario: Report a lockable request
- **WHEN** every requested logical authority scope is compatible with active leases
- **THEN** `lockable` returns true without mutating machine-local state

#### Scenario: Report a non-lockable request
- **WHEN** any requested logical authority scope conflicts with another active session
- **THEN** `lockable` returns false with the complete conflict set and leaves all state unchanged

### Requirement: Worktree-neutral authority evaluation
Creating or selecting a different Git worktree SHALL NOT change the logical identity or hierarchy of any requested OpenSpec authority. A worktree MAY be used independently for Git branch or workspace isolation when authority scopes are compatible, but SHALL NOT be presented as a resolution for a false `lockable` authority result.

#### Scenario: Share one checkout across distinct child authorities
- **WHEN** one session uses child authority A through a canonical checkout and another requests child authority B through that same checkout while the parent is unleased
- **THEN** `lockable` returns true because the authority scopes are independent

#### Scenario: Do not bypass a logical authority lease
- **WHEN** another session already leases the same logical authority requested by the current session
- **THEN** `lockable` returns false before and after substituting a different worktree

#### Scenario: Use a worktree without changing authority compatibility
- **WHEN** authority-compatible child sessions choose different worktrees so they can use different Git branches
- **THEN** their authority lease compatibility remains unchanged from the equivalent same-checkout plan

### Requirement: Deferred successor preserves authority exclusion
The `defer` command SHALL be available only when the selected session's current `lockable` result is false. It SHALL create and record a distinct deferred successor space with the selected session's complete resolved repository and OpenSpec authority closure without acquiring any conflicting logical authority lease. While the conflicting lease remains active, reevaluating the successor SHALL remain false regardless of its new physical worktree paths. The system SHALL NOT report the successor as writable or allow an `openlease`-governed protected mutation until its complete lease is acquired.

#### Scenario: Defer without acquiring the conflict
- **WHEN** a session is non-lockable because another session owns one of its requested logical authorities and the caller invokes `defer`
- **THEN** the system may create its complete deferred worktree cohort and successor-space record but leaves the existing owner and source session unchanged and grants the successor no conflicting lease

#### Scenario: Remain non-lockable after deferral
- **WHEN** a deferred successor is reevaluated while the conflicting authority owner remains active
- **THEN** `lockable` returns false with the same logical conflict even though the successor uses different worktrees

#### Scenario: Become lockable after the owner releases
- **WHEN** every conflicting owner releases, no new conflicting lease exists, and the successor's complete baseline remains valid
- **THEN** the deferred successor's next `lockable` evaluation returns true and a subsequent `lock` may atomically acquire its complete authority set

#### Scenario: Reject unnecessary deferral
- **WHEN** the selected session is already lockable
- **THEN** `defer` rejects the request without creating a successor space, branch, worktree, or deferred state

### Requirement: Deferred promotion revalidates clean baselines
Before a deferred successor acquires leases, the system SHALL require every recorded blocking predecessor to have an integrated, explicitly abandoned, or superseded disposition; re-resolve its complete authority graph; and compare every repository's recorded source ref, starting commit, current head, effective authority paths, and graph generation with current state. When a blocker was integrated, the successor SHALL also prove that its corresponding clean baseline includes the recorded integrated destination commit. It SHALL refresh a stale deferred baseline only when every generated worktree is clean and untouched and the refresh can preserve the recorded graph; otherwise it SHALL reject promotion with the divergent, dirty, or structurally stale members identified. Lease acquisition SHALL compare-and-swap against both the observed lease-registry revision and authority-graph generation. It SHALL NOT silently acquire a stale or user-modified deferred cohort.

#### Scenario: Release without integration is insufficient
- **WHEN** a blocking owner releases its lease but its authority changes have no integrated, abandoned, or superseded disposition
- **THEN** the successor remains ineligible for promotion and reports the unresolved predecessor handoff

#### Scenario: Refresh an untouched deferred cohort
- **WHEN** the prior owner has released, upstream branches advanced, and every generated deferred worktree remains clean and unmodified
- **THEN** the system refreshes the successor's complete recorded baselines coherently before atomic lease acquisition

#### Scenario: Reject modified work before authority acquisition
- **WHEN** any generated deferred worktree contains changes made before the successor acquired its complete authority lease
- **THEN** the system rejects promotion, identifies every dirty member, and preserves all work without silently treating it as authorized

#### Scenario: Require explicit deferred promotion
- **WHEN** all blockers have acceptable dispositions and the successor becomes fresh and lockable
- **THEN** the system retains it as deferred until the owner explicitly invokes `lock` and does not acquire leases merely because another space released

### Requirement: Atomic complete lease acquisition
The system SHALL acquire the complete writable authority closure of the affected claim as one operation. Associated members outside that closure SHALL receive no lease. If any required authority is invalid, unclassifiable, or already leased by another codespace, no new authority from the request SHALL remain leased.

#### Scenario: Reject partial multi-authority acquisition
- **WHEN** a requested monorepo and shared-store codespace resolves several writable authorities and one is unavailable
- **THEN** the system leaves all previously unowned authorities unclaimed and reports the complete unavailable set

### Requirement: Deterministic collision report
When a requested writable authority set conflicts with existing active leases, the system SHALL identify every conflicting logical authority, its physical contexts, and its existing codespace owner before requesting or applying any resolution.

#### Scenario: Report all detected conflicts
- **WHEN** a requested codespace overlaps multiple authorities leased by existing codespaces
- **THEN** the system reports the complete detected conflict set and leaves existing and requested state unchanged until an accepted resolution is selected

### Requirement: Atomic relational-workset replacement
An accepted change to an existing relational workset SHALL replace its complete persisted graph, writable lease set, and projection as one logical operation. Failure SHALL leave the previously accepted graph, leases, and projection usable and SHALL NOT expose a partially replaced workset or an unlocked transition interval.

#### Scenario: Preserve the current workset after replacement failure
- **WHEN** any validation, persistence, or projection step of a relational-workset change fails
- **THEN** the system retains the previously accepted graph, complete lease set, and opening projection without exposing the incomplete successor

### Requirement: Idempotent compatible planning
A request whose resolved authority graph, affected claim, writable lease set, and owned projection are already compatible with the accepted state SHALL succeed as a no-op without replacing identity or rewriting the projection.

#### Scenario: Repeat a compatible request
- **WHEN** a caller repeats a request that resolves to the currently accepted relational shape and intact owned projection
- **THEN** the system returns the existing workset outcome without changing persisted state or member folders

### Requirement: Preserve unrelated state
Collision planning and mutation SHALL remain bounded to the selected relational workset, its logical writable authorities, and its proven owned projection. The system SHALL NOT treat ordinary OpenSpec workset membership as proof of ownership over member folders, logical authorities, or unrelated worksets.

#### Scenario: Plan beside an unrelated user workset
- **WHEN** an unrelated user-owned OpenSpec workset contains one or more of the same folders
- **THEN** the system preserves that workset and determines collision only from the accepted `openlease` collision authority rather than from OpenSpec workset membership alone

### Requirement: Preserve active lease validity during topology expansion
Before persisting an authority-graph addition while leases are active, OpenLease SHALL evaluate the candidate graph against every current lease owner in the same serialized mutation. Each owner SHALL retain its exact complete affected plan and conflict coverage, its held authorities SHALL remain exactly sufficient for that plan, and the candidate graph SHALL introduce no conflict between existing owners. If any condition fails, OpenLease SHALL reject the candidate atomically. The existence of a lease in a disconnected authority component SHALL NOT itself be a conflict or blocker.

#### Scenario: Accept an independent authority component
- **WHEN** a candidate repository and authority are disconnected from every active lease owner's accepted topology and conflict coverage
- **THEN** OpenLease persists the candidate while preserving every existing owner and lease

#### Scenario: Reject a new uncovered writable dependency
- **WHEN** a candidate writable dependency would add an authority to a locked space's required affected closure without adding a corresponding lease atomically
- **THEN** OpenLease rejects the candidate and preserves the original graph and complete lease set

#### Scenario: Reject expanded hierarchy coverage
- **WHEN** a candidate containment relationship would expand or otherwise change the logical conflict coverage of a held authority
- **THEN** OpenLease rejects the candidate even when no second current lease occupies the newly covered scope

#### Scenario: Reject a new conflict between existing owners
- **WHEN** a candidate relationship would make two previously compatible existing lease sets overlap
- **THEN** OpenLease rejects the candidate without changing either owner or lease set

### Requirement: Implicit selection preserves collision authority
A cwd-selected temporary space SHALL begin without an affected claim or held lease. The host-session token, current directory, worktree, association, and temporary-space ownership SHALL NOT constitute writable authority. Before `lockable`, `lock`, or `defer`, the space SHALL satisfy the same explicit affected-claim, complete planning, topology, and logical lease-conflict rules as an explicitly selected durable space.

#### Scenario: Do not lease from cwd selection
- **WHEN** implicit selection scaffolds or reclaims a temporary space for a registered worktree
- **THEN** the space holds no authority and cannot perform a protected mutation until its affected claim is explicitly declared and its complete lease is acquired

#### Scenario: Report the same logical conflict
- **WHEN** a cwd-selected temporary space explicitly affects an authority already covered by another active lease
- **THEN** `lockable` and `lock` report the same logical conflict they would report for an explicitly selected durable space

#### Scenario: Allow an unrelated temporary plan
- **WHEN** a cwd-selected temporary space explicitly affects an authority component disconnected from every active lease owner's conflict coverage
- **THEN** its plan is not blocked solely because another component has an active lease
