## Context

See `proposal.md` for motivation and the three capability deltas for normative behavior.

OpenLease currently exposes a small read-only extension seam:

- `src/openlease/extension.py` defines `ExtensionManifest`, `ExtensionRegistration(manifest, resolver)`, immutable `ExtensionContext`, and `ExtensionResolution`.
- `OpenLease.resolve_extension_context()` plans extension-specific configuration sources, reads stable opaque bytes, constructs context, and invokes one resolver explicitly.
- `src/openlease/core/configuration.py` already defines extension roots, target identity, source binding, and deterministic machine → attached pack → space → repository → root-to-child authority planning.
- `ConfigurationSourceReader` provides stable byte reads and content digests but no parsing or writes.
- `OpenLease.reconcile_apply()` owns Git integration and invokes an injected `verifier(scope, paths)` after each leg and cohort.
- State schema version two records extension-specific roots, packs, bindings, and attachments without codec, layout, or write-authority fields.

The intended runtime is a replacement, not an additive compatibility layer. Current consumers will be changed together. Old registrations and old state must fail clearly rather than force every new abstraction to carry two semantics.

One deliberate product-format requirement shapes the design: shared configuration should support YAML, TOML, and JSON namespaces, while a standalone extension document such as repository-root `zpp.behave.yaml` must retain its root-level schema. Namespace is therefore binding metadata and access authority, not necessarily a physical wrapper table.

## Goals / Non-Goals

**Goals:**

- Provide one current extension contract with exact identity, managed configuration, named operations, optional callbacks, data/cache mappings, and structured outcomes.
- Make YAML, TOML, and JSON equal built-in configuration formats behind one codec contract.
- Support both shared multi-extension documents and dedicated one-extension documents.
- Make `extension.config[key] = value` a complete conflict-safe save operation without an additional save call.
- Preserve comments and unrelated structure where the chosen source format supports round-trip preservation.
- Support repository-local configuration through invocation-scoped direct binding without manufacturing spaces or topology.
- Reuse existing space/target source order, generated-worktree remapping, dependency isolation, and state-stability checks.
- Keep extension configuration and handlers incapable of implicitly authorizing Git or lifecycle effects.
- Keep direct writes immediate and batches optional.
- Make implementation failures phase-specific and externally inspectable.

**Non-Goals:**

- Supporting the former resolver, state schema, source record shape, or injected verifier.
- Automatic state/data migration or a transition release supporting two contracts.
- Dynamic plugin, operation, callback, provider, or codec discovery.
- Inferring format or layout from legacy content. Suffix-based UI convenience may propose a value, but the accepted binding records an explicit codec and layout.
- A general event bus.
- Deep merge of configuration values.
- Automatic Git staging, commit creation, merge/rebase selection, conflict resolution, integration, or finalization.
- Transactional rollback of arbitrary handler, process, Git, network, or filesystem effects.
- Built-in awareness of ZPP, behavior mappings, traits, Nx, Go Task, or argv providers.
- Secrets management, remote stores, distributed locks, background execution, or remote cache coordination.

## Decisions

### Replace the extension contract and state schema in one boundary

`EXTENSION_CONTRACT_VERSION` advances to the new contract and the old resolver fields disappear rather than becoming deprecated optionals. The current registration conceptually contains:

```python
@dataclass(frozen=True, slots=True)
class ExtensionRegistration:
    manifest: ExtensionManifest
    operations: tuple[ExtensionOperation, ...] = ()
    callbacks: tuple[ExtensionCallback, ...] = ()
    validator: ExtensionValidator | None = None
    codecs: tuple[ConfigurationCodec, ...] = ()
```

Construction validates the complete registry. A handler is never derived from an operation name. A callback binding references a declared operation. Codec names are unique after combining built-ins with explicit host additions. Registration has no side effects.

State advances to one new schema requiring codec, layout, and write authority on each persisted configuration source. The decoder rejects preceding schemas. OpenLease does not default missing fields to an opaque mode. Host products own reinitialization guidance and may preserve external authored documents separately, but OpenLease performs no conversion.

This clean break was selected over a v1/v2 union because the old raw-document resolver and the new effective managed mapping have conflicting ownership, failure, and write semantics. A compatibility adapter would be the largest and least exercised part of the runtime.

