# Space-Scoped Extension Configuration Specification

## Purpose

Provides dependent products with deterministic, read-only extension contexts and configuration layers derived from durable OpenLease spaces, nested OpenSpec authorities, effective worktrees, and explicitly appointed sources.

## Requirements

### Requirement: Explicit host-owned extension registration
OpenLease SHALL accept extensions only through explicit registration by the dependent host application. Every registered extension SHALL have a stable exact identity and the one current contract version. OpenLease SHALL NOT discover or execute arbitrary globally installed extension code, accept the former resolver-only registration, or let one registered extension read another extension's shared namespace, dedicated binding, data, or cache through the extension API.

#### Scenario: Register a dependent product extension
- **WHEN** a host constructs OpenLease with one compatible current explicitly identified extension
- **THEN** that extension becomes available through its namespace without making OpenLease depend on the host product or invoking extension code

#### Scenario: Reject an incompatible duplicate or former extension
- **WHEN** a host registers duplicate identities, an unsupported contract, or the former resolver-only shape
- **THEN** OpenLease rejects the complete extension set before resolving configuration or invoking code

### Requirement: Immutable space extension context
An extension-context request SHALL name one existing durable space and one explicit target repository or OpenSpec authority scope. OpenLease SHALL provide an immutable view containing the space identity, effective and source member paths, access roles, logical authority identities, parent-child and dependency relationships, and recorded branch and commit provenance relevant to that target. Generated members SHALL use their recorded effective worktree paths, while pinned members SHALL use their exact recorded context paths.

Extension resolution SHALL NOT grant mutation authority. An extension SHALL NOT acquire or release leases, change associations or affected claims, alter topology, select worktree destinations, mutate reconciliation state, or modify OpenLease state through lifecycle callbacks.

#### Scenario: Resolve context in an isolated successor
- **WHEN** a host requests extension context for an authority whose repository is generated in a successor space
- **THEN** OpenLease returns that authority and its configuration context against the successor's recorded effective worktree without changing the space

#### Scenario: Keep lease operations independent
- **WHEN** an extension is unavailable, invalid, or fails while resolving advisory context
- **THEN** the extension request fails without changing the selected space and without preventing independent lock, release, recovery, or reconciliation operations

### Requirement: Ordered namespaced configuration scopes
OpenLease SHALL plan extension configuration in machine, attached-pack, direct-space, repository, and selected OpenSpec authority root-to-child order. Pack bindings SHALL follow attachment order, direct-space bindings SHALL follow all packs, a more specific child scope SHALL follow its parent, and one child's binding SHALL NOT participate in a sibling target.

For each planned binding, OpenLease SHALL decode its declared YAML, TOML, JSON, or explicitly registered codec and select its shared or dedicated extension mapping. It SHALL create the effective configuration by shallow top-level key overlay in planned order: a later value replaces an earlier value for the same key, and a nested mapping or sequence is one replaceable value rather than an implicit deep merge. OpenLease SHALL expose source identity, scope, order, codec, layout, content digest, selected mapping, and per-key winning provenance. The extension SHALL retain ownership of schema validation, defaults, required keys, activation, and value meaning.

#### Scenario: Resolve root and child authority configuration
- **WHEN** a space contains machine, attached-pack, direct-space, repository, root-authority, child-A, and child-B bindings and the host targets child A
- **THEN** the effective mapping overlays machine through child A in order and excludes child B

#### Scenario: Replace rather than deep merge
- **WHEN** two participating bindings define the same key with nested mapping values
- **THEN** the later complete nested value wins and OpenLease does not recursively combine their child keys

#### Scenario: Keep product semantics opaque
- **WHEN** selected mappings contain extension-specific runner, activation, callback, or implementation settings
- **THEN** OpenLease overlays generic keys but neither validates their product meaning nor activates behavior from them

### Requirement: Reusable space configuration packs
OpenLease SHALL let a host define a reusable namespaced configuration pack and attach an explicit ordered set of packs to a space. A pack SHALL supply configuration rather than lease identity: attaching or removing a pack SHALL NOT create a child space, acquire an authority, or change the space's affected claim. The resolved context SHALL identify every participating pack and its observed configuration generation.

