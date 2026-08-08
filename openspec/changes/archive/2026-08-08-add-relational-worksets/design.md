## Context

See `proposal.md` for motivation and the two capability specs for the public contract. OpenLease begins as a local Python package and must coordinate durable state, Git worktrees, and bounded OpenSpec workset projections without treating any of those physical representations as logical lease identity.

## Goals / Non-Goals

**Goals:**

- Keep graph, closure, conflict, boundary, preparation, and reconciliation planning pure and deterministic.
- Serialize every durable mutation and reject stale plans.
- Journal multi-repository side effects before publishing a successor.
- Keep the importable lifecycle authoritative and the optional CLI thin.

**Non-Goals:**

- Cross-machine locking, editor or shell enforcement, automatic relationship discovery, conflict auto-resolution, and ZPP workflow execution.
- Reimplementing Git refs/worktrees or the OpenSpec workset protocol.

## Decisions

### Versioned immutable aggregate

Persist one versioned JSON aggregate containing repository and authority identities, relationships, spaces, leases, projection ownership, preparation artifacts, and reconciliation debt. Frozen slotted dataclasses and strict codecs make equality and structured output deterministic. A `filelock` inter-process lock plus observed-generation comparison and atomic replacement prevents partial or stale local mutations. A database or ORM would add deployment and migration complexity without improving this machine-local workload.

### Logical identity independent of worktree paths

Use Git's common directory as linked-worktree repository identity and repository-relative paths as authority identity. Parent edges affect conflict coverage without becoming leases; writable dependency edges expand the held closure, while read-only edges remain context. A general graph dependency is unnecessary for these bounded validations and traversals.

### Pure planning above narrow adapters

Keep closure resolution, hierarchy conflicts, boundary audits, preparation plans, rollback classification, dependency ordering, and complete reconciliation-path validation free of side effects. Use narrow shell-free adapters for Git and OpenSpec. Git remains authoritative for refs, dirty state, worktree creation, merge previews, merge, and rebase; OpenSpec remains authoritative for workset operations.

### Proven-owned projections

Treat an OpenSpec workset as an opening projection, never as lease evidence. Store the expected ordered members and structural fingerprint in OpenLease state. Replace or remove the projection only when the live workset still matches; preserve unmanaged or modified worksets.

### Affected-only successor preparation

Plan one generated worktree per distinct repository in the affected writable closure and keep all other associations pinned. Preflight deterministic destination collisions, reserve a successor and journal, then record each side effect. Publish only after every worktree and the owned projection exist. When cleanup cannot prove safety, retain a non-writable `preparation_failed` record and artifacts.

### Explicit reconciliation debt

Release removes leases and an intact owned projection but preserves generated branches and worktrees as debt. Reconciliation accepts a complete later source-to-destination mapping, records current destination commits, orders providers before consumers by default, applies one repository at a time, verifies each completed destination and the whole selected cohort, and stops at the first Git conflict. Rebase means rebase the generated source and then fast-forward the still-pinned destination.

### Explicit terminal attachment

`--space` and `OPENLEASE_SPACE` select a durable space. `session attach` returns the environment mapping because a child CLI process cannot mutate its parent shell. Process IDs and TTYs never own leases, and terminal loss never expires them.

## Risks / Trade-offs

- [Multi-repository effects are not one filesystem transaction] → Journal ownership before side effects, publish last, and retain uncertain artifacts.
- [Git and OpenSpec output can evolve] → Keep parsing in narrow adapters and fail closed on unknown shapes.
- [Cooperative local locking cannot stop arbitrary writes] → State the safety boundary and audit every observable OpenSpec path before release or reconciliation.
- [A destination can move after reconciliation planning] → Record its commit and reject application when it no longer matches.
- [Windows path aliases differ textually] → Resolve identity through Git and filesystem identity rather than raw path spelling.

## Migration Plan

This is the initial release. Install the base library or optional CLI, choose an isolated machine-local state root, register topology explicitly, and create new spaces. State schema changes must be versioned and rejected when unsupported. Rollback consists of using the prior package against its compatible state or preserving the state root and generated work while upgrading; OpenLease never deletes unproven work to force compatibility.