### Use an explicit codec registry with three built-ins

The internal codec protocol is format-neutral:

```python
class ConfigurationCodec(Protocol):
    name: str

    def decode(self, content: bytes) -> RoundTripDocument: ...
    def root_mapping(self, document: RoundTripDocument) -> Mapping[str, ManagedValue]: ...
    def replace_root_mapping(
        self,
        document: RoundTripDocument,
        value: Mapping[str, ManagedValue],
    ) -> RoundTripDocument: ...
    def encode(self, document: RoundTripDocument) -> bytes: ...
```

The public protocol may use immutable records instead of exposing a library-specific syntax tree, but it must allow an encoder to preserve unrelated authored structure. All codecs normalize to a closed managed value graph: string-key mappings, sequences, strings, integers, finite floats, booleans, and format-supported date/time values. `None` is excluded from the common contract because TOML cannot represent it. Extensions needing optional values omit keys or use an extension-specific sentinel value validated by their schema.

Built-in behavior:

| Codec | Parser/writer policy | Required rejection | Preservation |
| --- | --- | --- | --- |
| `yaml` | safe, round-trip YAML | duplicate keys, custom tags, non-string keys, merge-key ambiguity, multi-document input | comments, key order, quoting/style where supported |
| `toml` | strict round-trip TOML | invalid syntax, non-table shared namespace, unsupported managed values | comments, key order, exact quoted identity |
| `json` | strict UTF-8 JSON object | duplicate keys, non-object root, non-finite numbers, trailing values | semantic unrelated content; deterministic indentation/order |

Use mature Python 3.11-compatible libraries rather than custom parsers. Evaluate `ruamel.yaml` for YAML round-tripping and `tomlkit` for TOML round-tripping; JSON uses `json` with duplicate-key detection through `object_pairs_hook` and `parse_constant` rejection. Dependency versions are selected only after fail-first preservation and safety fixtures demonstrate the needed behavior.

Additional codecs require explicit host registration and the same behavior contract. They are executable extension infrastructure, so a codec failure is isolated and reported as configuration decoding or encoding—not silently retried through another codec.

### Make format and layout orthogonal binding metadata

Each persisted or direct binding records:

```python
ConfigurationBinding(
    extension_id="zpp.behave",
    codec="yaml",
    layout=ConfigurationLayout.DEDICATED,
    path=...,
    writable=True,
    # scope metadata only for persisted space-scoped bindings
)
```

`shared` layout selects one exact root key equal to `extension_id`:

```toml
[extension-a]
some-config = 1

["zpp.behave"]
runner = "go-task"
```

```yaml
extension-a:
  some-config: 1
zpp.behave:
  runner: go-task
```

```json
{
  "extension-a": {"some-config": 1},
  "zpp.behave": {"runner": "go-task"}
}
```

The manifest identifier is always one literal mapping key. TOML's unquoted dot creates nested tables, so the codec must render dotted identities as quoted keys. It must not equate `[zpp.behave]` with `["zpp.behave"]`.

`dedicated` layout treats the full root mapping as the extension value:

```yaml
# Entire document bound to extension zpp.behave
version: 1
commands:
  bdd:
    provider:
      kind: argv
      argv: [uv, run, behave, "{targets}"]
    targets: {}
```

This preserves `zpp.behave.yaml` without preserving its old loader or execution implementation. OpenLease applies the current codec/binding/write contract; ZPP supplies the current extension validator and operations.

Format is never tied to layout: a dedicated TOML or JSON document and a shared YAML document are equally valid. The binding, not the suffix, is authority. A CLI may default `.yaml` to `yaml` only as an input convenience before recording an explicit value; library APIs require the explicit codec.

### Retain extension-specific scope records

Persisted sources, packs, and attachments remain keyed by extension identity. The current planner already provides correct target isolation and ordering. A shared physical document can therefore have several extension-specific binding records pointing to the same canonical path, each selecting its own root key.

This avoids converting the whole configuration graph into document-first ownership. The write path must coordinate by canonical path rather than record identity so two extensions sharing a file cannot race.

New state records include:

- `codec`: registered codec name;
- `layout`: `shared` or `dedicated`;
- `writable`: explicit managed mutation authority;
- existing source identity, extension, scope, path, repository association, order, and revision.

