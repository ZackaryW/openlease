## Context

See `proposal.md` for motivation. The current extension contract is version 2. `ManagedMapping` is the public structural type used for configuration, data, and cache, while the exported concrete `ManagedConfiguration` already carries richer configuration-only behavior. Configuration failures are split between `InvalidRequest`, `CodecError`, and one concrete conflict class, and direct document calls repeat coordinated scalar fields.

The earlier v2 decision remains authoritative for explicit registration, codecs, callbacks, and core lifecycle/Git ownership. This change advances only the public extension/configuration API boundary before ZPP depends on it.

## Goals / Non-Goals

**Goals:**

- Establish one clean version-3 public configuration protocol with provenance and result-returning mutation operations.
- Give libraries and CLI consumers stable typed configuration failures without message parsing.
- Provide one strict immutable binding specification shared by open and initialization entry points.
- Reuse current source-authoritative resolution, conflict, validation, confinement, and publication behavior.

**Non-Goals:**

- Change general data/cache mapping behavior or grant extensions lifecycle/Git authority.
- Infer codec or layout, migrate persisted state, or retain version-2 registration compatibility.
- Add extension introspection, a target enum, batch-result ergonomics, version reporting, release automation, or a new dependency.

## Decisions

### Make `ManagedConfiguration` the version-3 public protocol

Define `ManagedConfiguration` as a public protocol extending `ManagedMapping` with `snapshot_record()`, `set()`, and `delete()`. Type `BoundExtension.config` and `ExtensionInvocation.config` with it; keep their data/cache members typed as `ManagedMapping`. Rename the concrete runtime class behind a private implementation boundary and stop exposing its constructor as the public contract.

Advance `EXTENSION_CONTRACT_VERSION` to 3 and reject v2 registrations through the existing incompatible-contract path. Keeping the concrete class public or introducing a second protocol name was rejected because ZPP has not yet adopted the API and a clean semantic name now avoids a permanent concrete/protocol split.

### Share one mutation path

The concrete `set(key, value)` and `delete(key)` methods call the same internal mutation operation used by mapping assignment/deletion and return its `WriteDisposition`. `__setitem__` and `__delitem__` delegate to those methods and intentionally discard the result. Preserve `last_write` for existing convenience, but downstream code no longer needs it for the current call's result.

This keeps validation, same-key conflict detection, path confinement, candidate validation, atomic publication, write recording, and baseline refresh identical across both call styles.

### Publish one configuration-error hierarchy and code contract

Place a public configuration-error base beneath `InvalidRequest`, with exported subclasses `ConfigurationReadOnly`, `ConfigurationValidationFailed`, `ConfigurationPathChanged`, `ConfigurationDecodeFailed`, and `ConfigurationConflict`. Give every subclass its specified stable class-level and instance-visible `code` value while retaining `outcome = "invalid_request"` and exit status 2.

Translate failures at extension configuration entry points, not inside standalone codecs: direct codec use continues to raise `CodecError`, while binding, snapshot, validation, and mutation surfaces raise the public configuration category with structured details and exception chaining. Move or re-export the existing conflict class so its public import remains singular.

For CLI JSON, add top-level `code` only when an error exposes one. Preserve the existing operation, outcome, message, and details fields. Human-readable CLI output and non-configuration errors remain unchanged.

### Export strict plain-value conversion

Expose `to_plain_managed_value` from the package root. Validate the input against the managed-value contract, recursively copy mappings to `dict` and sequences to `list`, and preserve supported scalar values. The helper has no filesystem or lifecycle effects. Internal codec conversion may share its recursion, but codec-specific unwrapping SHALL occur before the strict public boundary rather than making arbitrary `unwrap()` objects public managed values.

### Add unambiguous binding-object overloads

Define frozen `ExtensionDocumentBinding` with extension identity, path, codec, `ConfigurationLayout`, writable flag, and optional repository path. Both direct open and initialization accept this object; initialization retains `initial`, `boundary`, and `create_parents` as operation-specific arguments.

Retain existing scalar signatures. When a binding object is supplied, reject simultaneous scalar binding fields instead of merging them. Normalize both call forms into the same internal specification before validation so results and failures cannot drift. Codec and layout remain mandatory fields and are never derived from the path.

## Risks / Trade-offs

- **[Version 2 hosts fail immediately]** → Provide version-3 migration guidance and keep the existing explicit incompatibility failure before extension code executes.
- **[Renaming the concrete implementation breaks direct instantiation]** → Treat direct construction as intentionally removed public behavior and cover all supported access through bound extensions/invocations.
- **[Error translation can lose context]** → Preserve structured binding/path/key/codec/digest details and exception chaining in every translation test.
- **[Two direct-binding call forms can diverge]** → Normalize both forms through one internal binding specification and run shared parameterized conformance tests.
- **[Public conversion and codec conversion accept different inputs]** → Keep the public helper strict and test round-trip codec containers only after codec-owned unwrapping.

## Migration Plan

1. Introduce version-3 protocols, binding value, error hierarchy, and public conversion helper.
2. Move the concrete configuration implementation private and update all returned annotations and runtime construction.
3. Route explicit and mapping mutations through one operation and translate configuration entry-point failures.
4. Add binding-object overloads while retaining scalar forms, then update documentation and examples.
5. Verify focused public API contracts, both Python 3.11 and current Python, complete unit/integration tests, and every mapped BDD target.

Rollback restores the version-2 public surface and removes the additive APIs; no persisted-state conversion is required.
