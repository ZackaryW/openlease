## Why

Rebuilt downstream products such as ZPP should be able to depend on OpenLease for durable space selection, effective worktree paths, nested OpenSpec scope, configuration discovery, and machine-local storage without duplicating home and path resolution. OpenLease currently exposes the relational work context but has no generic, namespaced configuration or extension-context contract that a dependent resolver can consume.

## What Changes

- Add an explicitly registered, versioned extension-context surface that lets a host application compose read-only extensions without making OpenLease depend on those products or globally discovering arbitrary code.
- Make OpenLease the complete generic configuration kernel for dependent products: it owns home and root resolution, durable space selection, effective worktree paths, machine configuration, reusable packs, direct space configuration, repository scopes, parent-to-child OpenSpec authority scopes, custom source discovery, ordering, provenance, digests, and namespaced storage.
- Resolve each extension request against one explicit space and target scope, using generated members' effective worktree paths and pinned members' recorded paths. Sibling subscopes remain independent while parent configuration can flow downward.
- Let callers appoint explicit custom configuration-source paths. Repository-contained sources follow their logical repository-relative location into generated worktrees; external sources retain their exact canonical machine-local path.
- Make extension configuration, data, and cache roots fully overrideable, independently or beneath one host-selected product root. A rebuilt ZPP can therefore retain `~/.zpp` and repository `.zpp` locations while delegating canonical home and effective-worktree resolution to OpenLease.
- Re-evaluate participating configuration sources for every extension-context request. Changes become visible on the next request, including while a space is locked, without refreshing the lease or mutating lifecycle state; stale cached content is never substituted for an unavailable current source.
- Return ordered opaque configuration documents, observed generations, provenance, digests, and resolved extension-owned roots. Each extension retains ownership only of its product-specific schema, activation, composition, validation, and rendered output.
- Keep extension execution outside lease authority: extensions cannot acquire or release leases, change affected claims or topology, choose worktree destinations, mutate OpenLease state through callbacks, or make lock/release/recovery depend on successful advisory resolution.
- Replace downstream profile/home resolution with OpenLease space configuration. A reusable configuration pack can provide the role previously served by a ZPP profile without turning configuration scopes into lease-bearing child spaces.
- Do not propagate configuration implicitly across dependency edges. A dependent extension may request provider context explicitly, but repository or authority configuration does not leak into a consumer merely because an OpenSpec dependency exists.

## Capabilities

### New Capabilities

- `space-scoped-extension-configuration`: Explicit extension registration, immutable space contexts, nested authority-scoped configuration, reusable packs, custom source paths, namespaced storage, provenance, and mutation isolation.

### Modified Capabilities

- None.

## Impact

The public Python library gains extension manifests, immutable extension-context and configuration-layer result types, space/authority configuration bindings, live custom-source resolution, and fully overrideable namespaced storage resolution. Durable state gains versioned configuration records and generations. The optional CLI will need inspection and configuration commands, while downstream ZPP can select a `.zpp` product root, place the OpenLease state root beneath it, remove its independent configuration, home, profile, saved, repository, and effective-worktree resolution machinery, and register its trait resolver as an OpenLease consumer.

## Unresolved — Do Not Assume

- None.

## Explicitly Deferred

- The exact internal subdirectory and file convention beneath rebuilt ZPP's retained `.zpp` roots remains owned by the future ZPP change. OpenLease supports those roots without prescribing trait-specific filenames or formats.
