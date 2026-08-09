## ADDED Requirements

### Requirement: One breaking version-three extension contract
OpenLease SHALL accept one current version-three extension registration contract that declares a stable extension identity, compatible contract version, optional configuration validator, a unique set of named operations, optional supported-event callbacks, and any explicitly supplied additional configuration codecs. OpenLease SHALL reject duplicate extension identities or operation names, unsupported events, missing callback operations, duplicate codec names, and incompatible contracts before invoking extension code.

The exported `ManagedConfiguration` type SHALL be the public protocol extending `ManagedMapping` for configuration-specific provenance and mutation operations. Bound extensions and extension invocations SHALL type their `config` member with that protocol, while `data` and `cache` SHALL retain the general managed-mapping contract. The concrete runtime implementation SHALL NOT be the public construction surface.

OpenLease SHALL NOT support version-two registration, the former resolver-only registration, reinterpret a resolver as an operation, decode a legacy extension contract, or dynamically discover registrations, operations, callbacks, or codecs. A host using an incompatible contract SHALL reinitialize or replace its integration rather than enter a compatibility path.

Registration SHALL NOT resolve configuration, invoke an operation, activate a callback, create managed state, run verification, or mutate lifecycle or Git state.

#### Scenario: Register independent version-three extensions
- **WHEN** a host explicitly registers compatible version-three `zpp.traits` and `zpp.behave` extensions with distinct operations
- **THEN** OpenLease exposes each declaration only through its exact extension identity and invokes neither extension during registration

#### Scenario: Type configuration through the public protocol
- **WHEN** a host or extension receives a bound extension or invocation
- **THEN** its configuration member exposes the public `ManagedConfiguration` protocol while data and cache expose the general managed-mapping contract

#### Scenario: Reject a version-two registration
- **WHEN** a host supplies the superseded version-two extension contract
- **THEN** OpenLease rejects construction with version-three guidance and performs no compatibility invocation

#### Scenario: Reject an invalid callback or codec registration
- **WHEN** a registration references an undeclared callback operation, unsupported event, duplicate codec, or incompatible contract version
- **THEN** OpenLease rejects the complete registration before configuration or extension code is accessed

### Requirement: Public configuration provenance snapshot
The managed configuration object exposed through a bound extension and an extension invocation SHALL provide a public `snapshot_record()` operation returning `EffectiveConfigurationSnapshot` with effective values together with every participating binding's identity, scope, canonical path, codec, layout, write authority, order, revision, selected mapping, content digest, and observed generation; per-key winning binding identities; and relevant lifecycle and configuration generations. Callers SHALL NOT need to cast to a private or concrete runtime implementation to obtain that record.

The existing values-only snapshot SHALL remain available for callers that do not need provenance. Both snapshot forms SHALL use the same current source-authoritative resolution and immutable managed-value contract.

#### Scenario: Explain one effective value
- **WHEN** a dependent extension requests the configuration provenance snapshot for a key supplied by several ordered bindings
- **THEN** the result identifies the winning binding and every participating binding with its digest and generation while preserving immutable values

#### Scenario: Request only effective values
- **WHEN** a caller uses the values-only snapshot operation
- **THEN** OpenLease returns the current immutable effective mapping without requiring the caller to consume provenance metadata

### Requirement: Explicit configuration mutations return dispositions
Managed configuration SHALL preserve automatic persistence through mapping assignment and deletion. It SHALL additionally expose `set(key, value)` and `delete(key)` operations that perform the same validation, conflict detection, namespace confinement, and atomic publication as their mapping equivalents and return the completed `WriteDisposition` directly.

A successful explicit mutation SHALL return the exact binding identity, path, prior digest, resulting digest, key, store, and disposition kind already recorded for that publication. A rejected explicit mutation SHALL raise the same structured failure as the equivalent mapping operation and SHALL NOT fabricate a successful disposition.

#### Scenario: Set and inspect one configuration value
- **WHEN** an extension explicitly sets a valid key through a writable managed configuration
- **THEN** the document is saved automatically and the call returns that publication's `WriteDisposition`

