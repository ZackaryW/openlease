## Why

OpenLease currently requires every caller to create and select a durable named space before ordinary workflow commands can establish their working context. Session-oriented hosts already know the current working checkout and need a lightweight default that does not leave empty durable spaces behind.

## What Changes

- Allow a caller with no explicitly selected space to resolve the current Git worktree plus an opaque host-session token into a session-scoped temporary space.
- Reuse the same temporary space within its owning session, or atomically reclaim a matching inactive disposable space from an ended session.
- Scaffold a new temporary space when no safely reusable match exists, while preserving explicit repository and authority topology rather than inferring relationships from the working directory.
- Remove a temporary space when its session ends only while it remains empty and disposable; retain it as durable state once it acquires leases, generated work, projections, space-scoped configuration, preparation evidence, blockers, or reconciliation debt.
- Preserve explicit `--space` and `OPENLEASE_SPACE` selection as the authoritative durable-space path.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `relational-workset-lifecycle`: Add session-scoped cwd selection, safe temporary-space reuse/reclamation, and promotion or cleanup rules.
- `collision-aware-workset-planning`: Ensure implicit temporary selection preserves the same logical lease and affected-claim boundaries as explicit spaces.

## Impact

- Public OpenLease lifecycle and optional CLI context resolution.
- Persisted space records and their backward-compatible state codec.
- Space creation, selection, session close, locking, preparation, projection, configuration, and reconciliation transitions.
- Unit, CLI integration, and capability-owned Behave coverage.

## Unresolved — Do Not Assume

None. The working contract is limited to cwd-based selection backed by an opaque session token, safe reclaim of inactive disposable state, and durable retention as soon as the space carries ownership, space-scoped configuration, or recovery evidence.
