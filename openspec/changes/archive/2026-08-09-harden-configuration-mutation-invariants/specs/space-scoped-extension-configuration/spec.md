## MODIFIED Requirements

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