#### Scenario: Delete and inspect one configuration value
- **WHEN** an extension explicitly deletes an existing key through a writable managed configuration
- **THEN** the document is saved automatically and the call returns that deletion's `WriteDisposition`

#### Scenario: Preserve assignment ergonomics
- **WHEN** an extension assigns through `config[key]` instead of the explicit set operation
- **THEN** OpenLease retains the same automatic-save behavior without requiring a return value

### Requirement: Structured public configuration failures
Public managed configuration and direct-document operations SHALL distinguish read-only authority, extension validation, bound-path change, codec/decode, and same-key conflict failures through exported `ConfigurationReadOnly`, `ConfigurationValidationFailed`, `ConfigurationPathChanged`, `ConfigurationDecodeFailed`, and `ConfigurationConflict` error types. Each category SHALL remain an `InvalidRequest` for existing outcome and exit-status handling and SHALL expose a stable machine-readable identifier respectively equal to `configuration_read_only`, `configuration_validation_failed`, `configuration_path_changed`, `configuration_decode_failed`, or `configuration_conflict`.

Structured failures SHALL retain relevant non-secret context such as binding identity, codec, path, key, failure phase, and competing digests where available. A dependent library SHALL be able to select handling by public error type or stable identifier without parsing human-readable message text. Direct use of an individual codec MAY continue to expose its codec-level error; extension configuration entry points SHALL translate that failure into the public configuration-decode category.

CLI JSON for these failures SHALL include the same stable identifier in a top-level `code` field while retaining `outcome: "invalid_request"` and exit status 2. Adding the code SHALL NOT change human-readable error messages or make configuration failures equivalent to authority or ownership conflicts.

#### Scenario: Handle a read-only write without text matching
- **WHEN** a dependent product attempts an explicit or mapping mutation through a read-only configuration
- **THEN** it receives the public read-only configuration category and stable identifier while the document remains unchanged

#### Scenario: Handle invalid extension configuration
- **WHEN** an extension validator rejects an effective or candidate configuration
- **THEN** the caller receives the public validation-failed category with validation phase context and no unreported managed mutation

#### Scenario: Handle decode path and conflict failures distinctly
- **WHEN** configuration access respectively encounters invalid declared-codec content, a substituted bound path, or a changed same key
- **THEN** each failure exposes its distinct public category and stable identifier without requiring message parsing

#### Scenario: Emit a structured CLI configuration failure
- **WHEN** a CLI operation reports one of the public configuration failures as JSON
- **THEN** the envelope includes its stable top-level code while preserving the invalid-request outcome and exit status 2

### Requirement: Public conversion to plain managed values
OpenLease SHALL export `to_plain_managed_value` as a managed-value conversion helper that accepts supported immutable or mutable managed values and recursively returns ordinary dictionaries and lists while preserving supported scalar values. The returned structure SHALL contain no mapping proxies, codec round-trip containers, or tuples introduced solely for immutability and SHALL be suitable for downstream schema validation and serialization.

The helper SHALL validate the managed-value boundary and reject unsupported values rather than silently stringifying or otherwise changing their meaning. Conversion SHALL NOT mutate the source value or write configuration.

#### Scenario: Validate configuration with a downstream model
- **WHEN** a dependent product converts an immutable managed configuration snapshot to plain values
- **THEN** nested mappings and sequences become ordinary dictionaries and lists suitable for downstream model validation while supported scalars retain their values

#### Scenario: Reject a non-managed value
- **WHEN** a caller asks the public conversion helper to convert an unsupported object
- **THEN** OpenLease reports a managed-value validation failure without mutating the input

## REMOVED Requirements

### Requirement: One breaking version-two extension contract

**Reason**: The public configuration typing surface is deliberately cleaned up before ZPP depends on it, so the single supported extension contract advances to version 3.

**Migration**: Register extensions with contract version 3, type received configuration through the public `ManagedConfiguration` protocol, and do not instantiate the former exported concrete runtime class.
