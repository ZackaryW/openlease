## RENAMED Requirements

- FROM: `### Requirement: One breaking version-three extension contract`
- TO: `### Requirement: One breaking version-four extension contract`

## MODIFIED Requirements

### Requirement: One breaking version-four extension contract
OpenLease SHALL accept one current version-four extension registration contract that declares a stable extension identity, compatible contract version, optional configuration validator, a unique set of named operations, optional supported-event callbacks, and any explicitly supplied additional configuration codecs. OpenLease SHALL reject duplicate extension identities or operation names, unsupported events, missing callback operations, duplicate codec names, and incompatible contracts before invoking extension code.

The exported `ManagedConfiguration` type SHALL be the public protocol extending `ManagedMapping` for configuration-specific provenance and mutation operations. Bound extensions and extension invocations SHALL type their `config` member with that protocol, while `data` and `cache` SHALL retain the general managed-mapping contract. The concrete runtime implementation SHALL NOT be the public construction surface.

OpenLease SHALL NOT support version-three or version-two registration, the former resolver-only registration, reinterpret a resolver as an operation, decode a legacy extension contract, or dynamically discover registrations, operations, callbacks, or codecs. A host using an incompatible contract SHALL reinitialize or replace its integration rather than enter a compatibility path.

Registration SHALL NOT resolve configuration, invoke an operation, activate a callback, create managed state, run verification, or mutate lifecycle or Git state.

#### Scenario: Register independent version-four extensions
- **WHEN** a host explicitly registers compatible version-four `zpp.traits` and `zpp.behave` extensions with distinct operations
- **THEN** OpenLease exposes each declaration only through its exact extension identity and invokes neither extension during registration

#### Scenario: Type configuration through the public protocol
- **WHEN** a host or extension receives a bound extension or invocation
- **THEN** its configuration member exposes the public `ManagedConfiguration` protocol while data and cache expose the general managed-mapping contract

#### Scenario: Reject a version-three registration
- **WHEN** a host supplies the superseded version-three extension contract
- **THEN** OpenLease rejects construction with version-four guidance and performs no compatibility invocation

#### Scenario: Reject an invalid callback or codec registration
- **WHEN** a registration references an undeclared callback operation, unsupported event, duplicate codec, or incompatible contract version
- **THEN** OpenLease rejects the complete registration before configuration or extension code is accessed

### Requirement: Optional bounded lifecycle callbacks
OpenLease SHALL expose only lifecycle events enumerated by the current runtime contract. A registration MAY declare callback availability for those events, but neither registration nor configuration presence SHALL select a callback. Each lifecycle invocation or accepted plan SHALL explicitly identify every selected callback by extension identity, operation, event, mode, exact target, and owner-supplied input.

OpenLease SHALL accept callback input only within the public managed-value boundary, capture it as an immutable value when the callback is selected, and deliver that exact captured value as the invoked operation's input. OpenLease SHALL NOT interpret the input, infer it from extension configuration, derive a command from the selected operation, or permit caller mutation after selection to change planned or invoked behavior.

Each selected callback SHALL receive an immutable event record plus freshly resolved bound extension context. A callback SHALL receive no OpenLease lifecycle mutator, state repository, Git adapter, or authority to acquire or release leases, change topology or affected claims, select refs or strategies, stage files, create commits, merge or rebase, resolve conflicts, modify lifecycle records, finalize work, or invoke another extension implicitly.

Callbacks SHALL be observational unless the owning lifecycle contract explicitly supports and the accepted invocation selects a gating mode. Observational failures SHALL be recorded and reported without changing the owning lifecycle transition. Observational dispatch SHALL continue deterministically after an observational failure. A gating failure SHALL use only the owning lifecycle contract's documented predeclared stop behavior.

#### Scenario: Invoke a callback with explicit immutable input
- **WHEN** a host selects a callback with input `{"command": "bdd", "complete": true}` and later mutates its original input object
- **THEN** the selected operation receives the unchanged captured mapping as its invocation input without consulting extension configuration

#### Scenario: Ignore an available but unselected callback
- **WHEN** a supported event occurs and compatible callbacks are registered but none are selected
- **THEN** OpenLease performs the owning lifecycle's callback-free behavior and invokes no extension callback

#### Scenario: Run observational callbacks deterministically
- **WHEN** an accepted invocation selects several observational callbacks for one event
- **THEN** OpenLease invokes them in deterministic declared order with their respective captured inputs, reports every outcome including failures, and does not gate the lifecycle transition

#### Scenario: Apply only an explicitly supported gate
- **WHEN** an accepted lifecycle invocation explicitly selects gating mode for an event whose contract permits it
- **THEN** OpenLease displays the gate and its selected input before mutation and applies exactly that event contract's documented failure behavior
