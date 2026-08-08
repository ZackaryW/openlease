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

