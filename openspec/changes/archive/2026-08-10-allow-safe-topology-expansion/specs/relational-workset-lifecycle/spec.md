## ADDED Requirements

### Requirement: Lease-safe scoped topology expansion
OpenLease SHALL validate each explicit repository, authority, containment, or dependency addition as one candidate authority graph. While leases are active, it SHALL accept the candidate only when every locked space retains the same accepted associated topology, complete affected plan, hierarchical conflict coverage, and held lease set. An unrelated valid addition SHALL NOT be rejected solely because another authority component is leased. A rejected candidate SHALL leave the graph, graph generation, spaces, and leases unchanged.

#### Scenario: Register a disconnected repository while another space is locked
- **WHEN** one space holds leases in a registered authority component and the owner registers a distinct repository and authority with no relationship to that component
- **THEN** OpenLease accepts the new component atomically without changing the locked space or its leases

#### Scenario: Reject a relationship that changes a locked shape
- **WHEN** a candidate containment or dependency addition would change the accepted topology, affected plan, or hierarchical conflict coverage of a locked space
- **THEN** OpenLease rejects the complete addition without advancing the graph generation or changing any lease

#### Scenario: Preserve explicit topology declaration
- **WHEN** an unrelated candidate component is safe to add while another space is locked
- **THEN** the owner must still register every node and relationship explicitly and OpenLease infers no topology from cwd, Git, or OpenSpec metadata

### Requirement: Scoped deferred topology drift
OpenLease SHALL distinguish topology changes that preserve a deferred space's accepted topology and complete affected plan from changes that alter them. When an accepted graph addition is unrelated to a current deferred space, OpenLease SHALL advance that space's accepted graph baseline atomically so the unrelated change alone does not prevent later promotion. When an accepted graph addition changes the deferred space's accepted topology, affected plan, or conflict coverage, OpenLease SHALL retain drift evidence and reject promotion until the space is explicitly replanned or replaced.

#### Scenario: Promote after unrelated graph expansion
- **WHEN** a deferred space remains otherwise promotable after a disconnected repository and authority are registered
- **THEN** the unrelated graph-generation advance does not by itself prevent promotion

#### Scenario: Reject promotion after relevant topology drift
- **WHEN** an accepted graph addition changes a deferred space's complete affected closure or conflict coverage
- **THEN** OpenLease preserves the changed graph but rejects promotion of the stale deferred space
