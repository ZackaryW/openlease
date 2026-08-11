@collision-aware-leasing
Feature: Lease affected OpenSpec authorities without false collisions
  OpenLease users can serialize overlapping specification work while compatible
  child authorities and read-only context remain concurrently usable.

  Scenario: Require explicit topology and an affected claim
    Given a space has associated repositories but no complete explicit authority graph or affected claim
    When the owner runs lockable or lock
    Then OpenLease rejects acquisition without inferring or persisting relationships
    And no lease or projection is added

  Scenario: Expand an affected external authority
    Given repo 2 is affected
    And repo 2 has an explicit writable dependency on the authority hosted by repo 3
    When OpenLease plans the affected closure
    Then the closure includes the repo 3 hosted authority
    And excludes unrelated associated repositories

  Scenario: Share read-only context
    Given two spaces associate the same authority only as read-only context
    When both spaces acquire their affected writable closures
    Then neither acquires the shared read-only authority
    And the read-only overlap does not conflict

  Scenario: Lease sibling authorities concurrently in one monorepo checkout
    Given the repo 1 root authority is unleased
    And one space affects child A
    And another space affects child B
    When both spaces atomically acquire their closures
    Then both acquisitions succeed
    And neither space holds the root or its sibling authority
    And physical checkout overlap alone is not reported as a conflict

  Scenario: Reject a parent and child overlap
    Given one space holds the repo 1 root authority
    When another space requests child A
    Then lockable returns false
    And reports the held root, requested child, hierarchical conflict, and owning space

  Scenario: Report the complete intersection of partially overlapping claims
    Given one active space holds child A and the shared repo 3 authority
    And another affected closure contains child B and the same repo 3 authority
    When the second space runs lockable
    Then child B is reported as compatible
    And the shared repo 3 authority is reported as the conflict
    And no part of the second closure is leased

  Scenario: Competing processes acquire one closure exactly once
    Given two processes request closures containing the same logical authority
    When they attempt lock concurrently
    Then exactly one complete closure becomes locked
    And the other request receives the winning owner and complete conflict set
    And no partial losing lease remains

  Scenario: Worktree substitution does not bypass an authority conflict
    Given another space holds an affected logical authority
    When the requesting space substitutes a different worktree of the same repository
    Then lockable remains false for the same authority

  Scenario: Repeat a compatible lock as a no-op
    Given a selected space already holds the exact accepted affected closure
    When the owner repeats lock
    Then OpenLease returns the existing structured result
    And does not replace identity, starting commits, leases, or projection

  Scenario Outline: Reject topology expansion that changes an active lease boundary
    Given one or more locked spaces hold exact accepted affected closures
    When the owner attempts <lease-changing topology>
    Then OpenLease rejects the complete topology addition
    And preserves the graph generation, locked spaces, and complete lease sets

    Examples:
      | lease-changing topology                                      |
      | a writable dependency that expands a locked affected closure |
      | containment that expands a held authority's conflict coverage |
      | a relationship that makes existing lease owners conflict     |

  Scenario: Detect an affected-authority boundary violation
    Given a space holds only child A
    And its branch changes an OpenSpec file under child B
    When the owner releases or reconciles the space
    Then OpenLease reports the child B path outside the held boundary
    And does not represent the cohort as collision-safe

  Scenario: Grant no authority through implicit cwd selection
    Given implicit cwd selection created a temporary space for a registered worktree
    When the owner has not declared an affected claim
    Then lockable and lock reject acquisition
    And the session token, cwd, association, and temporary ownership grant no lease

  Scenario: Preserve logical conflicts for a temporary space
    Given a cwd-selected temporary space explicitly affects an authority covered by another active lease
    When the temporary space runs lockable or lock
    Then OpenLease reports the same logical conflict as an explicitly selected space
    And no losing lease is acquired

  Scenario: Plan unrelated temporary work beside an active lease
    Given a cwd-selected temporary space explicitly affects a disconnected authority component
    And another component has an active lease
    When the temporary space plans its complete affected closure
    Then the unrelated active lease does not block the plan
