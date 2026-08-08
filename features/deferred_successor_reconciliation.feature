Feature: Defer and reconcile affected branch cohorts
  OpenLease users can prepare blocked work without weakening authority exclusion,
  then integrate every generated branch through an explicit merge path.

  Scenario: Isolate compatible child work on another branch
    Given child A is lockable while child B work uses the canonical repo 1 checkout
    When the owner isolates the child A space with a successor name
    Then OpenLease creates one repo 1 worktree for the affected child A claim
    And atomically locks child A in the successor
    And leaves child B's space and checkout unchanged

  Scenario: Defer only repositories in the affected closure
    Given repo 1, repo 2, and repo 3 are associated
    And the affected closure contains only child A in repo 1
    And the selected space is non-lockable
    When the owner defers it with an unused successor name
    Then OpenLease creates one branch and linked worktree for repo 1
    And records repo 2 and repo 3 as pinned context without generated worktrees
    And publishes a distinct deferred successor space with no leases

  Scenario: Wire an affected consumer to its successor authority host
    Given affected repo 2 requires writable use of the authority hosted by repo 3
    And the selected space is non-lockable
    When the owner defers it
    Then OpenLease creates affected worktrees for repo 2 and repo 3
    And wires repo 2 to the authority path in the repo 3 successor worktree
    And leaves the source space and shared OpenSpec registration unchanged

  Scenario Outline: Select the GitHub Desktop-style branch source per repository
    Given a non-lockable affected repository needs a successor worktree
    When the owner defers it with <branch selection>
    Then OpenLease creates the worktree using <branch result>

    Examples:
      | branch selection     | branch result                                  |
      | no branch            | a new same-named branch from the starting head |
      | an available local   | that existing local branch                     |
      | a resolvable remote  | a corresponding local branch from that remote  |

  Scenario: Reject a deferred destination collision without partial publication
    Given one affected repository's derived path or selected branch is unavailable
    When the owner defers the complete affected closure
    Then OpenLease does not overwrite or reuse the collision
    And leaves the source space unchanged
    And publishes no usable deferred successor

  Scenario: Retain a preparation journal after incomplete rollback
    Given deferral created one affected worktree before a later repository failed
    And OpenLease cannot prove that every created artifact is unchanged and clean
    When preparation recovery runs
    Then OpenLease preserves the uncertain artifacts
    And records a non-writable preparation-failed successor
    And supports explicit resume or rollback

  Scenario: Keep a deferred successor blocked by logical authority
    Given a deferred successor uses different worktree paths from its blocker
    When the blocker still owns one requested logical authority
    Then lockable remains false for that authority
    And the successor cannot perform OpenLease-governed protected mutation

  Scenario: Release alone does not promote stale deferred work
    Given a blocker releases before its authority changes receive an integrated, abandoned, or superseded disposition
    When the deferred successor runs lockable
    Then promotion remains unavailable
    And status reports the unresolved blocker handoff

  Scenario: Explicitly promote a fresh deferred successor
    Given every blocker has an acceptable disposition
    And the clean successor baselines include every integrated blocker commit
    And the graph and lease generations still match
    When the owner explicitly runs lock
    Then OpenLease atomically acquires the complete affected closure
    And records the successor as locked

  Scenario: Refuse to promote modified deferred work
    Given an unleased deferred worktree contains user changes
    When the owner attempts lock
    Then OpenLease identifies the dirty member and rejects promotion
    And preserves all work

  Scenario: Refuse to promote drifted pinned context
    Given a deferred successor pins unrelated repo 2 context
    And the pinned repo 2 checkout moves from its recorded commit
    When the deferred successor runs lockable
    Then promotion remains unavailable
    And status reports the pinned repo 2 drift

  Scenario: Release generated work into reconciliation debt
    Given a locked successor has generated branches and worktrees
    When the owner releases it
    Then OpenLease removes its leases and owned projection
    And preserves every generated affected branch and worktree
    And records each generated member as pending reconciliation

  Scenario: Plan an explicit later merge path
    Given a released successor has pending generated branches
    When the owner supplies an ordered destination and merge-or-rebase strategy for each selected branch
    Then reconcile plans every source-to-destination leg against the current destination commits
    And reports divergence, dirty worktrees, missing branches, likely textual conflicts, and verification
    And does not mutate Git during planning

  Scenario: Default the visible plan order from provider to consumer
    Given repo 2 depends on the affected authority hosted by repo 3
    When the owner plans reconciliation without overriding dependency order
    Then the visible plan orders repo 3 before repo 2
    And the owner may provide a different complete order before applying it

  Scenario: Stop reconciliation at the first Git conflict
    Given an accepted merge path spans several affected repositories
    When one reconciliation leg encounters a Git conflict
    Then OpenLease preserves that conflict for explicit resolution
    And leaves every later repository untouched and pending
    And retains the complete cohort record

  Scenario: Finalize only fully disposed generated work
    Given a released space has generated affected members
    When any branch lacks a reconciled or abandoned disposition or any generated worktree remains
    Then finalization is rejected with the outstanding members
    When every branch has a disposition and every owned worktree is gone
    Then the owner can finalize the released space record

  Scenario: Force recovery preserves reconciliation evidence
    Given a locked space was abandoned after terminal loss
    And its generated worktrees may contain dirty files
    When the owner explicitly force-recovers that space
    Then OpenLease releases only its owned machine-local leases and intact projection
    And preserves its branches, worktrees, dirty files, and reconciliation records
