## 1. Freeze the Breaking Behavior Contracts

- [x] 1.1 Add fail-first `space_scoped_extension_configuration` BDD scenarios for explicit YAML/TOML/JSON codecs, shared and dedicated layouts, exact dotted identities, shallow overlay, direct binding, automatic retrieval/saving, conflict reporting, and old-state rejection.
- [x] 1.2 Add a capability-owned `bounded_extension_runtime` Behave root covering inert registration, explicit named invocation, optional callback selection, observational continuation, managed data/cache writes, explicit batching, phase-specific outcomes, and missing lifecycle authority.
- [x] 1.3 Extend `deferred_successor_reconciliation` scenarios for removal of the injected verifier, no-callback behavior, selected pre-repository gates, observational post events, registration drift, and extension inability to choose or perform Git integration.
- [x] 1.4 Add negative scenarios proving the former resolver-only registration, old state/source shape, former verifier argument, implicit codec fallback, implicit callback activation, and post-mutation gates are rejected.
- [x] 1.5 Review every accepted scenario against the proposal boundary: no compatibility reader, no automatic migration, no implicit staging/batching, and no extension-owned Git mutation.

## 2. Establish the Multi-Format Codec Conformance Suite

- [x] 2.1 Define one codec conformance fixture set for root mappings, managed scalar/container values, Unicode, empty mappings, nested values, invalid roots, duplicate keys, encoding errors, rendering, and decode/encode failure phases.
- [x] 2.2 Add YAML fail-first fixtures for safe data-only parsing, duplicate keys, non-string keys, custom tags, merge-key ambiguity, multi-document streams, comments, anchors policy, key order, quoting, and newline preservation.
- [x] 2.3 Add TOML fail-first fixtures for bare and quoted extension keys, dotted-identity distinction, nested tables as replaceable values, comments, ordering, date/time values, unsupported values, and malformed syntax.
- [x] 2.4 Add JSON fail-first fixtures for duplicate object keys, non-object roots, trailing values, UTF-8 errors, non-finite numbers, deterministic indentation/order, and semantic preservation of unrelated entries.
- [x] 2.5 Evaluate mature Python 3.11-compatible round-trip libraries, preferring `ruamel.yaml` and `tomlkit` only if they satisfy the fixtures; record dependency-fit rationale and reject hand-written YAML/TOML parsers.
- [x] 2.6 Add selected runtime dependencies to `pyproject.toml`, regenerate `uv.lock`, and prove the base package remains installable without the optional CLI dependency.

## 3. Replace Extension and Configuration Contracts

- [x] 3.1 Replace the resolver-shaped registration with current immutable manifest, operation, callback, validator, codec, target, handle, result, outcome, and write-disposition models in `src/openlease/extension.py`.
- [x] 3.2 Remove resolver types, `ExtensionResolution`, resolver invocation, compatibility branches, and every old public export and test expectation.
- [x] 3.3 Implement construction-time validation for exact unique extension identities, operation names, callback references/events/modes, built-in and custom codec names, target shapes, and one current contract version.
- [x] 3.4 Prove registration performs no source read, decode, validation, operation, callback, managed write, verifier call, state mutation, or Git action.
- [x] 3.5 Define the closed managed-value graph and validate string mapping keys, finite numeric values, supported temporal values, sequences, nested mappings, and rejection of `None` or arbitrary Python objects.

## 4. Replace State and Binding Models

- [x] 4.1 Advance the OpenLease state schema and require codec, layout, and write authority on each persisted configuration binding.
- [x] 4.2 Delete old-schema decoding defaults and migration code; reject every preceding state version and source record missing current fields with replacement guidance.
- [x] 4.3 Update state encoding, normalization, duplicate checks, source/pack/attachment validation, and structural keys for the current binding contract.
- [x] 4.4 Retain extension-specific source and pack records while allowing several extensions to bind one canonical shared path.
- [x] 4.5 Reject two extension identities claiming the same canonical dedicated document and reject incompatible duplicate binding identities.
- [x] 4.6 Extend bind/remove library and CLI inputs with explicit codec, layout, and read-only/writable authority; never infer a persisted legacy mode.
- [x] 4.7 Add fixtures proving incompatible state is rejected without reading or rewriting any referenced YAML/TOML/JSON document.

## 5. Implement Built-In and Explicit Codec Registries

- [x] 5.1 Implement the internal codec protocol and immutable registry with built-in `yaml`, `toml`, and `json` entries plus explicitly supplied unique custom codecs.
- [x] 5.2 Implement YAML safe round-trip decode/encode and all conformance rejections without permitting executable tags or ambiguous merge behavior.
- [x] 5.3 Implement TOML round-trip decode/encode with exact literal extension-key access and forced quoting for dotted identities.
- [x] 5.4 Implement strict JSON object decode using duplicate-key and non-finite-number rejection plus deterministic UTF-8 rendering.
- [x] 5.5 Implement shared layout selection/replacement that exposes one exact extension mapping and preserves all unrelated root entries.
- [x] 5.6 Implement dedicated layout selection/replacement that assigns the complete root mapping to one binding identity with no wrapper.
- [x] 5.7 Reject codec fallback, layout switching, non-mapping selected namespaces, and unregistered custom codecs before extension validation.
- [x] 5.8 Run the same conformance suite against all built-ins and the explicit custom-codec test double.

