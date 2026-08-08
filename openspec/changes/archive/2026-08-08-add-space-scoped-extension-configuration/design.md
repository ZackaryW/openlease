## Context

OpenLease currently stores one strict, machine-local state document and exposes lifecycle operations through `OpenLease`. The state already distinguishes repositories, nested OpenSpec authorities, spaces, effective worktree members, leases, and reconciliation records. State mutation is serialized with optimistic generation checks, while lifecycle and graph generations describe different kinds of change.

The new capability must reuse those identities and effective paths without coupling OpenLease to ZPP or any other dependent product. Configuration content is machine-local and may change independently of a locked space. See `proposal.md` for motivation and `specs/space-scoped-extension-configuration/spec.md` for the behavioral contract.

## Goals / Non-Goals

**Goals:**

- Introduce a generic configuration subsystem whose state, path, scope, ordering, freshness, and provenance rules are fully owned by OpenLease.
- Give explicitly registered extensions an immutable, target-specific view of one space without granting lifecycle mutation authority.
- Resolve repository-contained sources against each space member's effective checkout and external sources against their exact canonical paths.
- Keep configuration changes live and independently observable without changing lease or graph generations.
- Let a host relocate OpenLease state and every extension configuration, data, and cache root beneath a product root such as `.zpp`.

**Non-Goals:**

- Defining ZPP trait schemas, activation, replacement, overlays, validation, ordering within one trait document, or Markdown rendering.
- Discovering arbitrary installed plugins or providing general lifecycle hooks.
- Treating configuration scopes or packs as lease-bearing spaces.
- Importing configuration across dependency edges.
- Prescribing rebuilt ZPP's internal filenames or subdirectory convention beneath `.zpp`.

## Decisions

### 1. Register bounded extension contracts explicitly

The host will pass an immutable collection of extension registrations when constructing `OpenLease`. A registration contains a namespaced extension identifier, a supported contract version, and an optional resolver callable. Duplicate identifiers and unsupported versions fail construction. OpenLease will not inspect Python entry points or global environments.

OpenLease will build the generic context before calling an extension resolver. A resolver receives only immutable value objects and its own resolved roots; it does not receive the `OpenLease` service, state repository, Git adapter, or OpenSpec adapter. Resolver execution occurs outside state mutation and lifecycle transactions.

This capability-specific protocol is preferred over a general hook framework because it keeps dependency direction explicit and makes lifecycle mutation structurally unavailable. A global plugin loader was rejected because installation would silently become execution authority.

### 2. Persist configuration bindings separately from topology

The strict state codec will gain versioned records for:

- extension namespaces and root overrides;
- configuration packs and their ordered source bindings;
- ordered pack attachments on spaces;
- machine, direct space, repository, and authority source bindings.

Each source binding records extension identity, scope identity, stable source identity, source kind, order, and a binding revision. A repository-contained binding stores its repository identifier plus normalized repository-relative path. An external binding stores its exact canonical absolute path. One binding identifies one opaque document; callers express multiple documents as explicit ordered bindings, avoiding any OpenLease-imposed filename or directory-discovery convention.

Configuration metadata mutations use the existing serialized state repository and advance the overall state generation plus a dedicated configuration generation. They do not advance the graph generation, acquire leases, alter affected claims, or change space lifecycle status. Content edits at a bound path do not mutate state at all.

Embedding these records in the existing state document is preferred over a second registry because repository, authority, and space referential integrity can then be validated atomically. Mixing them into `SpaceRecord` was rejected because machine and reusable-pack configuration outlive any one space. The expanded document is schema version 2: the reader accepts version 1 as an empty configuration model, while the first version-2 write preserves a recoverable copy of the version-1 document. An older binary is not claimed to read version 2.

### 3. Resolve one explicit target into an immutable context

The public context request names an extension, a space, and either a repository or an OpenSpec authority. A pure context builder snapshots state, validates the target belongs to the space context, and emits frozen DTOs for:

- source and effective member paths;
- access roles and affected/held status;
- authority ancestry and dependency relationships;
- branch and commit provenance;
- ordered configuration documents and storage roots.

Generated members resolve beneath their recorded effective worktree. Pinned members retain their recorded source/effective path. Authority ancestry is derived root-first from the validated parent graph. Siblings and dependency providers are reported as relationships but are not traversed for configuration.

Returning DTOs rather than domain services prevents a resolver from reaching mutation methods and makes the result safe to serialize through the CLI.

### 4. Compose generic configuration in a fixed scope order

The configuration resolver orders bindings as:

1. machine scope;
2. packs attached to the selected space, in attachment order and then binding order;
3. direct selected-space scope;
4. target repository scope;
5. target OpenSpec authority ancestry from root to the selected child, each in binding order.

Stable identifiers break otherwise equal ordering, making results deterministic. Repository targets omit authority layers. Authority targets use the authority's owning repository layer exactly once. No dependency edge adds documents; a caller that needs a provider resolves that provider explicitly.

