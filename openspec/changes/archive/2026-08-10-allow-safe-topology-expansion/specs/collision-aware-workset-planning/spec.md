## ADDED Requirements

### Requirement: Preserve active lease validity during topology expansion
Before persisting an authority-graph addition while leases are active, OpenLease SHALL evaluate the candidate graph against every current lease owner in the same serialized mutation. Each owner SHALL retain its exact complete affected plan and conflict coverage, its held authorities SHALL remain exactly sufficient for that plan, and the candidate graph SHALL introduce no conflict between existing owners. If any condition fails, OpenLease SHALL reject the candidate atomically. The existence of a lease in a disconnected authority component SHALL NOT itself be a conflict or blocker.

#### Scenario: Accept an independent authority component
- **WHEN** a candidate repository and authority are disconnected from every active lease owner's accepted topology and conflict coverage
- **THEN** OpenLease persists the candidate while preserving every existing owner and lease

#### Scenario: Reject a new uncovered writable dependency
- **WHEN** a candidate writable dependency would add an authority to a locked space's required affected closure without adding a corresponding lease atomically
- **THEN** OpenLease rejects the candidate and preserves the original graph and complete lease set

#### Scenario: Reject expanded hierarchy coverage
- **WHEN** a candidate containment relationship would expand or otherwise change the logical conflict coverage of a held authority
- **THEN** OpenLease rejects the candidate even when no second current lease occupies the newly covered scope

#### Scenario: Reject a new conflict between existing owners
- **WHEN** a candidate relationship would make two previously compatible existing lease sets overlap
- **THEN** OpenLease rejects the candidate without changing either owner or lease set