A dedicated binding is normally unique per canonical path because the entire document belongs to one extension. Binding the same dedicated path to another extension is rejected. A shared path may be bound to several extensions.

### Resolve one generic effective mapping

Space-scoped resolution keeps current source order. Each selected source is stably read, decoded through its recorded codec, projected through its layout, and reduced into an effective mapping using shallow top-level overlay. A nested mapping is one value at its parent key. OpenLease does not deep merge because cross-product schemas cannot share a reliable recursive policy.

The immutable snapshot carries:

- effective values;
- each source's identity, scope, order, codec, layout, binding revision, digest, and observed generation;
- winning source provenance per effective key;
- selected target context and extension roots.

The extension validator sees the completed immutable mapping. It owns required keys, defaults, unions, semantic versions, runner selection, and domain errors. Configuration presence never invokes it except during an explicit read/bind/invocation that requires validation.

`ManagedConfiguration` reads resolve fresh source-authoritative state. `snapshot()`, iteration, `items()`, and similar whole-view operations use one coherent captured resolution. Nested mappings/sequences are immutable or defensively copied. There is deliberately no proxy graph that tries to detect arbitrary in-place Python mutation.

### Require an exact writable binding

An extension handle binds an exact writable source identifier:

```python
extension = openlease.bind_extension(
    "extension-a",
    space_id="work",
    target=ConfigurationTarget.repository("repo-a"),
    writable_source="repo-config",
)

extension.config["some-config"] = 1
```

Read-only binding is valid. Assignment then fails before I/O. A `(scope_kind, scope_id)` convenience may resolve a writable source only if exactly one current source matches. This avoids nondeterministic selection among two repository bindings with different order.

Writing changes the local selected mapping only. It never writes the flattened effective mapping. If a higher-precedence source shadows the key, the mutation result reports the written source while the next effective snapshot still shows the winner.

`del config[key]` deletes only that local key. A lower-precedence value may become visible afterward. `update()` follows normal direct assignment semantics unless called on an explicit batch object; it does not secretly stage handler-wide work.

### Add invocation-scoped direct document sessions

Repository configuration such as `zpp.behave.yaml` must work without requiring ZPP to create a durable OpenLease space merely to run repository verification. Add a direct binding entry point:

```python
behavior = openlease.bind_extension_document(
    "zpp.behave",
    path=repository_root / "zpp.behave.yaml",
    codec="yaml",
    layout=ConfigurationLayout.DEDICATED,
    writable=False,
)
```

The session receives one exact binding and the extension's ordinary data/cache roots. It has no space members, authorities, topology, leases, or lifecycle mutator. Its immutable target record identifies the canonical document and optional host-supplied repository context only.

Initialization is separate and explicit:

```python
behavior = openlease.initialize_extension_document(
    "zpp.behave",
    path=repository_root / "zpp.behave.yaml",
    codec="yaml",
    layout=ConfigurationLayout.DEDICATED,
    initial={"version": 1, "commands": {}},
)
```

Initialization requires absence, validates the initial mapping through codec and extension validator, creates no unexpected parents outside the authorized boundary, and publishes atomically. If the path exists, it is opened and validated through the non-creating path or initialization fails; it is never truncated.

Direct bindings are not stored in central state and do not advance lifecycle/configuration generations. They are invocation-scoped capabilities supplied by the host. This was selected over auto-registering the current repository because verification configuration must not mutate topology or create ownership claims.

### Serialize direct mutations by canonical document path

Every direct configuration mutation runs:

1. Validate key/value and writable authority.
2. Resolve and validate the canonical path within the binding boundary.
3. Acquire an interprocess lock keyed by a digest of the canonical path. Store lock files under an OpenLease-owned lock directory, not beside arbitrary external sources.
4. Re-read and decode current complete content under the lock.
5. Compare the caller's observed local value for the exact selected key against current local content.
6. If only unrelated content changed, rebase the requested assignment/deletion. If the same local key changed, return conflict.
7. Apply the mutation in the codec's round-trip document model without rebuilding unrelated shared namespaces.
8. Encode, write a flushed temporary sibling, and publish with `os.replace`; perform best-effort directory synchronization where supported.
9. Return old/new digests and binding provenance, then release the lock.

