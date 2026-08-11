@relational-workset-lifecycle
Feature: Build relational OpenLease spaces
  OpenLease users can compose repositories and OpenSpec authorities into durable
  spaces without flattening their containment and dependency relationships.

  Scenario: Register a nested monorepo and an externally hosted authority
    Given repo 1 contains a root OpenSpec authority and child authorities A and B
    And repo 2 consumes an OpenSpec authority hosted by repo 3
    When the owner registers those repositories and authorities
    And relates A and B as children of the repo 1 root
    And relates repo 2 as a consumer of the repo 3 authority
    Then status reports the complete typed authority graph
    And no lease or OpenSpec workset projection is created

  Scenario Outline: Reject an invalid relationship without changing the graph
    Given a valid registered authority graph
    When the owner attempts to add <invalid relationship>
    Then the relationship is rejected
    And the accepted graph generation is unchanged

    Examples:
      | invalid relationship            |
      | a containment cycle             |
      | a dependency cycle              |
      | a second containment parent     |
      | a missing relationship endpoint |
      | an endpoint of the wrong kind   |

  Scenario: Preserve one authority identity across linked worktrees
    Given a registered repository contains a repository-relative OpenSpec authority
    And two linked worktrees share that repository's Git common directory
    When OpenLease inspects the authority through both worktrees
    Then both physical contexts resolve to one logical authority identity

  Scenario: Keep an unlinked clone distinct
    Given two clones have separate Git common directories
    And the owner has not registered them with one shared repository identity
    When OpenLease inspects corresponding OpenSpec paths in both clones
    Then the paths resolve to distinct logical authorities

  Scenario: Use one durable space from multiple terminal processes
    Given a durable OpenLease space is selected in a terminal environment
    When commands run from successive processes in that terminal
    Then they target the same selected space identity
    And no process or TTY identity owns its leases

  Scenario: Preserve a locked space after terminal loss
    Given a terminal selected a locked OpenLease space
    When the terminal exits without releasing it
    Then the space and its leases remain durable
    And later commands can inspect or explicitly recover it

  Scenario: Separate associated context from affected work
    Given repo 1, repo 2, and repo 3 are associated with one space
    When the owner marks only repo 1 child A as affected
    Then status reports all three repositories as associated context
    And reports only child A in the direct affected claim
    And reports the resolved writable authority closure separately

  Scenario: Reject incremental growth of a locked space
    Given a space has atomically locked its complete affected closure
    When the owner tries to add one association or affected target incrementally
    Then OpenLease rejects the mutation
    And preserves the accepted shape and complete lease set

  Scenario: Register a disconnected authority component while another space is locked
    Given a locked space owns one complete authority component
    When the owner explicitly registers a distinct repository and authority without relating them to that component
    Then OpenLease accepts the disconnected authority component atomically
    And preserves the locked space's accepted shape and complete lease set

  Scenario: Preserve deferred promotion across unrelated topology expansion
    Given a deferred space retains its current accepted topology baseline
    When the owner explicitly registers a disconnected repository and authority
    Then the deferred space remains eligible for promotion after its blockers clear

  Scenario: Retain deferred drift after a relevant topology change
    Given a deferred space retains its current accepted topology baseline
    When an accepted topology addition changes its affected closure or conflict coverage
    Then OpenLease retains scoped topology drift for that space
    And rejects its promotion until it is explicitly replanned or replaced

  Scenario: Open one bounded OpenSpec projection
    Given an accepted space has associated affected and pinned members
    When the owner opens the space
    Then OpenLease creates or reuses one owned OpenSpec workset projection
    And the projection contains the distinct effective member folders in planned order
    And OpenLease status retains the relationships omitted by the OpenSpec workset format

  Scenario: Fail closed on a modified projection
    Given an OpenLease-owned projection no longer matches its recorded generation
    When a lifecycle operation would replace or remove that projection
    Then OpenLease reports an ownership conflict
    And preserves the modified projection and unrelated user worksets

  Scenario: Reuse one cwd-selected draft within a host session
    Given a registered repository has no matching temporary space
    When successive commands omit explicit space selection from directories within its worktree and use one host-session token
    Then OpenLease selects one temporary draft associated with that repository
    And the draft has no affected claim or lease
    And no topology is inferred from the working directory

  Scenario: Prefer an explicitly selected durable space
    Given a host-session token and cwd could select a temporary space
    And a durable space is explicitly selected
    When OpenLease resolves the command context
    Then it selects the explicit durable space
    And creates or reclaims no temporary space

  Scenario: Reject cwd outside the registered topology
    Given cwd does not resolve uniquely to one registered Git worktree
    When a command omits explicit space selection
    Then OpenLease rejects implicit selection
    And creates no space or topology

  Scenario: Reclaim an abandoned disposable draft
    Given an ended host session left a clean temporary draft for one canonical worktree
    When a new host session implicitly selects that worktree
    Then OpenLease rebinds the existing draft to the new session atomically
    And preserves its space identity and complete draft shape

  Scenario: Preserve retained state when selecting the same worktree
    Given a prior matching space carries lease or recovery evidence
    When a new host session implicitly selects that worktree
    Then OpenLease preserves the prior space and its evidence unchanged
    And scaffolds a distinct temporary draft for the new session

  Scenario: Remove an unused draft when its host session ends
    Given a host session owns a temporary space that remains fully disposable
    When that host session closes
    Then OpenLease removes only that temporary space
    And preserves registered topology and every other space

  Scenario: Promote temporary work at the first durable boundary
    Given a host session owns a temporary space with a complete explicit affected claim
    When the space atomically acquires its complete lease set
    Then OpenLease clears its temporary ownership in the same transition
    And retains it as a durable locked space after the host session disappears
