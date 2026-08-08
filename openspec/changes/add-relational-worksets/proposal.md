## Why

OpenSpec worksets compose folders into a personal local working view, but they do not express which OpenSpec roots and stores those folders can mutate or prevent two branches from concurrently changing the same logical OpenSpec authority. ZPP's codespace planner explored machine-local collision control and bounded workset projections, but that behavior is coupled to ZPP-specific workflow policy; `openlease` needs a standalone authority graph and lease lifecycle for complex multi-repository codespaces.

## What Changes

- Add a standalone Python tool that composes with the installed OpenSpec CLI rather than depending on the ZPP runtime.
- Let a relational codespace relate selected Git checkouts to the OpenSpec roots and stores they can mutate instead of flattening every member into an untyped folder list.
- Represent a repository-root OpenSpec authority and nested subproject OpenSpec authorities as parent and child nodes, while representing a project that uses an authority hosted by another repository as a dependency edge.
- Resolve branch and worktree checkouts of the same repository back to stable logical OpenSpec authority identities, so different physical paths do not bypass collision control.
- Provide a lifecycle for establishing, inspecting, changing, opening, and removing relational worksets while preserving the member folders and unrelated user-owned OpenSpec worksets.
- Require an affected claim before work begins, separating the complete associated working view from the project and authority targets expected to change. Resolve only that claim's required writable OpenSpec closure, then atomically lease it on the local machine, reject concurrent ownership of the same logical authority, make a compatible repeated request idempotent, and avoid leaving partial relationship, lease, or workset state after failure.
- Allow sessions that lease independent child authorities to coexist even when their projects belong to the same monorepo or use the same physical checkout; physical checkout overlap alone is not an OpenSpec collision.
- Audit changed OpenSpec paths against each space's exact held-authority boundaries before release and reconciliation so independent-child work is not represented as collision-safe if it also changed a parent, sibling, or other unheld authority. Arbitrary code edits and cross-machine writes remain outside the lease guarantee.
- Group work through a durable session identity selected explicitly with `--space` or the current terminal's `OPENLEASE_SPACE` environment; `session attach` returns that selection contract but does not pretend a child process can mutate its parent shell. Keep terminal process and TTY identity as context rather than lease authority.
- Expose explicit topology commands (`register`, `relate parent`, and `relate dependency`), session composition (`associate`), affected-claim commands (`affect add`, `affect remove`, and `affect show`), read-only `plan` and `lockable` preflights, atomic `lock`, `isolate` for lockable branch isolation, a `defer` successor-space bootstrap for non-lockable sessions, and explicit `status`, `release`, `reconcile`, session-close, recovery, and branch-disposition operations.
- Let `defer` extend GitHub Desktop's worktree creation behavior across the affected claim rather than every associated writable member: accept one successor name and optional per-repository branch selections, derive collision-free paths, create one linked worktree for every distinct Git repository needed by the resolved affected writable closure, and create a same-named branch in each generated repository when no branch is supplied there.
- Record the deferred result as a distinct successor `openlease` space containing the complete associated repository and OpenSpec authority graph, the exact affected claim, remapped effective paths for affected members, successor-local dependency wiring, generated worktree branches, and exact observed commits. Unaffected members remain pinned context and do not receive branches merely because they are associated.
- Keep the successor space unleased while its authority conflict remains. Creating its worktree cohort prepares later branch work but does not authorize concurrent mutation of a conflicting OpenSpec authority; the successor must refresh its clean baselines and acquire its complete lease after the conflict clears.
- Record which predecessor spaces block a deferred successor and require each blocker to be integrated, explicitly abandoned, or superseded by a recorded handoff before promotion; lease release by itself is not proof that the successor starts from accepted specification history.
- Carry every generated repository branch through an explicit `reconcile` lifecycle. Let the owner specify the ordered merge path later, when reconciliation is planned, rather than fixing destination refs during `defer`; then plan divergence and likely conflicts, reconcile one repository at a time using that path and the selected strategies, run repository and change-wide verification, retain unresolved branch debt, and finalize only after every branch has an explicit disposition and every generated worktree is gone.
- Require topology and session composition before acquisition. A locked session cannot grow incrementally; any changed shape must be validated and acquired as one atomic successor.
- Reuse the proven ZPP ideas of explicit member selection, stable structural identity, bounded OpenSpec workset projection, and plan-before-mutation behavior where they fit the new relationship model.
- Keep OpenSpec worksets as local opening projections rather than ownership evidence; `openlease`'s machine-local lease registry is the collision authority.
- Follow `agent-router`'s completed distribution shape: an importable Python library with deterministic structured results and an optional Typer CLI, explicit destinations/state roots for safe automation and tests, versioned ownership records, fail-closed inspection, and atomic mutation.
- Keep ZPP profiles, traits, agent hooks, and workflow skills outside this package. A Git worktree may provide branch or workspace isolation for otherwise authority-compatible work, but it does not change logical authority identity and cannot turn an authority conflict into a lockable request.

## Capabilities

### New Capabilities

- `relational-workset-lifecycle`: Establish and manage a codespace graph of Git checkouts and their parent, child, and shared OpenSpec authorities while remaining interoperable with OpenSpec worksets.
- `collision-aware-workset-planning`: Preflight an explicit affected claim and atomically lease only its complete required writable authority closure, allow independent child work in one monorepo, and reject only overlapping logical authority scopes.

### Modified Capabilities

None. `openlease` has no existing canonical product specifications.

## Impact

- Adds the initial `openlease` Python package, public command or library surface, metadata model, OpenSpec adapter, and automated verification.
- Invokes installed OpenSpec context, store, and workset commands and reads or writes only `openlease`-owned machine-local metadata plus explicitly selected OpenSpec worksets.
- Inspects Git checkout provenance and OpenSpec authority relationships so a logical authority has the same collision identity across local branches and worktrees.
- Adds a deterministic command surface whose terminal-selected session maps to a durable machine-local identity rather than a transient process or TTY.
- Creates Git branch/worktree cohorts only for repositories required by a successor's affected claim, while retaining the complete associated view, preserving the existing owner's authority lease, and keeping enough provenance for later reconciliation.
- Establishes a new local-state compatibility contract, including how an `openlease` release recognizes state written by earlier releases.
- Protects concurrent work on one machine. Cross-machine coordination remains normal Git/OpenSpec integration and is outside this change.

## Unresolved — Do Not Assume

No outcome-changing first-release decision remains. The first release intentionally requires explicit topology, affected claims, promotion, merge paths, strategies, and forced recovery; rejects cycles, multiple containment parents, missing authorities, and ambiguous identities; uses one proven-owned bounded projection per space; and does not include automatic discovery, automatic waiting or merging, ZPP activation/exec migration, or cross-machine coordination.
