## Context

See `proposal.md` for motivation. OpenLease currently uses Behave with four capability feature files, a common fixture layer, and a provider-neutral ZPP behavior mapping. Behave normally loads every module in one root's `steps` directory, so placing all bindings under one repository-wide root creates hidden discovery dependencies even if the command names individual feature files.

## Goals / Non-Goals

**Goals:**

- Make the discovery boundary, affected-verification boundary, and future cache boundary coincide at the capability root.
- Preserve reusable setup without permitting shared step registration.
- Keep complete verification available as an explicit audit independent from affected selection.
- Make unknown impact safe by selecting more verification, never less.

**Non-Goals:**

- Requiring Nx or any other cache implementation.
- Assigning one process or cache target to every individual scenario.
- Preventing equivalent natural-language steps from having root-local bindings.
- Changing OpenLease runtime, lease, worktree, or reconciliation semantics.

## Decisions

### Use one independently executable Behave root per capability

Each capability directory contains its feature documents, an `environment.py` hook surface, and a root-local `steps/` directory. This aligns what Behave discovers with what ZPP selects. Merely splitting one global step file into several files under a common `steps/` directory was rejected because Behave would still load all modules for every selected feature.

### Keep shared support below the step-registration layer

Reusable fixtures, Git setup, in-memory adapters, and assertion helpers live in a shared package. Capability steps import those ordinary functions, while the shared package never uses Behave step decorators. Importing step modules across roots was rejected because it recreates hidden target dependencies and makes isolated validation unreliable.

### Execute multiple roots through a literal argv runner

The repository-owned runner accepts one or more declared root paths and invokes Behave separately for each. ZPP expands only committed target values into the typed argv provider. Passing several roots directly to one Behave process was rejected because it can collapse discovery back to a common ancestor and reload unrelated bindings.

### Maintain separate affected and audit commands

The affected command maps capability and source inputs to the smallest justified target set. A second command always exposes the complete set for checkpoints and release confidence. Shared runner, configuration, fixture, and mapping inputs affect all targets; uncertain paths use ZPP's all-target fallback.

### Treat cacheability as boundary design, not a cache guarantee

Stable target names and explicit inputs are sufficient for a future cache provider to reason about independent results. The current provider-neutral runner performs selection but does not promise persistent result caching. Adding Nx solely for this governance change was rejected because provider adoption is a separate repository decision.

## Risks / Trade-offs

- [Root-local bindings can duplicate small assertion wrappers] → Share only undecorated helpers and prefer explicit ownership over hidden coupling.
- [Cross-cutting source files can select most or all targets] → Keep mappings evidence-based and conservative; optimize only when a narrower dependency is demonstrable.
- [A new feature may be placed in the wrong root] → Require target-map validation and isolated dry-run coverage during review.
- [Provider-neutral execution repeats setup between roots] → Accept the audit cost; affected runs avoid unrelated roots, and a cache provider can be adopted separately.

## Migration Plan

1. Inventory existing feature documents and assign each to one capability boundary.
2. Move each feature and its bindings into an independently executable root.
3. Extract only non-binding fixtures and helpers into shared support.
4. Eliminate cross-root step resolution by adding root-owned bindings where needed.
5. Declare stable affected and complete-audit targets in the committed behavior mapping.
6. Validate every root independently, then run the complete audit.

Rollback consists of reverting the layout, runner, and mapping together; partial rollback is not supported because discovery and impact boundaries must remain aligned.
