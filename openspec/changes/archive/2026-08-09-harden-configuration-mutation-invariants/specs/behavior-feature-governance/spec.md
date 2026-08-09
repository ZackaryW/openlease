## MODIFIED Requirements

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
