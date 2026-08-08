## Purpose

Provides dependent products with deterministic, read-only extension contexts and configuration layers derived from durable OpenLease spaces, nested OpenSpec authorities, effective worktrees, and explicitly appointed sources.

## ADDED Requirements

### Requirement: Explicit host-owned extension registration
OpenLease SHALL accept extensions only through explicit registration by the dependent host application. Every registered extension SHALL have a stable namespaced identity and a compatible contract version. OpenLease SHALL NOT discover or execute arbitrary globally installed extension code, and one registered extension SHALL NOT read another extension's private configuration or storage namespace through the extension API.

#### Scenario: Register a dependent product extension
- **WHEN** a host application constructs OpenLease with one compatible explicitly identified extension
- **THEN** that extension becomes available through its namespace without making OpenLease depend on the host product

#### Scenario: Reject an incompatible or duplicate extension
- **WHEN** a host registers duplicate extension identities or an unsupported contract version
- **THEN** OpenLease rejects the extension set before resolving any extension context

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
OpenLease SHALL resolve extension configuration as ordered opaque documents without interpreting extension-specific schemas. The ordered scopes SHALL be machine configuration, reusable packs attached to the selected space, direct selected-space configuration, repository scope, and the selected OpenSpec authority's parent-to-child ancestry. Pack documents SHALL follow attachment order, direct space configuration SHALL follow all attached packs, a more specific child scope SHALL follow its parent scope, and configuration attached to one child SHALL NOT participate in a sibling child's context.

The extension SHALL retain ownership of document parsing, activation, replacement, overlays, validation, and rendered output. OpenLease SHALL expose source identity, scope, order, content digest, and content for every resolved document so the extension can compose and cache deterministically.

#### Scenario: Resolve root and child authority configuration
- **WHEN** a space contains root OpenSpec authority configuration and distinct child A and child B configuration and the host targets child A
- **THEN** the ordered context contains machine, attached-pack, direct-space, repository, root, and child A documents in that order without including child B documents

#### Scenario: Preserve opaque extension semantics
- **WHEN** an extension receives documents containing its own activation and overlay fields
- **THEN** OpenLease preserves their content and order without interpreting or merging those fields

### Requirement: Reusable space configuration packs
OpenLease SHALL let a host define a reusable namespaced configuration pack and attach an explicit ordered set of packs to a space. A pack SHALL supply configuration rather than lease identity: attaching or removing a pack SHALL NOT create a child space, acquire an authority, or change the space's affected claim. The resolved context SHALL identify every participating pack and its observed configuration generation.

#### Scenario: Replace a downstream profile with a space pack
- **WHEN** a dependent product attaches a reusable trait-configuration pack to a selected space
- **THEN** the pack participates between machine and repository configuration without requiring the dependent product to resolve a separate profile home

#### Scenario: Keep configuration scope separate from work ownership
- **WHEN** root, child A, and child B authorities have different configuration scopes inside one space
- **THEN** those scopes remain independently resolvable without becoming lease-bearing subspaces

### Requirement: Live source-authoritative configuration
OpenLease SHALL re-evaluate every participating configuration source whenever a host requests extension context. The request SHALL resolve the content currently available through the recorded source binding and SHALL report its observed configuration generation and content digest. A content change in machine configuration, an attached pack, a repository scope, an OpenSpec authority scope, or an explicitly appointed source SHALL participate in the next request even while the selected space is locked, without requiring a refresh operation.

OpenLease SHALL NOT silently serve stale cached content when a current source is missing, unreadable, or invalid as an OpenLease configuration document. Failure to resolve current configuration SHALL fail that extension-context request without changing the selected space, its leases, affected claim, topology, worktree records, or reconciliation state. Content changes SHALL NOT themselves advance lifecycle or graph generations.

#### Scenario: Observe a pack edit while locked
- **WHEN** an attached reusable pack changes while its selected space remains locked and the host requests extension context again
- **THEN** OpenLease returns the current pack content with its newly observed generation and digest without refreshing or changing the lease

#### Scenario: Refuse stale fallback for an unavailable source
- **WHEN** a previously resolved configuration source becomes missing or unreadable before the next extension-context request
- **THEN** that request fails instead of returning cached content, while independent lifecycle operations remain available and unchanged

### Requirement: Explicit custom configuration-source paths
OpenLease SHALL let a host appoint an existing readable custom path as a configuration source for an extension at machine, space, repository, or OpenSpec authority scope. It SHALL canonicalize and record the source identity, reject missing or unreadable sources without partial binding, and treat the source as configuration rather than a repository member, authority, lease, worktree, or ownership proof.

When the appointed path is contained by a registered repository, OpenLease SHALL retain a logical repository-relative binding and resolve it beneath that space member's current effective checkout. When the path is external to every registered repository, OpenLease SHALL retain its exact canonical machine-local path. OpenLease SHALL NOT copy, adopt, delete, or rewrite appointed source content.

#### Scenario: Follow a repository source into a generated worktree
- **WHEN** a repository-scoped custom configuration source is appointed beneath a registered source checkout and the selected space uses a generated worktree for that repository
- **THEN** extension context resolves the same repository-relative source beneath the generated effective checkout

#### Scenario: Retain an external custom source
- **WHEN** a host appoints a readable configuration source outside every registered repository
- **THEN** extension context uses that exact canonical path without associating or leasing it

#### Scenario: Reject an unavailable custom source
- **WHEN** a host appoints a missing or unreadable custom configuration source
- **THEN** OpenLease rejects the complete binding without retaining a partial configuration record

### Requirement: Namespaced extension storage resolution
For each explicitly registered extension, OpenLease SHALL resolve separate configuration, data, and cache roots. The default data and cache roots SHALL be namespaced beneath the selected machine-local OpenLease state root, but a host SHALL be able to override every extension root independently or place them beneath one custom product root. The host MAY also use OpenLease's existing state-root selection to place the core registry beneath that product root.

OpenLease SHALL canonicalize the selected roots, expose their provenance, and keep extension namespaces distinct even when they share a host root. Configuration documents and extension results SHALL NOT be written into OpenLease lifecycle state unless a separate versioned OpenLease configuration record owns that data. Neither OpenLease nor an extension SHALL overwrite or remove pre-existing content merely because a custom root was selected; destructive authority requires exact recorded ownership.

#### Scenario: Resolve extension storage under an overridden state root
- **WHEN** isolated automation supplies an explicit OpenLease state root and requests extension context
- **THEN** the extension receives data and cache roots namespaced beneath that state root without independently resolving a product-specific home directory

#### Scenario: Preserve a dependent product home
- **WHEN** rebuilt ZPP selects `.zpp` as its custom product root and appoints configuration, data, cache, and OpenLease state locations beneath it
- **THEN** OpenLease resolves those exact namespaced locations while ZPP remains free of independent home and effective-worktree path resolution

#### Scenario: Override extension roots independently
- **WHEN** a host appoints distinct custom paths for an extension's authored configuration, writable data, and disposable cache
- **THEN** OpenLease returns those canonical paths with separate roles and ownership boundaries rather than forcing them beneath the default state root

### Requirement: Dependency configuration isolation
An OpenSpec dependency edge SHALL remain relationship context and SHALL NOT implicitly import the provider authority's extension configuration into the consumer's scope. A host MAY make a separate explicit context request for the provider authority, preserving the provider's own scope chain and access role.

#### Scenario: Keep provider traits out of a consumer scope
- **WHEN** repo 2 depends on an OpenSpec authority hosted by repo 3 and extension context targets repo 2
- **THEN** the result reports the dependency but excludes repo 3 authority configuration unless the host explicitly requests that provider scope