OpenLease returns source bytes, scope and source identities, resolved path, order, provenance, content digest, and an observed generation token. It does not parse or merge extension content. The token is content-addressed from the persisted binding revision and current digest, so it changes when either the binding or content changes without requiring an observation write.

This fixed generic composition replaces downstream profile/home/repository resolution while leaving product semantics in the extension. Letting extensions choose scope traversal was rejected because different products would reconstruct conflicting notions of the same space.

### 5. Re-read bound sources on every request

Every context request takes a state snapshot, resolves all participating paths, reads their current bytes, and computes digests before invoking an optional extension resolver. A cache may accelerate hashing only when it can prove identity and freshness, and its output must be indistinguishable from re-reading the current source. A missing, unreadable, or changed-during-read source fails the context request; previously cached bytes are never returned as fallback.

For a coherent result, OpenLease verifies that the state generation used to select bindings has not changed before returning the context. If it changed, resolution retries against a fresh snapshot within a bounded retry policy, then reports concurrent change rather than mixing generations. Source reads use pre/post metadata checks and digest the bytes actually returned. This provides request-level coherence without freezing configuration for the lifetime of a lease.

Persisted binding changes increment configuration generation. File-content changes are reflected by their content-addressed observed generation tokens. Neither advances lifecycle or graph generation.

Live reads were chosen over lease-time snapshots because the owner explicitly wants configuration edits to apply on the next request, including during a lock. A refresh gate and stale fallback were rejected because both hide the current source of authority.

### 6. Centralize path and storage resolution

`OpenLease` continues accepting an explicit state root. Extension root policy adds independent optional configuration, data, and cache overrides plus a convenience product root from which namespaced defaults are derived. All selected roots are canonicalized and returned with provenance indicating default, product-root-derived, or explicit selection.

Selecting a root grants location, not ownership. OpenLease creates only directories/files that its own operation explicitly owns, records ownership where deletion could later occur, and never overwrites or removes pre-existing content merely because it is under a selected root. Authored configuration remains caller-owned; caches remain extension-namespaced and disposable only through an explicit owning operation.

This permits standalone OpenLease to default under `~/.openlease`, while rebuilt ZPP can place OpenLease state and extension roots beneath `~/.zpp` or another appointed `.zpp` root. Keeping a fixed OpenLease home was rejected because it would force ZPP to maintain parallel resolution machinery.

### 7. Keep the CLI a thin configuration and inspection adapter

The optional CLI will expose explicit operations for registering configuration sources, defining packs, attaching ordered packs, setting root policy, and inspecting the resolved context. It will call the same public library methods and return the existing result-envelope shape. Trait interpretation remains a ZPP command concern.

Exact command spelling can follow the existing Typer conventions during implementation; the stable boundary is the library API and its observable behavior. This avoids binding the configuration model to one shell presentation.

## Risks / Trade-offs

- **[Live reads can observe rapid editor rewrites]** → Verify source stability around each read, retry boundedly, and fail coherently instead of returning mixed or stale documents.
- **[The strict state schema grows substantially]** → Keep configuration records normalized, validate all references centrally, and add backward-compatible decoding defaults plus round-trip tests.
- **[Hosts may mistake custom roots for destructive ownership]** → Return root provenance, separate authored/data/cache roles, and require exact recorded ownership for cleanup.
- **[A resolver can still perform arbitrary process-local side effects]** → Treat resolver code as host-trusted, give it no OpenLease service handles, and execute it outside lifecycle transactions so failures cannot roll back or block lifecycle operations.
- **[Per-request hashing costs scale with configuration size]** → Permit freshness-proven hashing optimization, keep documents explicitly bound, and never trade correctness for a stale fallback.
- **[Configuration and state can change concurrently]** → Couple every result to observed state/configuration generations and retry rather than combining incompatible snapshots.

## Migration Plan

1. Extend the state model and codec to schema version 2 with empty-by-default configuration collections, root policy, and a dedicated configuration generation; verify version-1 state decodes to the empty configuration model and is backed up before its first version-2 write.
2. Add pure path, scope-ordering, source-read, digest, and immutable-context utilities before exposing mutations.
3. Add public registration, binding, pack, root-policy, and context-resolution APIs while retaining all existing lifecycle signatures.
4. Add the optional CLI adapters and serialized inspection output.
5. Verify existing lifecycle behavior remains unchanged, then document the host integration contract for rebuilt ZPP.

Rollback removes use of the new APIs while retaining existing lease behavior. Before any version-2 mutation after upgrade, OpenLease preserves the version-1 state document as an owned recovery artifact. Rolling back to a version-1 binary requires restoring that backup and therefore discards state changes made after migration; the CLI and documentation must report that boundary rather than implying bidirectional compatibility.
