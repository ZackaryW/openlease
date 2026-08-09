## Why

OpenLease resolves ordered extension documents but leaves parsing, persistence, named execution, and lifecycle participation to every consumer. Dependent products need one bounded runtime where an extension can read and assign managed configuration, register operations and optional callbacks, and use confined data/cache state without making OpenLease understand product schemas or take over Git workflow policy.

## What Changes

- **BREAKING** Replace the current manifest-plus-resolver extension surface with one version-two registration contract. There is no resolver adapter, legacy document mode, state migration, or dual-version execution path; incompatible state and registrations are rejected and must be reinitialized by the host product.
- Add an explicit configuration codec registry with built-in YAML, TOML, and JSON codecs. Bindings declare their format; OpenLease never guesses a legacy format from file contents.
- Support two explicit document layouts:
  - `shared`: a root mapping contains exact extension-identity keys, such as `[extension-a]` or `["zpp.behave"]` in TOML, `extension-a:` in YAML, and `{"extension-a": {...}}` in JSON;
  - `dedicated`: the complete root mapping belongs to the binding's one extension identity, allowing an existing current-format document such as `zpp.behave.yaml` to remain unwrapped.
- Add a host-extensible but explicitly populated codec registry. Built-in codecs define strict mapping, duplicate-key, safe-value, rendering, and preservation behavior; additional codecs require explicit host registration and are never discovered dynamically.
- Add a bound extension configuration mapping whose reads resolve current effective values and whose assignments or deletions automatically save to one explicitly selected writable binding with canonical-path locking, conflict detection, and atomic publication.
- Add invocation-scoped direct document binding so a host can safely open or explicitly initialize one extension-owned repository file without creating an OpenLease space, topology record, or persistent source binding.
- Preserve normal space-scoped binding for machine, pack, space, repository, and authority configuration. Decoded extension mappings use deterministic shallow key overlay while the extension remains responsible for schema validation and value meaning.
- Add explicit, versioned named operations and a closed registry of optional lifecycle callbacks. Registration and configuration presence activate nothing; an operation must be invoked and a callback must be selected for a supported event.
- Make callbacks observational by default. Reconciliation may explicitly select a pre-repository callback as a gate before Git mutation; post-repository and post-cohort callbacks remain observational.
- Add managed durable-data and disposable-cache mappings with immediate atomic writes by default and an explicitly entered optional batch for bounded grouped mutations.
- Record structured phase-specific invocation outcomes without granting handlers a lifecycle mutator or storing opaque extension results in OpenLease lifecycle state.
- **BREAKING** Remove the externally injected reconciliation-verifier compatibility surface. Baseline OpenLease safety checks remain core behavior; product verification participates only through explicitly selected extension callbacks.
- Keep staging, commit creation, merge/rebase selection, integration, conflict resolution, and finalization outside the extension runtime. Configuration and callbacks never authorize or trigger those actions implicitly.
- Keep extension schemas, validation policy, runner adapters, and implementation settings opaque to OpenLease. ZPP verification, Nx, Go Task, and argv are motivating consumers, not built-in runner policy.

Example shared documents represent the same exact namespaces:

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

A dedicated binding instead treats the complete document as the extension mapping. Thus `zpp.behave.yaml` can retain its current root-level `version` and `commands` keys while its binding assigns the whole document to extension identity `zpp.behave`; this is a current version-two contract, not a compatibility reader.

## Capabilities

### New Capabilities

- `bounded-extension-runtime`: Explicit version-two registration, named operations, optional bounded callbacks, managed configuration/data/cache mappings, structured outcomes, and authority isolation.

### Modified Capabilities

- `space-scoped-extension-configuration`: Replace opaque resolver documents with breaking YAML/TOML/JSON managed bindings, shared or dedicated namespace layouts, effective mapping resolution, direct document binding, and automatic conflict-safe saving.
- `relational-workset-lifecycle`: Replace the injected verifier surface with optional plan-bound extension callbacks while preserving explicit owner-selected Git integration and core safety checks.

## Impact

- Public Python contracts in `openlease.extension`, `openlease.lifecycle`, results, exports, and reconciliation inputs.
- Configuration source/state models, schema version, codecs, source planning, direct binding, canonical-path locks, atomic writers, and conflict diagnostics.
- New base runtime dependencies for safe round-trip YAML and TOML; JSON uses the standard library with duplicate-key rejection.
- Managed extension data/cache records, optional batch recovery, invocation outcome retention, and public inspection.
- Reconciliation planning/application and CLI JSON envelopes for explicit callback selections; no extension-owned Git integration state.
- All current extension consumers must move to the new contract and reinitialize incompatible OpenLease state. There is intentionally no compatibility or automatic migration phase.
