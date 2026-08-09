## Why

Reconciliation callbacks cannot yet carry an explicitly selected dependent-product command, and cohort callbacks receive only the first completed repository's context. ZPP therefore cannot adopt OpenLease reconciliation without guessing verification intent or losing repository-specific configuration isolation.

## What Changes

- **BREAKING** Advance the extension contract from version 3 to version 4 so reconciliation callback selection includes explicit immutable input and cohort callback dispatch has repository-isolated fan-out semantics.
- Carry the exact owner-selected callback input through reconciliation planning, drift evidence, and invocation without interpreting or inferring it from extension configuration.
- Dispatch each selected `reconcile.after_cohort` callback only after all selected integrations complete, once per completed repository in deterministic reconciliation order, with both cohort and repository identity in its event and freshly bound repository context.
- Report every repository-specific cohort callback outcome while preserving the existing observational, non-gating lifecycle result.
- Keep intrinsic Git checks, integration authority, callback selection, and verification-command choice outside extension configuration.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `bounded-extension-runtime`: Define the version-four callback-selection input contract and exact opaque input delivery.
- `relational-workset-lifecycle`: Define callback planning evidence and repository-isolated after-cohort dispatch and reporting.

## Impact

- Public extension API: `EXTENSION_CONTRACT_VERSION`, `CallbackSelection`, and callback event/invocation behavior.
- Reconciliation planning and apply behavior in `src/openlease/lifecycle.py`.
- Extension contract and lifecycle unit/integration tests, BDD features, public documentation, and exports/version guidance where applicable.
- ZPP can explicitly select input such as `{"command": "bdd", "complete": true}` and receive one isolated post-cohort verification context per reconciled repository.

## Unresolved — Do Not Assume

None. This change does not add callback retries, post-mutation gates, command inference, cross-repository aggregate configuration, or lifecycle authority for extensions.