## 6. Resolve Current Effective Configuration

- [x] 6.1 Refactor source-authoritative context construction into one reusable path for managed reads, snapshots, operations, and selected callbacks.
- [x] 6.2 Preserve machine → attached packs → space → repository → root-to-child authority planning, stable tie-breaking, generated-worktree remapping, sibling exclusion, and dependency-provider isolation.
- [x] 6.3 Decode each binding through its recorded codec/layout and retain identity, scope, order, revision, canonical path, codec, layout, digest, and observed generation.
- [x] 6.4 Implement deterministic shallow top-level overlay with nested mappings/sequences treated as whole replacement values and per-key winning provenance.
- [x] 6.5 Add immutable effective snapshot and bound context models with coherent iteration, target/member/authority/relationship evidence, roots, and participating binding provenance.
- [x] 6.6 Invoke an extension validator only after generic overlay, report semantic failures as `validation`, and never infer product defaults, activation, runner, or callback policy.
- [x] 6.7 Re-read current sources for each managed access/invocation and reject missing, malformed, unsafe, or repeatedly changing sources without stale fallback.

## 7. Add Managed Configuration Mappings

- [x] 7.1 Implement read-only and writable `ManagedConfiguration` plus `BoundExtension`, requiring one exact writable source identifier for mutation.
- [x] 7.2 Permit a scope shorthand only when it resolves to exactly one eligible writable binding; reject absent or ambiguous selection before I/O.
- [x] 7.3 Implement fresh `__getitem__`, `get`, containment, and coherent `snapshot`/iteration behavior without mixing source generations.
- [x] 7.4 Return immutable or defensive nested values and prove in-place Python mutation does not alter source documents.
- [x] 7.5 Implement immediate `__setitem__` and `__delitem__` against only the selected local namespace; require no `save()` method or implicit transaction.
- [x] 7.6 Prove a lower-precedence local save remains shadowed by a later binding and that mutation/effective provenance explains both states.
- [x] 7.7 Validate keys and codec-compatible managed values before acquiring the document lock or creating a temporary file.

## 8. Implement Conflict-Safe Atomic Publication

- [x] 8.1 Add canonical-path-derived interprocess locks under an OpenLease-owned lock namespace using the existing `filelock` dependency.
- [x] 8.2 Under lock, re-read and decode complete current content, compare the selected local key with the caller baseline, and rebase unrelated changes.
- [x] 8.3 Reject same-key conflicts without last-writer-wins overwrite and return binding, path, prior/current digest, and conflicting key evidence.
- [x] 8.4 Mutate the retained round-trip document, preserve unrelated namespaces and structure according to codec guarantees, and revalidate before publication.
- [x] 8.5 Write a flushed temporary sibling and publish with `os.replace`, using best-effort directory synchronization where supported.
- [x] 8.6 Preserve the prior authoritative document and safely handle owned temporary artifacts after encoding, write, permission, synchronization, or replacement failure.
- [x] 8.7 Add concurrency/failure-injection tests for two extensions in one shared file, two bindings for one extension, unrelated keys, same keys, comments, permission failures, lock contention, and replacement interruption.

## 9. Add Invocation-Scoped Direct Documents

- [x] 9.1 Add a direct document target and library binding method requiring exact extension identity, canonical path, codec, layout, and read-only/writable authority.
- [x] 9.2 Validate an existing direct document through the same codec/layout/validator path while creating no state record, space, topology, pack, lease, or lifecycle generation.
- [x] 9.3 Add explicit missing-document initialization requiring writable authority and a complete valid initial mapping; atomically create only an absent path and never truncate existing content.
- [x] 9.4 Define the permitted parent-directory creation boundary and reject traversal, symlink escape, broad roots, non-file targets, and competing path creation.
- [x] 9.5 Reuse managed configuration, data/cache, mutation, conflict, and outcome behavior for direct sessions without pretending they have space context.
- [x] 9.6 Add a dedicated YAML fixture equivalent to root-level `zpp.behave.yaml` and prove it binds wholly to `zpp.behave` without a wrapper or persistent OpenLease record.

## 10. Add Confined Data Cache and Optional Batch

- [x] 10.1 Define versioned data/cache record envelopes and a closed logical-key grammar.
- [x] 10.2 Implement path confinement beneath selected extension roots, rejecting absolute/parent/device/alternate-separator paths, symlink escape, cross-extension access, and unowned replacement/deletion.
- [x] 10.3 Implement current reads and immediate atomic assignments/deletions with durable ownership and explicit cache disposability.
- [x] 10.4 Ensure completed direct configuration/data/cache writes remain published after later handler failure and are reported separately.
- [x] 10.5 Implement an explicitly entered optional batch for bounded managed records only, with clear committed/uncommitted/recovery-required dispositions.
- [x] 10.6 Create a recovery journal only when a multi-file batch requires it; prove ordinary assignments create no staging directory or journal.
- [x] 10.7 Prove batches cannot claim atomicity over subprocess, Git, network, or arbitrary filesystem effects.

