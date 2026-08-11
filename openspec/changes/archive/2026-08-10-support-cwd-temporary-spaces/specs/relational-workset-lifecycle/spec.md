## ADDED Requirements

### Requirement: Session-scoped cwd space selection
When no explicit space is selected, OpenLease SHALL accept a current working directory and opaque host-session token as temporary selection context. It SHALL resolve the directory to exactly one registered Git worktree and repository identity, then atomically reuse a temporary space already owned by that token for the same canonical worktree, reclaim an eligible inactive temporary space for that worktree, or scaffold a new temporary draft associated with that repository. Explicit space selection SHALL take precedence. Cwd selection SHALL NOT infer or persist repository registrations, OpenSpec authorities, topology relationships, or an affected claim.

#### Scenario: Reuse one temporary space within a host session
- **WHEN** repeated commands omit explicit space selection and supply the same host-session token from directories within one registered worktree
- **THEN** OpenLease selects the same temporary space for every command without creating duplicate drafts

#### Scenario: Preserve explicit selection precedence
- **WHEN** a command supplies an explicit space together with cwd and host-session context
- **THEN** OpenLease selects the explicit space without creating, reclaiming, or selecting a temporary space

#### Scenario: Reject an unresolved cwd
- **WHEN** cwd is outside every registered Git worktree or resolves ambiguously to multiple repository registrations
- **THEN** OpenLease rejects implicit selection without creating a space or inferring topology

#### Scenario: Scaffold without inferring affected scope
- **WHEN** cwd resolves to one registered worktree and no reusable or reclaimable temporary space exists
- **THEN** OpenLease creates a temporary draft associated with that repository and leaves its affected repository and authority claims empty

### Requirement: Safe temporary-space reclamation
OpenLease SHALL reclaim a matching inactive temporary space only when it has no held lease, generated member, projection ownership, space-scoped configuration source or pack attachment, preparation artifact, blocker, handoff disposition, or reconciliation record. Reclamation SHALL atomically replace its prior session fingerprint with the current session fingerprint while preserving its stable identity and complete draft shape. A matching space that is locked or carries any retained ownership, configuration, or recovery evidence SHALL be preserved, and implicit selection SHALL create a distinct temporary draft instead of adopting or deleting it.

#### Scenario: Reclaim an abandoned clean draft
- **WHEN** a new host session resolves a canonical worktree with an inactive temporary draft that satisfies every disposable condition
- **THEN** OpenLease atomically rebinds that draft to the new session and returns its existing space identity

#### Scenario: Preserve a retained matching space
- **WHEN** a matching prior space holds a lease or contains generated work, projection ownership, space-scoped configuration, preparation evidence, blockers, a handoff disposition, or reconciliation debt
- **THEN** OpenLease preserves that space unchanged and scaffolds a separate temporary draft for the current session

### Requirement: Temporary cleanup and durable promotion
Ending a host session SHALL remove each space owned by that session only when the space still satisfies the complete disposable predicate. An operation that atomically grants a lease or records generated work, projection ownership, space-scoped configuration, preparation evidence, blockers, a handoff disposition, or reconciliation debt SHALL clear temporary ownership in the same transition and retain the space under the ordinary durable lifecycle. Loss of a host process or terminal SHALL NOT release a lease or delete retained state.

#### Scenario: Remove an unused session draft
- **WHEN** a host session ends after its temporary space remained an empty disposable draft
- **THEN** OpenLease removes that temporary space without changing repository topology or any other space

#### Scenario: Promote while acquiring a lease
- **WHEN** a temporary space with an explicit affected claim successfully acquires its complete lease set
- **THEN** OpenLease clears its temporary ownership atomically with lease acquisition and retains it as a durable locked space

#### Scenario: Retain recovery-bearing state at session end
- **WHEN** a formerly temporary space carries any ownership, space-scoped configuration, or recovery evidence when its originating host session ends or disappears
- **THEN** OpenLease retains the durable space and all evidence without releasing, adopting, or deleting it
