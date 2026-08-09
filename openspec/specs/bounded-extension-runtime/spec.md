# Bounded Extension Runtime Specification

## Purpose

Provides explicitly registered dependent-product extensions with named operations, optional bounded lifecycle callbacks, managed configuration/data/cache mappings, and structured outcomes without transferring OpenLease lifecycle authority or requiring OpenLease to understand extension schemas.

## Requirements

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

### Requirement: Explicit operation invocation with current bound context
A host invocation SHALL identify one registered extension, one declared operation, one exact configuration binding or existing space and target context, and one target shape accepted by the operation contract. OpenLease SHALL validate registration, operation, target, binding, writable authority, current configuration, and the extension's registered validator before invoking the handler. Failure in any preceding phase SHALL start no handler or managed mutation.

The handler SHALL receive opaque host input, an immutable target/event context, and narrow managed configuration, data, and cache mappings. OpenLease SHALL return a structured result containing extension and operation identity, target identity, state/configuration generations when applicable, participating binding identities and content digests, handler outcome, and actual managed-write dispositions. OpenLease SHALL NOT interpret extension-specific input, effective configuration meaning, or handler output schema.

#### Scenario: Invoke one named operation
- **WHEN** a host invokes a declared operation against a valid current bound target
- **THEN** OpenLease resolves the target's current extension configuration, validates it, invokes exactly the selected handler once, and returns its opaque value separately from runtime metadata

#### Scenario: Reject an unavailable operation before effects
- **WHEN** a host requests an operation absent from the selected extension registration
- **THEN** OpenLease reports the unavailable operation and starts no handler, configuration mutation, data write, cache write, callback, or lifecycle mutation

### Requirement: Optional bounded lifecycle callbacks
OpenLease SHALL expose only lifecycle events enumerated by the current runtime contract. A registration MAY declare callback availability for those events, but neither registration nor configuration presence SHALL select a callback. Each lifecycle invocation or accepted plan SHALL explicitly identify every selected callback by extension identity, operation, event, mode, and exact target.

Each selected callback SHALL receive an immutable event record plus freshly resolved bound extension context. A callback SHALL receive no OpenLease lifecycle mutator, state repository, Git adapter, or authority to acquire or release leases, change topology or affected claims, select refs or strategies, stage files, create commits, merge or rebase, resolve conflicts, modify lifecycle records, finalize work, or invoke another extension implicitly.

Callbacks SHALL be observational unless the owning lifecycle contract explicitly supports and the accepted invocation selects a gating mode. Observational failures SHALL be recorded and reported without changing the owning lifecycle transition. Observational dispatch SHALL continue deterministically after an observational failure. A gating failure SHALL use only the owning lifecycle contract's documented predeclared stop behavior.

#### Scenario: Ignore an available but unselected callback
- **WHEN** a supported event occurs and compatible callbacks are registered but none are selected
- **THEN** OpenLease performs the owning lifecycle's callback-free behavior and invokes no extension callback

#### Scenario: Run observational callbacks deterministically
- **WHEN** an accepted invocation selects several observational callbacks for one event
- **THEN** OpenLease invokes them in deterministic declared order, reports every outcome including failures, and does not gate the lifecycle transition

#### Scenario: Apply only an explicitly supported gate
- **WHEN** an accepted lifecycle invocation explicitly selects gating mode for an event whose contract permits it
- **THEN** OpenLease displays the gate before mutation and applies exactly that event contract's documented failure behavior

### Requirement: Managed extension data and cache mappings
An invoked operation or selected callback MAY receive durable-data and disposable-cache mappings confined to the selected extension's resolved namespaces. Reads SHALL return the current extension-owned value. An assignment or deletion SHALL validate the logical key, serializable value, ownership, and resolved path and SHALL atomically publish that single mutation where supported. OpenLease SHALL reject absolute paths, parent traversal, alternate namespace access, symlink escape, and replacement or deletion without exact recorded ownership.

Direct managed mutations SHALL NOT require a staging session or recovery journal. A completed direct mutation SHALL remain completed if the handler later fails, and the result SHALL report both facts truthfully. OpenLease MAY provide an explicitly entered optional batch for a bounded set of managed configuration/data/cache mutations; operations and callbacks SHALL NOT enter a batch implicitly, and a batch SHALL NOT claim atomicity over Git, subprocess, network, or arbitrary filesystem effects.

#### Scenario: Save one extension-owned record immediately
- **WHEN** a handler assigns a valid value through its durable-data mapping outside a batch
- **THEN** OpenLease confines and publishes that record before the assignment returns and creates no implicit staging journal

#### Scenario: Preserve a direct write after handler failure
- **WHEN** a handler completes a direct managed write and subsequently fails
- **THEN** OpenLease preserves the published record and reports both the completed write and failed handler

#### Scenario: Reject cross-namespace access
- **WHEN** an extension addresses another namespace, traverses beyond its root, follows an escaping symlink, or replaces unowned content
- **THEN** OpenLease rejects the mutation and preserves existing content

#### Scenario: Enter batching explicitly
- **WHEN** extension code explicitly opens a batch and completes a valid bounded mutation set
- **THEN** OpenLease applies the documented batch publication contract while direct mutations outside that block remain immediate

### Requirement: Durable structured invocation outcomes
OpenLease SHALL attempt to record a bounded outcome envelope for every invoked operation and selected callback. The envelope SHALL identify extension, operation or event, target, callback mode, relevant state and configuration generations, participating binding digests, handler status, each managed-write disposition, failure phase, and bounded diagnostics without copying the opaque handler value into lifecycle state. Outcomes SHALL be extension-namespaced, versioned, inspectable, and bounded by an explicit retention policy.

If outcome recording fails after a handler or managed effect ran, the returned result SHALL retain the known execution and write dispositions and report outcome-recording failure separately. OpenLease SHALL NOT claim that an already executed handler or published write was rolled back.

#### Scenario: Inspect a failed callback outcome
- **WHEN** a selected callback fails after receiving a resolved context and outcome recording succeeds
- **THEN** inspection exposes its extension, operation, event, target, context evidence, callback mode, failure phase, and write dispositions without interpreting its opaque payload

#### Scenario: Report outcome storage failure truthfully
- **WHEN** a handler and one direct write complete but recording their outcome fails
- **THEN** OpenLease reports the completed handler and write plus the distinct recording failure without duplicating the operation or claiming rollback

#### Scenario: Preserve unrelated lifecycle availability
- **WHEN** a manually invoked extension operation fails
- **THEN** unrelated lock, release, recovery, reconciliation, and configuration operations remain available

### Requirement: Extension code has no implicit lifecycle authority
Extension configuration, registered operations, callback availability, managed data, cache records, and operation outcomes SHALL NOT grant or imply authority to invoke an operation, select a callback, mutate OpenLease lifecycle state, or perform Git integration. Authority SHALL come only from the explicit host invocation and the owning lifecycle contract.

#### Scenario: Treat configuration as data rather than authority
- **WHEN** an extension configuration declares verification, runner, staging, commit, or merge settings
- **THEN** OpenLease exposes those values to the selected extension but starts no operation, callback, process, or Git mutation from the values alone
