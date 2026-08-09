## Why

OpenLease already carries rich configuration provenance, mutation dispositions, immutable managed values, and explicit binding metadata internally, but dependent products cannot consume those guarantees through one stable typed public surface. ZPP traits and verification diagnostics would otherwise need concrete-class casts, string-matched failures, and duplicated conversion/binding code.

## What Changes

- **BREAKING** Advance the extension contract to version 3, make exported `ManagedConfiguration` the public protocol extending `ManagedMapping`, and move the concrete runtime implementation behind a private boundary.
- Expose a configuration-specific managed-mapping contract whose coherent snapshot includes effective values, binding provenance, digests, per-key winners, and lifecycle/configuration generations.
- Preserve automatic assignment/deletion while adding explicit `set` and `delete` operations that return the completed `WriteDisposition` directly.
- Publish structured configuration failure categories with stable machine-readable codes for read-only, validation, path-change, decode, and conflict failures; include the code in CLI JSON while preserving the existing outcome and exit status.
- Publish `to_plain_managed_value` for recursively converting immutable managed mappings/tuples into ordinary dictionaries/lists suitable for validation and serialization libraries.
- Add an immutable `ExtensionDocumentBinding` value object as an additive direct open/initialization call form while retaining the existing scalar argument forms.
- Keep codec and layout selection explicit; do not infer either from filenames or content.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `bounded-extension-runtime`: Expose configuration provenance, explicit mutation results, public managed-value conversion, and structured configuration failures through stable downstream-facing contracts.
- `space-scoped-extension-configuration`: Accept reusable typed direct-document binding specifications while retaining explicit codec/layout authority and automatic saving semantics.

## Impact

The public Python extension protocol advances to contract version 3. Exported types/helpers/errors, direct binding entry points, CLI error envelopes, documentation, and extension-runtime tests are affected. Existing scalar binding calls remain supported. No lifecycle/Git authority, state schema, codec inference, dynamic discovery, ZPP home resolution, provider choice, or workflow process changes.

## Explicitly Deferred

- Extension registration/operation/callback/codec introspection such as `describe_extension()`.
- Replacing free-form operation target strings with a public `TargetKind` enum.
- Returning batch commit dispositions directly from context-manager exit.
- Package/extension-contract version reporting and the repository-environment action of publishing a tagged release.

## Settled Decisions

- `ManagedConfiguration` becomes the public protocol in extension contract version 3; the concrete runtime implementation is private and version-2 registrations are rejected under the existing no-compatibility policy.
- Every structured configuration error exposes a stable library `code`, and CLI JSON includes that code while retaining `outcome: "invalid_request"` and exit status 2.
- `ExtensionDocumentBinding` overloads are additive. Existing scalar binding and initialization forms remain supported and are not deprecated by this change.

## Unresolved — Do Not Assume

None.
