# Behavior Feature Governance Specification

## Purpose

Defines how executable behavior features are owned, isolated, selected, and audited so capability changes remain independently verifiable and suitable for correct affected or cached execution.

## Requirements

### Requirement: Capability-owned behavior roots
Each governed product capability SHALL own an independently executable behavior root containing its feature documents, environment hook surface, and step bindings. A repository-wide step module that registers bindings for multiple capability roots SHALL NOT be the authority for governed behavior.

#### Scenario: Add behavior for one capability
- **WHEN** a contributor adds or changes executable behavior for one capability
- **THEN** its feature and bindings reside in that capability's behavior root without extending a repository-wide binding module

#### Scenario: Execute one capability root
- **WHEN** verification selects one capability target
- **THEN** the runner discovers and executes that root without loading another capability root's step modules

### Requirement: Binding dependency isolation
A capability root SHALL resolve every step used by its feature documents from bindings owned by that root. A capability root SHALL NOT depend on importing or globally registering a step binding owned by another capability root, even when two capabilities use similar wording.

#### Scenario: Reuse equivalent behavior wording
- **WHEN** two capability roots require equivalent domain assertions
- **THEN** each root owns its binding while any implementation-neutral assertion helper may be shared

#### Scenario: Break an unrelated binding module
- **WHEN** a binding module in an unselected capability root is invalid
- **THEN** that module is outside the selected target's discovery and loading boundary

### Requirement: Non-binding shared support
Shared behavior support SHALL contain only fixtures, hooks, adapters, and helper functions that do not register executable steps. Every capability target that consumes a shared support input SHALL declare that input as affecting the target.

#### Scenario: Change a shared fixture
- **WHEN** a shared fixture used by all capability roots changes
- **THEN** affected verification selects every consuming capability target

#### Scenario: Change one root-owned binding
- **WHEN** only one capability root's step binding changes and no shared input changes
- **THEN** affected verification may select only that capability target

### Requirement: Closed and stable capability targets
The committed behavior mapping SHALL declare a closed set of stable target identifiers, with each target resolving to one independently executable capability root. Every governed capability root SHALL have one matching stable target identity in both the affected behavior command and the complete audit command. Runtime impact selection SHALL choose only declared targets and SHALL NOT invent executable command text or undeclared target names.

#### Scenario: Select a declared target
- **WHEN** changed paths map conclusively to one capability root
- **THEN** the configured runner receives that root through its declared target value

#### Scenario: Add a governed capability root
- **WHEN** a governed capability introduces an independently executable behavior root
- **THEN** repository acceptance requires the same stable target identity and root in both affected and complete-audit mappings

#### Scenario: Reject an undeclared target
- **WHEN** selection input names a target outside the committed closed set
- **THEN** verification fails before starting a fallback process

### Requirement: Conservative affected-path mapping
Repository-relative impact rules SHALL map each capability-owned input to its target and each cross-cutting input to every target it can affect. If any changed path is unmapped or its impact is uncertain, affected verification SHALL select the complete declared target set.

#### Scenario: Change capability-owned inputs
- **WHEN** every changed path maps conclusively to one capability target
- **THEN** affected verification selects that target without selecting unrelated targets

#### Scenario: Change an unknown path
- **WHEN** at least one changed path has no conclusive impact rule
- **THEN** affected verification selects all declared capability targets

### Requirement: Separate affected verification and complete audit
The repository SHALL expose an affected behavior command and a separately configured complete audit command. The complete audit target set SHALL match the governed capability target set declared for affected verification and SHALL execute every declared capability root regardless of affected-path selection. Repository acceptance SHALL require the complete audit to pass, and mapping validation SHALL reject an omitted or mismatched governed capability target before treating the audit as complete.

#### Scenario: Run an affected check
- **WHEN** a contributor requests normal affected verification for a capability-local change
- **THEN** only the targets justified by the committed impact mapping execute

#### Scenario: Run the complete audit
- **WHEN** a release, workflow checkpoint, or governance validation requests the complete behavior audit
- **THEN** every declared capability target executes and any failing root fails the audit

#### Scenario: Reject an incomplete audit mapping
- **WHEN** a governed capability target exists in affected verification but is absent from or resolves differently in the complete audit command
- **THEN** governance validation rejects the mapping instead of accepting a partial complete audit

### Requirement: Provider-independent cache boundary
Each capability target SHALL have an independent target identity and explicit input boundary suitable for reuse by a cache-capable provider. The governance contract SHALL NOT claim that results are cached when the established provider does not implement caching, and it SHALL NOT require installation or migration to a different provider merely to satisfy target isolation.

#### Scenario: Use a provider-neutral runner
- **WHEN** the repository has no established cache-capable workspace provider
- **THEN** affected target isolation remains available through the established provider-neutral runner without representing executions as cached

#### Scenario: Adopt compatible caching later
- **WHEN** the repository deliberately establishes a compatible cache-capable provider
- **THEN** the existing capability target identities and impact boundaries can be mapped to that provider without merging the roots into one global binding target

### Requirement: Governance validation precedes execution
The committed behavior mapping and every selected root SHALL be validated before governed execution is accepted. Validation SHALL reject malformed mappings, duplicate declarations, missing target roots, undefined steps, ambiguous steps, and cross-root discovery that violates the declared isolation boundary.

#### Scenario: Validate a well-formed feature structure
- **WHEN** every declared root exists, owns its bindings, and has no undefined or ambiguous steps
- **THEN** governance validation accepts the target structure for affected and complete execution

#### Scenario: Detect a hidden cross-root dependency
- **WHEN** a feature resolves a required step only because an unrelated capability root is loaded
- **THEN** isolated-root validation rejects that capability target
