## ADDED Requirements

### Requirement: Implicit selection preserves collision authority
A cwd-selected temporary space SHALL begin without an affected claim or held lease. The host-session token, current directory, worktree, association, and temporary-space ownership SHALL NOT constitute writable authority. Before `lockable`, `lock`, or `defer`, the space SHALL satisfy the same explicit affected-claim, complete planning, topology, and logical lease-conflict rules as an explicitly selected durable space.

#### Scenario: Do not lease from cwd selection
- **WHEN** implicit selection scaffolds or reclaims a temporary space for a registered worktree
- **THEN** the space holds no authority and cannot perform a protected mutation until its affected claim is explicitly declared and its complete lease is acquired

#### Scenario: Report the same logical conflict
- **WHEN** a cwd-selected temporary space explicitly affects an authority already covered by another active lease
- **THEN** `lockable` and `lock` report the same logical conflict they would report for an explicitly selected durable space

#### Scenario: Allow an unrelated temporary plan
- **WHEN** a cwd-selected temporary space explicitly affects an authority component disconnected from every active lease owner's conflict coverage
- **THEN** its plan is not blocked solely because another component has an active lease
