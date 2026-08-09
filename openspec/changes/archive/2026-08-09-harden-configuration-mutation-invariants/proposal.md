## Why

The bounded extension runtime passed ordinary tests while two writable-configuration edge cases still violated its canonical conflict and path-confinement contract, and its behavior root was omitted from governed complete verification. The mature fixes now need an explicit, auditable OpenSpec contract so absence baselines, bound-path identity, and complete target coverage cannot regress.

## What Changes

- Define an absent writable key as an observed baseline that participates in same-key conflict detection.
- Require a writable binding to retain its originally authorized canonical path and reject later symlink or path substitution before reading or publishing a mutation.
- Require each governed capability behavior root to be declared in both affected and complete-audit mappings, with shared runtime inputs mapped to every capability they can affect.
- Add executable regression coverage for both configuration edge cases while preserving the established provider-neutral ZPP runner.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `space-scoped-extension-configuration`: Make absent-key baselines and post-binding path substitution explicit parts of conflict-safe managed mutation.
- `behavior-feature-governance`: Make one-to-one affected/audit target coverage mandatory for every governed behavior root.

## Impact

Affected surfaces are the managed configuration runtime, its integration and BDD regressions, the canonical extension-configuration and behavior-governance specifications, and the committed `zpp.behave.yaml` target mapping. No public operation shape, persistence schema, dependency, ZPP provider, or workflow process changes.
