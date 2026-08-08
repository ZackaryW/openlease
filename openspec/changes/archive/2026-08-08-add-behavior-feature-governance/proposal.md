## Why

Executable feature coverage loses useful ownership and affected-verification boundaries when every scenario binds through one repository-wide step module. OpenLease needs an explicit governance contract so capability changes can be selected, executed, and eventually cached without hidden dependencies on unrelated feature bindings.

## What Changes

- Establish capability-owned Behave roots as the unit of executable feature ownership and affected verification.
- Require each root to contain its own feature documents, hook surface, and step bindings without importing bindings from another capability root.
- Restrict shared behavior support to non-binding fixtures and helpers, and fan changes to shared inputs out to every dependent target.
- Require a committed, validated mapping from repository-relative impact paths to a closed set of capability targets, with conservative all-target fallback for unknown impact.
- Separate affected execution from an explicit complete audit, while keeping target boundaries suitable for provider caching without requiring a cache-capable provider.

## Capabilities

### New Capabilities

- `behavior-feature-governance`: Governs executable feature ownership, binding isolation, shared support, affected target mapping, and complete behavior audits.

### Modified Capabilities

None.

## Impact

- Affects the repository's `features/` layout, Behave support hooks, behavior runner, development commands, and committed `zpp.behave.yaml` mapping.
- Establishes verification architecture rather than changing the OpenLease runtime or public CLI behavior.
- Keeps Nx optional; the existing provider-neutral Python and Behave runner remains authoritative unless the repository deliberately establishes another provider.