#### Scenario: Replace a downstream profile with a space pack
- **WHEN** a dependent product attaches a reusable trait-configuration pack to a selected space
- **THEN** the pack participates between machine and repository configuration without requiring the dependent product to resolve a separate profile home

#### Scenario: Keep configuration scope separate from work ownership
- **WHEN** root, child A, and child B authorities have different configuration scopes inside one space
- **THEN** those scopes remain independently resolvable without becoming lease-bearing subspaces

### Requirement: Live source-authoritative configuration
OpenLease SHALL re-evaluate every participating binding whenever a host reads managed configuration, snapshots a bound mapping, invokes an operation, or dispatches a selected callback. It SHALL resolve current bytes through the recorded path, codec, and layout and SHALL report the observed generation and content digest. A source edit SHALL participate in the next access even while a selected space is locked, without requiring refresh or advancing lifecycle or graph generations.

OpenLease SHALL NOT serve stale effective content when a current source is missing, unreadable, malformed, unsafe for its codec, invalid for its declared layout, or repeatedly changes during resolution. Such failure SHALL fail only that configuration access or extension invocation without changing the selected space, leases, affected claim, topology, worktree records, or reconciliation state.

#### Scenario: Observe a live edit while locked
- **WHEN** an attached YAML, TOML, or JSON binding changes while its selected space remains locked and the host reads configuration again
- **THEN** OpenLease returns the newly decoded effective mapping with a new digest without refreshing or changing the lease

#### Scenario: Refuse stale fallback
- **WHEN** a previously resolved binding becomes missing, unreadable, malformed, or repeatedly changes before a later access
- **THEN** that access fails instead of returning cached content while independent lifecycle operations remain available

### Requirement: Explicit custom configuration-source paths
OpenLease SHALL let a host appoint an existing readable custom path as a current configuration source at machine, space, repository, or OpenSpec authority scope. The host SHALL name extension identity, codec, layout, and read-only or writable authority explicitly. OpenLease SHALL canonicalize and validate the complete binding and SHALL reject missing, unreadable, malformed, ambiguous, or unsafe sources without partial state mutation.

When the path is contained by a registered repository, OpenLease SHALL retain a logical repository-relative binding and resolve it beneath the selected space member's current effective checkout. When external to every registered repository, OpenLease SHALL retain its exact canonical machine-local path. A read-only binding SHALL never rewrite source content. A writable binding SHALL authorize only managed mutation of the selected shared namespace or complete dedicated document under the conflict-safe atomic contract; it SHALL NOT establish repository membership, authority ownership, a lease, or general filesystem ownership.

#### Scenario: Follow a repository source into a generated worktree
- **WHEN** a repository-scoped managed source is appointed beneath a registered source checkout and the selected space uses a generated worktree
- **THEN** OpenLease resolves the same repository-relative source beneath the generated effective checkout with its recorded codec, layout, and write authority

#### Scenario: Retain an external read-only source
- **WHEN** a host appoints a read-only source outside every registered repository
- **THEN** OpenLease resolves that exact canonical path without associating, leasing, adopting, or rewriting it

#### Scenario: Mutate only an authorized namespace
- **WHEN** a host explicitly appoints a writable shared source for one extension
- **THEN** managed assignment may change only that extension's root mapping while every unrelated namespace remains outside its mutation authority

#### Scenario: Reject an unavailable or invalid custom source
- **WHEN** a host appoints a missing, unreadable, malformed, or layout-incompatible existing source
- **THEN** OpenLease rejects the complete binding without retaining a partial configuration record or rewriting the path

### Requirement: Namespaced extension storage resolution
For each explicitly registered extension, OpenLease SHALL resolve separate configuration, data, and cache roots. Default roots SHALL be namespaced beneath the selected machine-local OpenLease state root, while a host MAY override each root independently or place them beneath one custom product root. OpenLease SHALL canonicalize roots, expose provenance, and keep extension namespaces distinct even when they share a host root.

