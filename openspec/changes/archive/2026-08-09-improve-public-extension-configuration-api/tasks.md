## 1. Establish the version-three public contract

- [x] 1.1 Add fail-first public-contract tests for extension contract version 3, rejection of version-2 registrations, and configuration/data/cache protocol typing.
- [x] 1.2 Define the public `ManagedConfiguration` protocol, advance `EXTENSION_CONTRACT_VERSION` to 3, and type bound-extension and invocation configuration through the new protocol.
- [x] 1.3 Move the concrete managed-configuration implementation behind a private runtime boundary and update runtime construction without exposing a public constructor.

## 2. Expose provenance and result-returning mutations

- [x] 2.1 Add fail-first tests proving `snapshot_record()` is available through the public protocol and returns coherent values, binding provenance, winners, digests, and generations.
- [x] 2.2 Add fail-first tests proving `set()` and `delete()` return the exact completed `WriteDisposition` while mapping assignment and deletion retain automatic persistence and `last_write` behavior.
- [x] 2.3 Implement public provenance access and route explicit and mapping mutations through one validation, conflict-detection, confinement, publication, and baseline-refresh path.

## 3. Publish structured configuration failures

- [x] 3.1 Add fail-first library tests for the five public configuration error categories, their stable codes, structured context, exception chaining, and `InvalidRequest` compatibility.
- [x] 3.2 Implement `ConfigurationReadOnly`, `ConfigurationValidationFailed`, `ConfigurationPathChanged`, `ConfigurationDecodeFailed`, and `ConfigurationConflict`, and translate extension configuration entry-point failures without changing standalone codec errors.
- [x] 3.3 Add fail-first CLI tests and emit top-level configuration error `code` values in JSON while preserving existing messages, `invalid_request` outcomes, and exit status 2.

## 4. Export managed-value conversion

- [x] 4.1 Add fail-first tests for nested immutable-to-plain conversion, scalar preservation, source immutability, codec-container exclusion, and rejection of unsupported values.
- [x] 4.2 Implement and export strict `to_plain_managed_value`, sharing safe recursion where appropriate without admitting arbitrary codec `unwrap()` objects to the public managed-value boundary.

## 5. Add reusable direct-document bindings

- [x] 5.1 Add fail-first tests for frozen `ExtensionDocumentBinding` construction, existing-document binding, absent-document initialization, and explicit codec/layout requirements.
- [x] 5.2 Implement the immutable binding value and additive open/initialization overloads, normalizing object and scalar calls through one internal specification.
- [x] 5.3 Reject mixed object/scalar binding arguments and inconsistent initialization authority before filesystem access, while preserving existing scalar-call behavior without deprecation.

## 6. Integrate, document, and verify

- [x] 6.1 Update public exports, type declarations, API documentation, examples, and version-3 migration guidance for the configuration protocol, errors, conversion helper, and binding object.
- [x] 6.2 Add or update BDD feature scenarios and `zpp.behave.yaml` affected-verification mappings so every changed capability is covered by complete verification.
- [x] 6.3 Run focused unit, integration, CLI, typing, and BDD tests under Python 3.11 and the current development Python, then run the repository's complete lint and mapped audit gates.
