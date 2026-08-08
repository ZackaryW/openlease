## 1. Prove Destination Behavior

- [x] 1.1 Add fail-first behavior coverage for first and incremented repository-adjacent destinations in `defer` and `isolate`.
- [x] 1.2 Cover multi-repository locality, explicit worktree-base placement, unmanaged matching paths, state reservations, Git-registered paths, and late destination races.
- [x] 1.3 Cover preservation of centralized paths already recorded in existing spaces and reconciliation debt.

## 2. Implement Collision-Safe Allocation

- [x] 2.1 Preserve an omitted worktree-base value through the CLI and public lifecycle while retaining explicit environment, option, and library overrides.
- [x] 2.2 Add pure lowest-positive-suffix allocation from source directory basenames using state, filesystem, symbolic-link, and Git worktree occupancy.
- [x] 2.3 Extend Git inspection narrowly to report registered worktree destinations without inferring OpenLease ownership.
- [x] 2.4 Reserve the complete cohort's planned generated members and effective paths in the preparing successor before any Git creation.
- [x] 2.5 Route both compatible `isolate` and non-lockable `defer` preparation through the new allocator and fail closed on stale reservations or late races.
- [x] 2.6 Keep status, promotion, release, reconciliation, recovery, cleanup, and finalization driven by each member's exact recorded path under either placement policy.

## 3. Document and Verify

- [x] 3.1 Document the separation between home-directory state, repository-adjacent default worktrees, explicit placement overrides, and name-versus-ownership evidence.
- [x] 3.2 Run the affected destination and lifecycle targets followed by the complete governed behavior audit.
- [x] 3.3 Run unit tests, lint, formatting, package build, strict OpenSpec validation, and compatibility checks against version-one state fixtures.