OpenLease lifecycle state SHALL store only current configuration binding metadata and references required by its own contract; decoded configuration values, opaque operation results, and extension payloads SHALL remain outside lifecycle state. Selecting a custom root SHALL grant no destructive authority. A direct or scope-bound writable configuration binding SHALL grant managed authority only over its selected namespace/document, while data and cache replacement or removal SHALL require exact recorded extension ownership.

#### Scenario: Resolve storage under an overridden state root
- **WHEN** isolated automation supplies an explicit OpenLease state root and binds an extension
- **THEN** configuration metadata plus extension-namespaced data and cache roots resolve beneath that root without a product-specific home resolver

#### Scenario: Preserve a dependent product home
- **WHEN** ZPP selects `.zpp` as its product root
- **THEN** OpenLease resolves current extension configuration, data, cache, and core state locations beneath that root while ZPP does not independently resolve competing extension-storage paths

#### Scenario: Override extension roots independently
- **WHEN** a host appoints distinct current configuration, durable data, and disposable cache locations
- **THEN** OpenLease preserves their separate roles, namespace boundaries, provenance, and mutation authorities

### Requirement: Dependency configuration isolation
An OpenSpec dependency edge SHALL remain relationship context and SHALL NOT implicitly import the provider authority's extension configuration into the consumer's scope. A host MAY make a separate explicit context request for the provider authority, preserving the provider's own scope chain and access role.

#### Scenario: Keep provider traits out of a consumer scope
- **WHEN** repo 2 depends on an OpenSpec authority hosted by repo 3 and extension context targets repo 2
- **THEN** the result reports the dependency but excludes repo 3 authority configuration unless the host explicitly requests that provider scope

### Requirement: Explicit YAML TOML and JSON configuration codecs
OpenLease SHALL provide built-in configuration codecs named `yaml`, `toml`, and `json`. Every current configuration binding SHALL record one exact codec name and one exact document layout; OpenLease SHALL NOT infer a legacy mode from document content or silently fall back to another codec after a declared codec rejects a document.

Each built-in codec SHALL accept a root mapping with string keys and values representable by the current managed value contract. YAML SHALL use safe data-only semantics and reject duplicate keys, custom tags, non-string mapping keys, and ambiguous merge behavior. JSON SHALL reject duplicate object keys, non-object roots, non-finite numbers, and trailing content. TOML SHALL reject invalid syntax and a selected namespace that is not a table. Format errors SHALL identify the binding and codec and SHALL occur before extension validation, operation invocation, or mutation.

A host MAY explicitly register an additional uniquely named codec as part of the extension runtime construction. OpenLease SHALL NOT discover codecs from packages, entry points, filenames, or configuration. An additional codec SHALL implement the same root-mapping, validation, rendering, conflict, and atomic-publication contract as a built-in codec.

#### Scenario: Decode each built-in format
- **WHEN** three valid bindings explicitly select YAML, TOML, and JSON and each resolves a mapping for the selected extension
- **THEN** OpenLease supplies equivalent managed mapping values with each binding's format and digest provenance

#### Scenario: Reject ambiguous serialized input
- **WHEN** a YAML or JSON binding contains a duplicate key, unsafe YAML tag, non-string mapping key, non-finite JSON number, or trailing JSON value
- **THEN** OpenLease rejects the binding before exposing configuration or invoking extension code

#### Scenario: Reject format fallback
- **WHEN** a binding declared as JSON contains bytes that are valid YAML but invalid JSON
- **THEN** OpenLease reports a JSON configuration error and does not retry the bytes through the YAML codec

### Requirement: Shared and dedicated namespace layouts
Every configuration binding SHALL declare either `shared` or `dedicated` layout. In `shared` layout, the root mapping SHALL contain zero or one value under the exact registered extension identity, and a present value SHALL be a mapping. OpenLease SHALL expose only that selected mapping to the extension and SHALL preserve every other root entry during mutation. Dots in an extension identity SHALL remain literal key characters rather than nested-path separators; TOML serialization SHALL quote such identities where required.

