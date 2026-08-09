# Bounded extension runtime

OpenLease contract version 4 is a clean replacement for version 3, the
version-two public configuration surface, and the earlier resolver-only extension seam. Hosts must
explicitly register extensions, operations, callbacks,
validators, and additional codecs. Registration and configuration presence are
inert; only a host invocation or an accepted lifecycle callback selection executes
extension code.

## Codec fit

The base package depends on `ruamel.yaml` and `tomlkit`. Both support Python 3.11
and retain comments, ordering, quoting, and human-authored structure while a
selected mapping is changed. This is why OpenLease does not carry hand-written
YAML or TOML parsers. JSON uses the standard library with duplicate-key,
non-finite-number, trailing-content, UTF-8, and object-root checks.

| Codec | Shared identity | Dedicated root | Preservation |
| --- | --- | --- | --- |
| YAML | exact root mapping key | complete root mapping | comments, order, quoting, newline style |
| TOML | exact table key; dotted identities are quoted | complete root table | comments, order, whitespace, quoting |
| JSON | exact object key | complete root object | unrelated semantic values; deterministic rendering |

All codecs expose the same closed managed graph: string-key mappings, sequences,
strings, integers, finite floats, booleans, and supported date/time values. `None`,
arbitrary Python objects, unsafe YAML tags, YAML merge keys, duplicate keys, and
non-mapping roots are rejected. A host-provided codec must be registered directly;
OpenLease never discovers one from packages, filenames, or configuration.

## Binding and mutation

A persisted binding records an exact extension identity, path, codec, layout, and
read-only/writable authority. Space resolution overlays machine, attached packs,
space, repository, and root-to-child authority mappings shallowly. Nested mappings
and sequences are complete replacement values. Reads are source-authoritative and
nested results are immutable.

An assignment or deletion selects exactly one writable source. OpenLease validates
the key and value, locks by canonical document path, re-reads the complete document,
rejects a same-key baseline conflict, rebases unrelated changes, mutates the retained
round-trip tree, writes a flushed temporary sibling, and publishes with
`os.replace`. A lower-source write can remain shadowed by a later source; provenance
reports both facts.

`ManagedConfiguration` is the public configuration protocol returned on bound
extensions and invocations. It adds `snapshot_record()`, `set()`, and `delete()` to
the general managed mapping contract. Explicit mutations return the completed
`WriteDisposition`; mapping assignment and deletion keep their automatic-save
behavior. Data and cache remain general managed mappings.

`ExtensionDocumentBinding` is a frozen reusable description for direct open and
initialization calls. It always carries an explicit extension identity, path,
codec, layout, write authority, and optional repository context. Object and scalar
call forms normalize through the same validation; codec and layout are never
inferred.

Public configuration entry points distinguish read-only, validation, path-change,
decode, and same-key conflict failures with exported error types and stable codes.
Standalone codec calls continue to raise `CodecError`. Use
`to_plain_managed_value()` to copy a supported immutable managed snapshot into
ordinary dictionaries and lists for downstream schema validation.

Direct bindings apply the same codec, validation, conflict, and managed-storage
contract to one invocation-scoped document. They create no space, topology,
authority, pack, lease, source record, or lifecycle generation. Missing-document
initialization is separate, requires writable authority and a complete initial
mapping, uses exclusive creation, and confines optional parent creation to the
explicit boundary.

## Operations, storage, and outcomes

A named operation receives opaque host input, immutable target/event context, and
narrow configuration, durable-data, and disposable-cache mappings. It receives no
`OpenLease`, state repository, Git adapter, or lifecycle mutator. Managed data and
cache use versioned extension-owned envelopes and confined logical keys. Ordinary
writes are immediate; `with extension.batch()` is the only staging boundary, and it
covers managed records only.

Every invocation attempts to persist a bounded outcome with identities, target,
generations, binding digests, handler status, callback mode, failure phase, and
actual write dispositions. The opaque handler value is returned separately. If
outcome persistence fails, the handler is not retried and completed writes remain
reported and authoritative.

## Reconciliation boundary

Reconciliation plans select callbacks by exact extension, operation, event, mode,
repository/cohort target, and optional managed input. Selection validates and
freezes that input, displays it in the plan, includes it in drift evidence, and
passes it unchanged to the operation; configuration never infers or changes the
command. `reconcile.before_repository` may be an explicit gate before Git mutation.
`reconcile.after_repository` and `reconcile.after_cohort` are observational and
continue/report failures without creating an unverified state.

After every selected repository integrates, each after-cohort selection runs once
per completed repository in reconciliation order. Every invocation resolves that
repository's extension context, identifies both the cohort and repository in its
event, and produces a separate outcome. One observational failure does not suppress
later repository invocations or reinterpret completed Git results.

Extensions never choose or perform staging, commits, merge/rebase strategy,
integration, conflict resolution, or finalization. These remain owner-directed Git
legs and intrinsic OpenLease checks.

## ZPP boundary

A rebuilt ZPP can choose `.zpp` as the OpenLease product root and register separate
`zpp.traits` and `zpp.behave` extensions. Per-scope/subscope trait semantics remain
ZPP-owned. A dedicated root-level `zpp.behave.yaml` can be bound without a wrapper,
and Nx, Go Task, or argv values remain opaque extension data. OpenLease resolves the
paths, codecs, overlays, storage, and concurrency; it does not modify ZPP profiles,
traits, process policy, environment selection, or runner behavior.

There is no compatibility decoder or automatic migration. Extension contracts
before version 4, state schemas before version 3, resolver-only registrations, and
the injected reconciliation verifier
are rejected with reinitialization guidance. Authored YAML/TOML/JSON documents are
not read or rewritten while old state is rejected.