## 11. Implement Named Operations and Outcomes

- [x] 11.1 Add explicit library invocation for one registered operation with opaque input, exact direct or space-scoped target, and optional writable selection.
- [x] 11.2 Implement the ordered invocation pipeline and phase-specific failures for registration, target, binding, read, decode, layout, overlay, validation, handler, write, batch, and outcome recording.
- [x] 11.3 Pass immutable contexts and narrow managed mappings rather than `OpenLease`, the state repository, Git adapter, or lifecycle mutators.
- [x] 11.4 Return opaque handler values separately from deterministic runtime metadata and never serialize them into central lifecycle state.
- [x] 11.5 Define/store bounded versioned extension-owned outcome envelopes with identities, target, generations, binding digests, callback mode, handler status, write dispositions, and diagnostics.
- [x] 11.6 Implement per-extension retention while preserving records referenced by unresolved optional batch recovery.
- [x] 11.7 Report outcome-recording failure after effects without retrying a handler, duplicating writes, or claiming rollback.
- [x] 11.8 Prove operation failure leaves unrelated lifecycle and configuration operations available.

## 12. Add Explicit Callback Selection

- [x] 12.1 Add the closed event enum for `reconcile.before_repository`, `reconcile.after_repository`, and `reconcile.after_cohort`.
- [x] 12.2 Add selections naming extension, operation, event, mode, and exact repository/cohort target; never select from registration or configuration.
- [x] 12.3 Resolve fresh target contexts and deterministic isolated cohort target contexts for every selected callback.
- [x] 12.4 Dispatch observational callbacks deterministically, continue after observational failures, and report every outcome without gating lifecycle state.
- [x] 12.5 Permit gating only for `reconcile.before_repository`, stop before that repository's Git mutation on failure, and reject post-event gates during planning.
- [x] 12.6 Prove callbacks cannot acquire/release leases, mutate topology/affected claims, choose worktrees/refs/strategies, stage/commit/merge/rebase, resolve conflicts, alter reconciliation state, finalize work, or invoke extensions implicitly.

## 13. Replace Reconciliation Verification Integration

- [x] 13.1 Remove the constructor verifier argument, stored verifier callable, verification compatibility reporting, and all adapter tests.
- [x] 13.2 Identify and retain intrinsic OpenLease plan, Git-result, state-consistency, checkout, and ownership checks as core reconciliation behavior.
- [x] 13.3 Add callback selections separately from `ReconcileSelection`; keep repository, destination, path, and merge/rebase strategy solely in the Git leg.
- [x] 13.4 Display exact selected callback identities, modes, targets, and order in read-only plans and bind them to current registration/context evidence.
- [x] 13.5 Reject callback drift before any Git mutation during apply re-planning.
- [x] 13.6 Dispatch before-repository after plan validation and before Git mutation, after-repository after ordinary reconciled recording, and after-cohort after ordinary cohort completion.
- [x] 13.7 Preserve only `pending`, `reconciled`, and `abandoned` member statuses; add no unverified, callback-retry, or callback-finalization state.
- [x] 13.8 Add integration tests for no callback, observational successes/failures, pre-gate failure, unsupported post gate, registration drift, Git conflict, and configuration that mentions merging without authorizing it.

## 14. Public Surface Documentation and Completion

- [x] 14.1 Export all current runtime, codec, binding, managed mapping, callback, target, result, and outcome contracts and remove every former resolver/verifier export.
- [x] 14.2 Update deterministic result serialization for enums, paths, immutable mappings, codec/layout provenance, callback selections, conflicts, and write dispositions.
- [x] 14.3 Update CLI inputs/help/JSON for explicit codec/layout/write binding and callback selections only where executable registrations exist; never add dynamic handler discovery.
- [x] 14.4 Document equivalent shared YAML/TOML/JSON, dedicated documents, quoted TOML dotted identities, shallow overlay, exact writable selection, shadowed writes, automatic assignment, conflicts, defensive nested values, direct sessions, and optional batches.
- [x] 14.5 Document the hard reset/reinitialization boundary and remove every promise of resolver, old-state, opaque-source, or injected-verifier compatibility.
- [x] 14.6 Add downstream probes for separate `zpp.traits` and `zpp.behave` registrations, dedicated `zpp.behave.yaml`, and opaque Nx/Go Task/argv configuration without importing ZPP or runners.
- [x] 14.7 Run focused configuration, codec, locking, storage, state, runtime, outcome, and reconciliation unit/integration suites.
- [x] 14.8 Run every Behave root, complete pytest, Ruff lint, Ruff formatting, dependency-lock consistency, and package build.
- [x] 14.9 Verify base install/import on Python 3.11 and the current development interpreter without optional CLI dependencies.
- [x] 14.10 Run strict OpenSpec validation and confirm no compatibility path, implicit callback, implicit staging, post-mutation gate, extension-owned Git behavior, or product runner policy remains.

