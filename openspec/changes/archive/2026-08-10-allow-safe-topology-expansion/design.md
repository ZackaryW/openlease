## Context

The four public topology mutations currently call `_ensure_graph_mutable`, which rejects whenever the state contains any lease. This protects locked affected closures but applies at global registry scope, preventing a distinct repository and authority component from being registered while unrelated work is locked.

Affected plans are derived deterministically from explicit claims and writable dependencies. Hierarchical lease conflicts are derived separately from containment ancestry. Locked spaces retain their accepted affected claim and exact held authority ids, while deferred spaces retain the graph generation accepted during preparation. The global generation is currently too coarse to distinguish relevant drift from an unrelated graph addition.

## Goals / Non-Goals

**Goals:**

- Admit disconnected topology additions without releasing unrelated leases.
- Reject any topology addition that changes a locked space's accepted topology, affected closure, conflict coverage, or lease validity.
- Keep candidate validation and persistence atomic under the existing state-generation mutation contract.
- Prevent unrelated graph additions from making deferred spaces unpromotable while retaining fail-closed behavior after relevant drift.

**Non-Goals:**

- Automatic topology discovery or registration.
- Topology removal or replacement.
- Incremental changes to a locked space's association or affected claim.
- Automatic acquisition, release, recovery, or reconciliation.
- Changes to cross-machine coordination.

## Decisions

### Validate one candidate graph instead of checking for any lease

Each topology operation will construct and structurally validate its complete candidate state first. A shared lifecycle guard will compare current and candidate graph safety for every owner represented in `state.leases` before the candidate is persisted.

For each locked owner, the comparison will cover:

- its explicit associated and affected topology footprint;
- its complete `AffectedPlan`;
- the hierarchy-derived conflict coverage of every held authority;
- equality between required and held authority ids; and
- compatibility with every other existing lease owner under the candidate graph.

The candidate is accepted only when all those observations are unchanged and valid. Comparing only `AffectedPlan` was rejected because a new containment edge can expand a held authority's exclusion coverage without changing its held ids. Checking only current pairwise conflicts was rejected because it would permit an unoccupied scope to be silently added to a locked owner's coverage.

### Keep explicit additions atomic with the existing state transaction

Baseline calculation, candidate construction, graph validation, active-owner validation, deferred-baseline handling, and generation advancement will execute inside the existing compare-and-mutate callback. A concurrent state change therefore causes ordinary stale-state retry or rejection rather than validating against an obsolete lease set.

The current `_ensure_graph_mutable` global predicate will be removed from repository registration, authority registration, containment, and dependency additions. All four paths will use the same candidate guard so registration and relationship behavior cannot diverge.

### Advance only current, unaffected deferred baselines

For each deferred space whose recorded graph generation equals the current state generation, OpenLease will compare its accepted scoped topology, affected plan, and conflict coverage before and after the candidate addition. When they are unchanged, the same atomic mutation advances that deferred space's recorded graph generation to the candidate generation. When they differ, its prior generation remains unchanged and promotion continues to fail closed.

An already-stale deferred space is never refreshed by a later unrelated mutation. This prevents a second graph update from erasing evidence of the earlier relevant drift and avoids a persisted-state schema change.

### Retain typed, side-effect-free rejection

Invalid graph structure continues to use the established graph-to-domain error translation. A lease-safety failure will report which active space and which safety dimension changed, while preserving the original graph, graph generation, spaces, and leases.

## Risks / Trade-offs

- **Candidate checks scale with active and deferred spaces** → The registry is machine-local and expected to remain bounded; favor deterministic complete validation over premature indexing.
- **A conservative topology footprint may reject a theoretically safe edge** → Require exact preservation for locked work and extend admissibility only with new accepted behavior and evidence.
- **Deferred baseline advancement could hide earlier drift** → Advance only a baseline that matched the immediately preceding global generation; never refresh an already-stale space.
- **Concurrent topology or lease mutation can invalidate preflight** → Perform validation inside the serialized compare-and-mutate transaction.

## Migration Plan

No state-schema migration is required. Existing locked and deferred records retain their current fields. After deployment, new safe graph additions use scoped validation; rollback restores the global freeze without requiring state conversion.

## Open Questions

None.
