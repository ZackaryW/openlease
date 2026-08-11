## Why

OpenLease currently rejects every authority-graph mutation whenever any lease is active, so unrelated repositories and authorities cannot be registered even though they cannot alter or conflict with the locked space. This global freeze contradicts the product's capability-scoped collision model and prevents independent work from being bootstrapped safely.

## What Changes

- Evaluate a proposed repository, authority, containment, or dependency addition against the complete accepted shapes and lease sets that it could affect instead of rejecting it solely because some lease exists.
- Accept an atomic graph addition when every locked space continues to resolve the same complete affected plan and every existing lease remains valid and mutually compatible.
- Reject the complete graph addition without advancing graph or state generations when it would change a locked space's affected plan, leave a required authority unleased, or invalidate an existing lease relationship.
- Let unrelated graph additions coexist with deferred spaces, while requiring promotion to reject topology drift that changes the deferred space's accepted affected closure rather than rejecting every unrelated graph-generation advance.
- Preserve explicit registration and relationship declaration; this change adds no automatic discovery, topology removal, or incremental mutation of a locked space's own declared shape.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `relational-workset-lifecycle`: Permit safe authority-graph expansion alongside existing locked and deferred spaces while retaining deterministic graph validation and scoped drift detection.
- `collision-aware-workset-planning`: Replace the global active-lease topology freeze with atomic validation that preserves every existing complete lease closure and rejects only graph additions that would invalidate one.

## Impact

- Changes repository and authority registration plus containment and dependency mutation in `src/openlease/lifecycle.py`.
- Changes deferred-space topology drift evidence and may require a backward-compatible persisted-state addition or derived structural evidence.
- Adds capability-owned BDD scenarios and focused lifecycle/core tests for disconnected additions, closure-changing additions, atomic rejection, and deferred promotion after relevant or irrelevant graph changes.
- Adds no dependency and does not change the public command names or explicit topology inputs.

## Unresolved — Do Not Assume

No outcome-changing product decision remains. The accepted boundary is behavioral: an addition is safe only when it preserves each locked space's complete resolved affected plan and the validity of all existing leases. The implementation may choose derived comparison or persisted scoped evidence, but unrelated global graph-generation movement alone must not block independent work or deferred promotion.