Use the existing `filelock` dependency. Canonical-path locking covers different extensions and persisted/direct bindings pointing at one file. Same-key comparison prevents silent lost updates while allowing an unrelated comment, key, or namespace edit to survive.

A successfully replaced document remains authoritative even if the handler later fails. This is the required non-staging default. The outcome must report the write and handler failure independently.

### Keep optional batch semantics bounded

An explicit batch may group configuration, data, and cache mutations:

```python
with extension.batch() as changes:
    changes.config["runner"] = "go-task"
    changes.config["target"] = "test"
    changes.data["last-selection"] = {"runner": "go-task"}
```

Only entering this block delays publication. Ordinary mappings never create a staging directory or journal. A multi-file batch may use temporary siblings and a small OpenLease-owned recovery record. The batch contract covers only managed records and cannot include subprocesses, Git, network effects, or arbitrary handler filesystem work. If cross-file atomicity cannot be proven on a platform, the result must report committed, uncommitted, and recovery-required records rather than overstate rollback.

### Use confined logical-key records for data and cache

Durable data and disposable cache are not human-authored configuration formats. They remain extension-specific roots containing versioned OpenLease record envelopes addressed by logical keys. Normalize keys, reject empty/dot/parent/device/absolute forms, resolve beneath the root, reject symlink escape, and require recorded extension ownership for replacement/deletion. Cache records explicitly permit eviction; durable records do not.

Handlers receive managed mappings, not general writable root authority. Context may still report roots as provenance, but path possession is not permission to mutate them through OpenLease.

### Use one invocation pipeline

A named operation follows:

1. Validate extension, operation, contract, target shape, binding, and requested write authority.
2. Snapshot applicable OpenLease state.
3. Resolve direct or space-scoped current configuration and provenance.
4. Validate extension configuration.
5. Construct immutable invocation context plus managed mappings.
6. Invoke exactly one handler with opaque host input.
7. Collect completed direct-write and optional-batch dispositions.
8. Record a bounded outcome envelope.
9. Return structured metadata plus the separate opaque handler value.

Failure phases are `registration`, `target`, `binding`, `read`, `decode`, `layout`, `overlay`, `validation`, `handler`, `managed_write`, `batch_commit`, and `outcome_recording`. A preceding-phase failure starts no handler. A write failure raises at the assignment. A later handler failure cannot relabel a completed write. Outcome-recording failure retains the known execution facts.

Outcomes live under the owning extension's durable namespace and contain only runtime metadata: identity, operation/event, target, callback mode, state/config generation when applicable, binding digests, handler status, write dispositions, bounded diagnostics, and retention information. Opaque results never enter central lifecycle state.

### Separate callback availability from selection

The callback registry is a closed mapping from supported event to declared operation. Registration means “available”; a lifecycle request or accepted plan must separately select extension, operation, event, mode, and target. Configuration never selects callbacks.

Selected handlers receive an immutable event record and bound extension handle, not `OpenLease`, the state repository, Git adapter, or lifecycle mutator. Observational dispatch continues after failures to collect every selected outcome. Gates stop according to their owning contract.

The initial reconciliation events are:

- `reconcile.before_repository`: observational or explicitly gating, immediately before Git mutation after plan revalidation;
- `reconcile.after_repository`: observational only, after ordinary integration and state recording;
- `reconcile.after_cohort`: observational only, after every ordinary member result is recorded.

The former injected verifier is removed. Intrinsic OpenLease safety checks remain ordinary reconciliation code. A dependent product that wants tests during reconciliation registers and selects its extension callback explicitly.

### Keep reconciliation owner-directed

Callback selections are separate from `ReconcileSelection`, which continues to own repository, destination ref/path, and merge/rebase strategy. Planning shows selected callbacks next to Git legs and binds them to registration/target evidence. Apply re-plans and rejects drift before Git mutation.

No callback means no extension code. A pre-repository gate failure occurs before irreversible Git mutation. Post-event failures are observations and do not add `integrated_unverified`, retry, or finalization-blocking state. A future post-mutation gate requires a separate proposal with truthful durable lifecycle semantics.

### Keep modules narrowly owned

Expected implementation placement:

