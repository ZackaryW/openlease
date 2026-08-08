## Why

OpenLease currently defaults generated worktrees into its machine-local state directory, separating working copies from the repositories they extend and making ordinary OpenLease-managed work harder to recognize in repository browsers and Git clients. Generated worktrees should instead appear beside their registered source checkout with a stable visible ownership marker, while the home-directory registry continues to coordinate exact ownership and collision safety.

## What Changes

- Change the default destination for every newly generated `isolate` or `defer` worktree from the OpenLease state root to a sibling of that repository's registered source checkout.
- Derive names as `<source-directory>-olease-<n>`, where `n` is the lowest available positive integer for that source location.
- Reserve and record exact chosen destinations before Git side effects, skipping any candidate occupied in durable state, the filesystem, or Git's worktree registry and failing closed on a late race.
- Treat the `-olease-<n>` suffix as a human-visible managed-worktree hint only; exact durable provenance remains the ownership authority.
- Preserve the explicit worktree-base override for isolated automation, using the same collision-safe `<source-directory>-olease-<n>` naming within the selected base.
- Preserve every previously recorded generated worktree at its existing path; this change does not relocate or adopt existing work.
- Keep the default shared coordination registry at `~/.openlease`; only generated checkout placement changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `relational-workset-lifecycle`: Define repository-adjacent default placement, visible managed naming, reservation, collision handling, overrides, and compatibility for generated worktrees.

## Impact

- Changes the default path planning used by `isolate` and `defer`, associated CLI environment defaults, preparation journaling, and worktree-related behavior coverage.
- Does not change logical repository or OpenSpec authority identity, lease compatibility, affected-closure membership, reconciliation, or the location of machine-local state.
- Existing state already records exact source and effective paths, so no state-schema migration is required.

## Unresolved — Do Not Assume

No outcome-changing decision remains. The source directory name, nearest available positive suffix, exact ownership evidence, explicit override behavior, and preservation of existing worktrees are fixed by this change.
