## 1. Behavior Contract

- [x] 1.1 Add capability-owned BDD scenarios proving disconnected registration succeeds during an unrelated lease and closure- or coverage-changing additions fail atomically.
- [x] 1.2 Add deferred-space scenarios proving unrelated graph expansion preserves promotion while relevant drift remains blocking.

## 2. Candidate Graph Safety

- [x] 2.1 Add focused fail-first unit tests for scoped topology footprints, affected-plan preservation, hierarchical conflict coverage, and existing-owner compatibility.
- [x] 2.2 Implement the minimum deterministic graph-safety comparison needed by topology mutations.

## 3. Lifecycle Integration

- [x] 3.1 Replace the global active-lease topology freeze with atomic candidate validation across repository, authority, containment, and dependency additions.
- [x] 3.2 Advance only current unaffected deferred graph baselines and preserve stale evidence after relevant drift.
- [x] 3.3 Return typed failure details while preserving graph generation, spaces, and leases on rejection.

## 4. Verification

- [x] 4.1 Run focused unit and capability BDD verification for safe topology expansion.
- [x] 4.2 Run the complete lint, format, test, and clean package-build gates.