In `dedicated` layout, the complete root mapping SHALL belong to the binding's one recorded extension identity and SHALL be exposed without an additional wrapper. A dedicated binding SHALL never be addressable by another extension even if its root mapping contains a key equal to another extension identity.

The same extension MAY participate through shared and dedicated bindings at different ordered scopes. Their selected mappings SHALL use the same deterministic overlay contract. A single binding SHALL NOT switch layouts after creation without explicit replacement and complete revalidation.

#### Scenario: Select one namespace from a shared document
- **WHEN** one shared document contains mappings for `extension-a` and `extension-b` and the binding selects `extension-a`
- **THEN** OpenLease exposes only the `extension-a` mapping and preserves `extension-b` during any authorized write

#### Scenario: Preserve a dotted identity as one TOML key
- **WHEN** a shared TOML document binds extension identity `zpp.behave`
- **THEN** OpenLease selects the exact quoted table `["zpp.behave"]` and does not treat `[zpp.behave]` as the same namespace

#### Scenario: Bind a complete dedicated YAML document
- **WHEN** a dedicated YAML binding assigns a root-level `version` and `commands` mapping to extension identity `zpp.behave`
- **THEN** the extension receives `version` and `commands` directly while no YAML wrapper key is required

### Requirement: Bound configuration provides automatic retrieval and saving
A host SHALL be able to bind a registered extension to an existing space and target with an exact writable source identifier, or to one invocation-scoped direct document binding. The resulting `config` object SHALL behave as a managed mutable mapping: reading SHALL resolve current effective values, and assigning or deleting a key SHALL update the selected namespace in the writable binding without an explicit load or save call.

Binding without writable authority SHALL provide a read-only mapping. A scope selector MAY be offered as shorthand only when it identifies exactly one eligible writable source; ambiguous or missing writable selection SHALL fail before mutation. A write to a lower-precedence binding SHALL NOT erase or override a later source, and subsequent effective reads SHALL continue to apply normal ordering.

Mapping snapshots and complete iteration SHALL observe one coherent source generation. Returned nested mappings and lists SHALL be immutable or defensive values; mutating a retrieved nested Python object SHALL NOT imply persistence. Nested changes SHALL be saved by assigning a replacement value through the managed mapping.

#### Scenario: Assign and save without a save call
- **WHEN** a bound extension executes `extension.config["some-config"] = 1` with one exact writable binding
- **THEN** OpenLease publishes that key in the binding's selected namespace and returns mutation provenance without requiring `load` or `save`

#### Scenario: Retrieve current effective configuration
- **WHEN** extension code reads a key or requests a configuration snapshot
- **THEN** OpenLease resolves the current ordered bindings and returns the effective value plus coherent provenance without serving a stale prior snapshot

#### Scenario: Reject ambiguous write selection
- **WHEN** several writable bindings match a requested scope and no exact source is selected
- **THEN** OpenLease rejects mutation without choosing a source or changing a document

#### Scenario: Preserve higher-precedence shadowing
- **WHEN** a host writes a key to a lower-precedence binding while a later source defines the same effective key
- **THEN** the lower binding is saved but the next effective read continues to return the later value with both sources represented in provenance

#### Scenario: Require replacement for a nested mutation
- **WHEN** a caller mutates a nested defensive value without assigning it back through `config`
- **THEN** no configuration document changes and a later read returns source-authoritative content

### Requirement: Conflict-safe atomic document mutation
Before each configuration mutation, OpenLease SHALL acquire coordination for the canonical document path, read and decode the complete current document, and compare the selected key's current local value with the caller's observed baseline. The observed baseline SHALL distinguish an absent local key from every present value. If only unrelated keys or namespaces changed, OpenLease SHALL reapply the requested mutation to the current document. If the same local key changed, including creation after the caller observed it absent, OpenLease SHALL report a conflict rather than silently overwrite the competing value.

