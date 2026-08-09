## Context

See `proposal.md` for motivation. The current runtime already coordinates and atomically replaces configuration documents, but it previously re-resolved writable paths at mutation time and represented baselines only for keys that were present. The established behavior runner is provider-neutral and already supports independent named targets.

## Goals / Non-Goals

**Goals:**

- Preserve the document identity authorized at binding across later reads and writes.
- Preserve explicit absence as part of each handle's observed writable-source baseline.
- Make behavior-target completeness mechanically visible in both affected and audit mappings.

**Non-Goals:**

- Introduce general filesystem ownership, follow mutable symlinks, or authorize arbitrary path replacement.
- Change codec semantics, public operation shapes, persistence schemas, ZPP providers, or workflow stages.
- Add a cache provider or claim cached verification.

## Decisions

### Keep authorization attached to the original canonical path

The runtime validates that the path authorized during binding still resolves to that exact path before a managed read and immediately before atomic publication. Publication uses the bound path rather than a newly resolved target. This rejects deterministic substitution and ensures a last-moment symlink race can at worst replace the link itself rather than write through it. Re-authorizing the newly resolved target was rejected because it silently expands the host's original authority.

### Retain a complete selected-mapping baseline per handle

Each handle records the selected writable mapping observed when it binds or explicitly refreshes. Mutation compares the current local value against that snapshot, using absence as a first-class state. A per-present-key cache was rejected because it cannot distinguish “never observed” from “observed absent” and refreshes too late for a newly created key.

### Extend the existing mapping without changing its provider

The bounded-runtime behavior root receives the same stable target identity in `bdd` and `bdd-audit`. Runtime and codec inputs also affect the existing space-configuration target. Replacing the argv provider or introducing Nx was rejected because target completeness does not require a provider migration.

## Risks / Trade-offs

- **[Path replacement that was previously followed now fails closed]** → Return a specific path-change failure while preserving both the substituted entry and its target.
- **[A stale handle can no longer overwrite a key created after an absent observation]** → Surface the same structured configuration conflict used for changed present values.
- **[Shared runtime edits select more than one BDD target]** → Keep the mapping conservative so all affected capability contracts execute.

## Migration Plan

No persisted-state or consumer migration is required. Validate the existing provider-neutral mapping, run focused regressions, execute the complete mapped audit, synchronize the two modified capability deltas, and archive the corrective change. Rollback is the ordinary source/configuration revert; no state conversion is involved.
