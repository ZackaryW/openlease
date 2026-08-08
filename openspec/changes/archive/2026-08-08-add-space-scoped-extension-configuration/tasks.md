## 1. Versioned Configuration State Contract

- [x] 1.1 Add fail-first codec tests for version-1 migration, the version-2 configuration records, strict unknown-field rejection, referential integrity, configuration-generation changes, and recoverable pre-upgrade backup behavior.
- [x] 1.2 Implement frozen records for extension root policy, source bindings, reusable packs, and ordered space-pack attachments in the state codec without placing configuration fields on lifecycle records.
- [x] 1.3 Implement version-1 reading, version-2 round trips, validation, and the atomic first-write backup, then run the focused state codec and repository tests as the state-contract verification target.

## 2. Canonical Path and Storage Resolution

- [x] 2.1 Add fail-first tests for default, product-root-derived, and independently overridden configuration/data/cache roots, including namespace separation, provenance, canonicalization, and non-ownership of pre-existing content.
- [x] 2.2 Implement the pure namespaced root-policy resolver and public immutable root/provenance result types without creating or deleting caller-owned paths.
- [x] 2.3 Add fail-first tests for classifying exact custom document paths as repository-relative or external and for rebinding repository-relative paths into pinned and generated effective checkouts.
- [x] 2.4 Implement canonical source binding and effective-path resolution, including traversal rejection, containment checks, readability checks, and no copy/adopt/delete side effects; run the focused path-resolution tests as an independent verification target.

## 3. Live Ordered Configuration Resolution

- [x] 3.1 Add fail-first tests for machine → attached packs → direct space → repository → root-to-child authority ordering, stable tie-breaking, sibling exclusion, repository-only targets, and dependency-provider isolation.
- [x] 3.2 Implement a pure scope planner that produces ordered binding descriptors from one state snapshot without reading product-specific schemas.
- [x] 3.3 Add fail-first tests proving current bytes are re-read on each request, content-addressed observed generations change during a lock, missing/unreadable sources never fall back to cached bytes, and content edits do not advance lifecycle or graph generations.
- [x] 3.4 Implement coherent source reads, digests, observed-generation tokens, bounded state/source concurrency retries, and immutable document/provenance results; run the focused live-resolution tests as an independent verification target.

## 4. Extension Context Boundary

- [x] 4.1 Add fail-first tests for explicit namespaced registration, supported contract versions, duplicate rejection, namespace isolation, and absence of global extension discovery.
- [x] 4.2 Implement immutable extension manifest, registration, target, member, relationship, configuration, and context DTOs and export the stable public contract.
- [x] 4.3 Add fail-first tests for pinned and generated member contexts, explicit repository and authority targets, branch/commit/access provenance, parent/dependency relationships, and invalid target-space combinations.
- [x] 4.4 Implement context assembly and optional resolver invocation outside state transactions, passing no lifecycle service or mutable state handles; prove resolver failure leaves lock, release, recovery, and reconciliation callable in the focused extension-boundary target.

## 5. Configuration Management API

- [x] 5.1 Add fail-first lifecycle tests for binding, replacing, ordering, and removing extension sources at machine, direct-space, repository, and authority scopes with optimistic generation protection and atomic rejection of invalid bindings.
- [x] 5.2 Implement public source-binding mutations that advance state/configuration generations but never graph generation, affected claims, leases, worktree records, or space status.
- [x] 5.3 Add fail-first lifecycle tests for defining reusable packs and attaching, reordering, and detaching packs from draft, locked, and successor spaces without creating child spaces or lease ownership.
- [x] 5.4 Implement pack and attachment mutations plus context-resolution entry points on `OpenLease`, and run the focused configuration-management integration target.

## 6. Optional CLI and Serialized Inspection

- [x] 6.1 Add fail-first CLI tests for explicit source registration/removal, pack definition/attachment, root-policy configuration, and repository/authority context inspection through the standard JSON result envelope.
- [x] 6.2 Implement thin Typer adapters over the public configuration API with explicit extension, space, scope, source, order, and root arguments; keep trait parsing and rendering out of OpenLease.
- [x] 6.3 Verify CLI failures for incompatible extensions, unavailable sources, ambiguous targets, and concurrent changes are stable, non-partial, and do not interfere with lifecycle commands.

## 7. Capability Acceptance and Host Handoff

- [x] 7.1 Add a dedicated `space_scoped_extension_configuration` behavior feature root covering nested monorepo scopes, reusable packs, repo-2/repo-3 dependency isolation, generated successor rebinding, live locked-space edits, custom `.zpp` roots, and resolver failure isolation.
- [x] 7.2 Add focused step bindings and reusable fixtures for that capability without merging unrelated lifecycle scenarios or execution steps into one feature or support module.
- [x] 7.3 Document the standalone `~/.openlease` defaults, complete host override model, schema-v2 recovery boundary, and a rebuilt-ZPP integration example in which OpenLease resolves configuration while ZPP interprets only trait semantics.
- [x] 7.4 Run the capability behavior target, unit/integration targets affected by each cacheable slice, strict OpenSpec validation, lint, and the full regression suite; record each target result independently.
