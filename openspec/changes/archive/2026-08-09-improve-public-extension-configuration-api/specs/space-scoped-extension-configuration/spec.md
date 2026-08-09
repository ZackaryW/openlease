## ADDED Requirements

### Requirement: Reusable direct document binding specification
OpenLease SHALL expose `ExtensionDocumentBinding` as an immutable typed value describing one direct extension document binding. The value SHALL carry extension identity, document path, explicit codec name, explicit shared or dedicated layout, read-only or writable authority, and optional repository context needed for target provenance. The same value SHALL be accepted when opening an existing document and when explicitly initializing an absent document, with initialization-specific initial content and boundary authority supplied separately.

Constructing or passing the value SHALL NOT infer codec or layout from a filename, content, extension identity, or repository convention. The owning direct-document operation SHALL still perform current registration, codec, layout, path, write-authority, initialization-boundary, and content validation before returning a bound extension or creating content.

The typed binding call forms SHALL be additive. Existing scalar direct binding and initialization calls SHALL remain supported with identical validation and observable results and SHALL NOT be deprecated by this change.

#### Scenario: Open one explicit binding specification
- **WHEN** a host supplies a direct document binding value naming `zpp.behave`, a YAML codec, dedicated layout, its exact path, and writable authority
- **THEN** OpenLease opens that exact binding without repeating the coordinated fields and without inferring behavior from the filename

#### Scenario: Initialize through the same binding specification
- **WHEN** a host supplies a writable direct document binding value for an absent path plus explicit initial content and initialization boundary
- **THEN** OpenLease applies the existing confined initialization contract and returns a binding with the same declared identity, codec, layout, and path provenance

#### Scenario: Preserve scalar direct binding calls
- **WHEN** an existing host supplies extension identity, path, codec, layout, and write authority through the scalar call form
- **THEN** OpenLease applies the same current direct binding contract without a deprecation or forced binding-object migration

#### Scenario: Reject incomplete or inconsistent binding metadata
- **WHEN** a direct document binding value omits explicit codec or layout, requests initialization without writable authority, or conflicts with its operation-specific boundary
- **THEN** OpenLease rejects the request before reading, creating, or mutating a document
