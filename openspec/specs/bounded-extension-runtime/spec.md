# Bounded Extension Runtime Specification

## Purpose

Provides explicitly registered dependent-product extensions with named operations, optional bounded lifecycle callbacks, managed configuration/data/cache mappings, and structured outcomes without transferring OpenLease lifecycle authority or requiring OpenLease to understand extension schemas.

## Requirements

### Requirement: One breaking version-two extension contract
OpenLease SHALL accept one current extension registration contract that declares a stable extension identity, compatible contract version, optional configuration validator, a unique set of named operations, optional supported-event callbacks, and any explicitly supplied additional configuration codecs. OpenLease SHALL reject duplicate extension identities or operation names, unsupported events, missing callback operations, duplicate codec names, and incompatible contracts before invoking extension code.

OpenLease SHALL NOT support the former resolver-only registration, reinterpret a resolver as an operation, decode a legacy extension contract, or dynamically discover registrations, operations, callbacks, or codecs. A host using an incompatible contract SHALL reinitialize or replace its integration rather than enter a compatibility path.

Registration SHALL NOT resolve configuration, invoke an operation, activate a callback, create managed state, run verification, or mutate lifecycle or Git state.

#### Scenario: Register independent current extensions
- **WHEN** a host explicitly registers compatible `zpp.traits` and `zpp.behave` extensions with distinct operations
- **THEN** OpenLease exposes each declaration only through its exact extension identity and invokes neither extension during registration

#### Scenario: Reject a former resolver-only registration
- **WHEN** a host supplies the superseded resolver-only contract
- **THEN** OpenLease rejects construction with current-contract guidance and performs no compatibility invocation

#### Scenario: Reject an invalid callback or codec registration
- **WHEN** a registration references an undeclared callback operation, unsupported event, duplicate codec, or incompatible contract version
- **THEN** OpenLease rejects the complete registration before configuration or extension code is accessed

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
