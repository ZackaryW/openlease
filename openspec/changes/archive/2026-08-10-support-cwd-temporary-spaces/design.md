## Context

OpenLease persists durable named spaces and requires callers to select one before most workflow operations. A session-oriented host can instead provide an opaque token and its current working directory, but separate CLI invocations still need to resolve the same disposable draft without using a process ID or terminal as lease ownership. The current state schema has no temporary ownership or worktree-origin fields, and cwd must not weaken explicit topology, affected-claim, or lease rules.

## Goals / Non-Goals

**Goals:**

- Resolve an omitted explicit space from a canonical Git worktree and opaque host-session token.
- Make repeated resolution idempotent within one session and permit atomic reclaim of abandoned clean drafts.
- Promote any temporary record carrying ownership or recovery evidence to ordinary durable state.
- Preserve backward compatibility for existing state and explicit space selection.

**Non-Goals:**

- Inferring repositories, OpenSpec authorities, relationships, or affected claims from cwd.
- Treating a PID, TTY, shell, branch, or directory name as lease ownership.
- Automatically deleting leases, generated worktrees, projections, preparation evidence, blockers, handoffs, or reconciliation records.
- Replacing explicit named spaces for durable work.

## Decisions

### Persist a bounded temporary-space descriptor

Extend a space with an optional temporary descriptor containing the registered repository identity, canonical worktree root, and a one-way fingerprint of the opaque session token. A descriptor is required only while the space is disposable. Existing schema-version-three records decode as durable spaces with no descriptor.

This allows independent CLI invocations from one host session to resolve the same draft without persisting the raw token. Deriving ownership from a parent PID or TTY was rejected because those identifiers are neither stable across hosts nor valid lease owners.

### Resolve cwd through registered Git identity

Canonicalize cwd through Git to its worktree root and common-directory identity, then match that identity to exactly one registered repository. A nested cwd resolves to its containing worktree. No match or an ambiguous registration fails without creating state. The resolver associates only that registered repository; authority topology and affected claims remain explicit follow-up inputs.

Using a path prefix alone was rejected because symlinks, nested paths, and linked worktrees would make identity inconsistent with existing authority rules.

### Reuse or reclaim only a disposable matching record

Inside one serialized mutation, resolution first reuses a descriptor matching both the worktree and current token. Otherwise it may reclaim an inactive temporary descriptor for the same canonical worktree only when the record has no held leases, generated members, projection ownership, space-scoped configuration sources or pack attachments, preparation artifacts, blockers, handoff disposition, or reconciliation records. If no candidate is eligible, it creates a collision-safe temporary identifier and draft associated with the registered repository.

A matching record that carries durable evidence is preserved rather than adopted or overwritten. Creating a separate disposable draft keeps selection available while normal planning later reports any genuine authority conflict.

### Promote at the first durable boundary

Any atomic operation that grants a lease or records generated work, projection ownership, space-scoped configuration, preparation evidence, blockers, handoff disposition, or reconciliation debt clears the temporary descriptor in the same state transition. From that point the ordinary durable lifecycle applies and session closure cannot remove the space.

Session closure removes only temporary records that still satisfy the complete disposable predicate. A lost host session does not trigger unsafe asynchronous deletion; a later session may reclaim its clean record.

### Keep explicit selection authoritative

The CLI and library resolve a cwd temporary space only when no explicit space identifier was supplied. `--space` and `OPENLEASE_SPACE` retain their current behavior. The host-session token is selection context, not an authority claim, and all `affect`, `plan`, `lockable`, and `lock` rules run unchanged after resolution.

## Risks / Trade-offs

- [Abandoned clean temporary records can remain after a crashed host] → Reclaim them atomically on the next matching cwd session; never use timeout-based lease cleanup.
- [A session token could be exposed through persisted state] → Persist only a one-way fingerprint and return no raw token in status.
- [A worktree may be re-registered ambiguously] → Fail closed unless cwd resolves to exactly one registered repository identity.
- [Promotion checks can drift across lifecycle operations] → Centralize the disposable predicate and promotion helper over both space fields and external state references, then cover every durability-bearing transition with unit and BDD tests.

## Migration Plan

1. Add backward-compatible decoding from schema version three and encode the new temporary descriptor in the next schema version.
2. Add pure cwd resolution, disposable eligibility, identifier allocation, and promotion helpers behind lifecycle tests.
3. Expose implicit selection through the public lifecycle and optional CLI while preserving explicit selection precedence.
4. Roll back by leaving new records readable as durable state; never downgrade or delete a promoted record automatically.

## Open Questions

None.