- `src/openlease/extension.py`: public registration, codec protocol/name, operation, callback, selection, direct/space target, handle, result, outcome, and managed-value contracts.
- `src/openlease/core/configuration.py`: binding records, codec/layout/write selectors, pure source ordering, namespace projection, shallow overlay, and target validation.
- `src/openlease/utils/configuration_source.py` plus focused sibling codecs: stable reads, YAML/TOML/JSON decode/encode, canonical-path lock, conflict comparison, temporary sibling, and atomic publication.
- A focused managed-storage utility: logical-key data/cache records and optional batch recovery.
- `src/openlease/core/state_codec.py`: the one current state schema; no legacy defaults or migrations.
- `src/openlease/lifecycle.py`: registry construction, bind/invoke pipeline, outcome orchestration, and callback dispatch at owned lifecycle event points.
- `src/openlease/core/reconciliation.py`: pure callback-selection validation/order only if needed; Git plan/application stays independent.
- `src/openlease/result.py` and `src/openlease/__init__.py`: deterministic envelopes and public exports.
- `src/openlease/cli.py`: explicit format/layout/write fields and callback selection where the host process actually has registrations; never dynamic handler discovery.

## Risks / Trade-offs

- **[A clean break rejects existing consumers and state]** → Coordinate dependent changes, fail with precise replacement guidance, and keep external authored documents untouched so hosts can explicitly rebind them.
- **[Three formats triple parser edge cases]** → Put every codec behind one conformance suite covering duplicate keys, value graph, namespace selection, preservation, and failure phases.
- **[YAML has unsafe or ambiguous features]** → Use safe round-trip parsing and reject custom tags, non-string keys, merge-key ambiguity, and multi-document streams.
- **[Shared files let extensions race]** → Lock by canonical path, compare the selected local key, rebase unrelated edits, and reject same-key conflict.
- **[Round-trip writers can damage human formatting]** → Select mature libraries only after preservation fixtures and mutate the retained syntax tree rather than reconstructing unrelated namespaces.
- **[JSON cannot preserve comments]** → JSON has no comment contract; preserve semantic unrelated values and use deterministic rendering.
- **[Dotted TOML identities become nested paths]** → Treat identity as one literal key and force quoting when required.
- **[Lower-scope saves appear ineffective]** → Require exact writable binding and return written/winning provenance while retaining standard precedence.
- **[Nested Python mutation looks persistable]** → Return immutable/defensive values and require replacement assignment.
- **[Immediate writes survive handler failure]** → Report effects truthfully and offer an explicit bounded batch for callers needing grouped managed writes.
- **[Direct document binding bypasses space context]** → Limit it to one exact document and extension namespace with no topology, lease, or lifecycle authority.
- **[A custom codec executes host code]** → Require explicit registration, validate protocol conformance, isolate codec phases, and never fall back dynamically.
- **[Callbacks become implicit verification policy]** → Separate availability from selection and make post-mutation callbacks observational.
- **[Removing the injected verifier weakens tests accidentally]** → Preserve intrinsic checks in core and require product verification to be visibly selected in plans.
- **[Outcome recording fails after effects]** → Preserve known handler/write dispositions and never retry handlers implicitly.

## Migration Plan

This is a replacement sequence, not a data migration:

1. Land fail-first codec/layout/concurrency behavior and new state rejection fixtures.
2. Add and validate YAML/TOML dependencies plus the JSON strict decoder.
3. Replace extension and configuration public models with the current contract.
4. Replace the state schema and reject all previous records without defaults or conversion.
5. Implement shared/dedicated decode, effective overlay, immutable snapshots, direct binding, and explicit initialization.
6. Implement automatic direct writes, canonical-path locking, conflicts, and atomic publication.
7. Implement confined data/cache mappings and optional batches.
8. Implement explicit operations, outcomes, and callback registry/selection.
9. Remove resolver and injected verifier code paths.
10. Add reconciliation event dispatch without changing Git ownership or adding post-mutation gates.
11. Update public exports, CLI envelopes, documentation, and dependent contract probes.
12. Update downstream hosts in coordinated changes and require their existing OpenLease state to be reset/reinitialized.

Before a release, current Python 3.11 base installation, complete BDD/pytest/lint/format/build verification, codec conformance, dependency lock, strict OpenSpec validation, and downstream ZPP probes must pass. Rollback restores the preceding package and its preceding state backup; it does not ask the old binary to decode the new state or delete authored YAML/TOML/JSON documents.
