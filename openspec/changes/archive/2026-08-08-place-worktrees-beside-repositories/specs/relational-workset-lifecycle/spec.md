## ADDED Requirements

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

## MODIFIED Requirements

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
