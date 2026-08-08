## Context

See `proposal.md` for motivation and the `relational-workset-lifecycle` delta for the product contract. Current CLI construction converts an omitted worktree base into `<state-root>/worktrees`, and preparation derives destinations beneath a successor-specific directory. Durable members already record source and effective paths, but a preparing successor currently reserves its identity before it records all planned destinations.

Canonical behavior already requires complete preflight, durable preparation journaling, exact ownership evidence, safe rollback, explicit destination overrides, and path-independent logical authority. Relevant zmem history contains no worktree-placement decision; its only decision records explicit terminal attachment, which this change does not alter.

## Goals / Non-Goals

**Goals:**

- Make ordinary generated worktrees visually local to their source repositories.
- Allocate deterministic, monotonic-looking sibling names without relying on names for ownership.
- Reserve a multi-repository cohort before Git side effects using the existing state schema.
- Preserve safe automation overrides and every existing recorded path.

**Non-Goals:**

- Moving the machine-local coordination registry out of the home directory.
- Moving or renaming existing worktrees.
- Encoding successor names, lease states, or authority identities into paths.
- Adopting, deleting, or reusing unmanaged directories that resemble OpenLease names.

## Decisions

### Preserve an omitted worktree base as an actual default choice

The CLI and library SHALL retain `None` when no worktree-base override is supplied. Path planning can then distinguish default repository-adjacent behavior from an explicit base. Treating the state-root worktree directory as an implicit override was rejected because it recreates the behavior being removed.

### Allocate from the source directory basename

For source `parent/repo`, default candidates are `parent/repo-olease-1`, `parent/repo-olease-2`, and so on. With an explicit base, candidates are `<base>/repo-olease-<n>`. Repository IDs and successor names remain state metadata rather than path components. This makes the base-versus-managed distinction visible and keeps branch or session renames from destabilizing paths.

### Compute availability from three authorities

The allocator considers durable OpenLease reservations, filesystem existence including symbolic links, and Git's registered worktree paths. The lowest candidate absent from all three is selected. State proves OpenLease ownership; filesystem and Git observations protect unmanaged work and stale-but-still-registered paths.

### Reserve planned members before creating worktrees

The preparing successor record SHALL contain generated member entries with every planned effective path before the first Git operation. Existing preparation-artifact entries continue to identify completed side effects. This uses the current state shape: members represent the reserved cohort, while preparation artifacts distinguish creations that recovery may inspect or remove. A fresh allocator therefore sees paths reserved by an interrupted or concurrent preparation even before those paths exist.

The existing compare-and-swap state generation makes one concurrent reservation win. A stale contender fails before Git mutation and can be replanned by its caller. Holding the registry lock throughout Git operations was rejected because slow external processes would block all otherwise independent OpenLease state work.

### Fail closed after reservation

Git remains authoritative at creation time. If an external process occupies a path after reservation, preparation records the failure and applies existing proven-safe rollback rules. OpenLease never increments silently after partial cohort reservation because doing so would change the reviewed atomic plan.

### Grandfather exact recorded paths

No migration scans or moves existing worktrees. All later status, promotion, release, reconciliation, recovery, cleanup, and finalization operations continue from each member's recorded effective path. New allocations observe those old paths as occupied if they intersect a candidate.

## Risks / Trade-offs

- [A source parent may be unwritable] → Fail with the unavailable destination and direct automation to the explicit worktree-base override; do not fall back silently.
- [Unmanaged directories can imitate the suffix] → Treat names as hints only and require exact durable provenance for ownership or cleanup.
- [Stale Git worktree registrations can consume suffixes] → Skip them until the repository owner prunes or resolves the Git registration.
- [Concurrent planners can observe the same candidate] → Reserve the complete planned member set through generation-checked atomic state mutation before Git side effects.
- [Sibling paths may be spread across volumes for multi-repository work] → Preserve per-repository locality; state and the successor projection remain the cohort view.

## Migration Plan

1. Add fail-first planning and lifecycle coverage for adjacent naming, increments, multi-repository locality, overrides, unmanaged collisions, reservations, late races, and old paths.
2. Make the configured worktree base optional through the CLI and library boundary.
3. Add pure destination allocation using state, filesystem, and Git worktree observations.
4. Persist planned generated members in the preparing successor before side effects.
5. Route both `isolate` and `defer` through the new allocation while leaving existing recorded members untouched.
6. Update CLI documentation and run the complete governed behavior audit.

Rollback restores centralized allocation only for future worktrees. It SHALL preserve every exact path already recorded under either placement policy.