OpenLease SHALL render the complete updated document through its declared codec, write a temporary sibling, and atomically replace the prior document where the platform supports replacement. Failure before publication SHALL preserve the prior document. Mutation SHALL preserve unrelated shared namespaces and semantically preserve all unrelated values; YAML and TOML codecs SHALL also preserve comments and human-authored structure to the extent defined by their round-trip codec contract. A mutation result SHALL identify binding, codec, layout, canonical path, prior digest, and resulting digest.

Coordination SHALL be by canonical document path rather than binding identity, so different extensions and bindings referencing the same file cannot overwrite one another. A writable binding SHALL retain the exact canonical document path authorized when it was created. Before a later managed read or publication, OpenLease SHALL reject traversal, symlink substitution, or any other replacement that causes that bound path to resolve to a different target. Rejection SHALL preserve both the substituted path and its target and SHALL NOT publish through the replacement.

#### Scenario: Rebase an unrelated extension edit
- **WHEN** `extension-b` changes its namespace after `extension-a` observed a shared document and before `extension-a` publishes a different key
- **THEN** OpenLease reapplies the `extension-a` mutation to current content and preserves the completed `extension-b` change

#### Scenario: Reject a same-key conflict
- **WHEN** the exact writable local key changes after the caller's baseline and before publication
- **THEN** OpenLease reports a conflict, preserves the competing content, and does not apply last-writer-wins replacement

#### Scenario: Reject creation after an absent baseline
- **WHEN** two writable handles observe the same local key as absent and the first handle creates it before the second publishes a different value
- **THEN** OpenLease treats the creation as a same-key conflict, preserves the first value, and rejects the second publication

#### Scenario: Reject a bound path replaced by a symlink
- **WHEN** an authorized writable document path is replaced after binding by a symlink to another document
- **THEN** OpenLease rejects the managed mutation, preserves the symlink and external document, and publishes no content through the replacement

#### Scenario: Preserve the document after publication failure
- **WHEN** encoding, temporary-file writing, validation, or replacement fails before atomic publication completes
- **THEN** the previously published document remains authoritative and temporary owned artifacts are safely reported or removed

### Requirement: Invocation-scoped direct document binding
A host SHALL be able to create an invocation-scoped binding for one exact canonical configuration document without creating a space, repository, authority, pack, topology edge, lease, persistent configuration-source record, or lifecycle generation. The host SHALL explicitly supply extension identity, codec, layout, path, and read-only or writable authority.

Opening an existing direct document SHALL validate it before returning a mapping. Creating a missing direct document SHALL require an explicit initialization request, writable authority, codec, layout, and initial mapping; OpenLease SHALL create no parent outside the exact authorized boundary and SHALL reject replacement of any pre-existing path. A direct binding SHALL participate only in the operation or host session that received it and SHALL not become global configuration implicitly.

#### Scenario: Open a repository behavior document directly
- **WHEN** a host opens an existing repository-root `zpp.behave.yaml` as dedicated YAML for `zpp.behave`
- **THEN** OpenLease returns the complete root mapping through that namespace without requiring an OpenLease space or topology mutation

#### Scenario: Initialize a missing dedicated document explicitly
- **WHEN** a host explicitly initializes an absent writable dedicated YAML document with a valid initial mapping
- **THEN** OpenLease atomically creates exactly that document and returns its current binding provenance

#### Scenario: Keep a direct binding invocation-scoped
- **WHEN** a direct document session ends
- **THEN** no persistent OpenLease source binding, scope attachment, topology record, or lease remains solely because the document was opened

### Requirement: Current configuration state has no compatibility decoder
OpenLease SHALL encode only the current configuration source, codec, layout, and writable-authority schema. It SHALL reject state records that omit required current fields, use the former opaque-document contract, or declare unsupported schema versions. OpenLease SHALL NOT supply default legacy modes, translate prior source records, or rewrite prior documents during startup.

#### Scenario: Reject an old source record
- **WHEN** OpenLease reads state containing a pre-change configuration source without current codec and layout fields
- **THEN** it rejects the state with reinitialization guidance and does not read or rewrite the referenced source
