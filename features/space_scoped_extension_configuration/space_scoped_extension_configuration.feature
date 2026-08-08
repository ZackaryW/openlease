@space-scoped-extension-configuration
Feature: Resolve extension configuration from an OpenLease space
  Host applications can delegate generic configuration and path resolution to
  OpenLease while retaining ownership of their product-specific semantics.

  Scenario: Register one bounded host extension
    Given a host explicitly registers a namespaced extension with a supported contract version
    When the host requests that extension through OpenLease
    Then OpenLease makes only that registered namespace available
    And does not discover globally installed extension code

  Scenario Outline: Reject an unsafe extension set before context resolution
    Given a host supplies <registration problem>
    When the host constructs OpenLease
    Then OpenLease rejects the complete extension set
    And no extension context is resolved

    Examples:
      | registration problem              |
      | duplicate extension identities    |
      | an unsupported contract version   |

  Scenario: Resolve nested authority configuration without sibling leakage
    Given repo 1 has machine configuration, two ordered space packs, repository configuration, root authority configuration, and distinct child A and child B configuration
    And one space targets child A
    When the host requests child A context for its extension
    Then the documents are ordered from machine through both packs, repository, root, and child A scopes
    And child B configuration is excluded
    And OpenLease preserves each opaque document for extension-owned interpretation

  Scenario: Keep configuration scopes separate from lease ownership
    Given root, child A, and child B configuration scopes participate in one durable space
    When the host attaches a reusable configuration pack and resolves each child separately
    Then the pack participates between machine and repository configuration for both children
    And no configuration scope or pack becomes a child space or leased authority
    And the affected claim remains unchanged

  Scenario: Resolve immutable context against effective member paths
    Given a successor space has one generated repository member and one pinned repository member
    When the host requests an explicit repository or authority context
    Then generated authorities use their recorded effective worktree paths
    And pinned authorities use their exact recorded context paths
    And the result includes immutable relationship, access, branch, and commit provenance

  Scenario: Follow repository configuration into a successor worktree
    Given an extension source is appointed at a repository-relative path in a source checkout
    And the selected successor records a generated worktree for that repository
    When the host resolves extension context in the successor
    Then OpenLease reads the same relative source beneath the effective worktree
    And does not copy, adopt, rewrite, or lease the source

  Scenario: Retain an exact external configuration source
    Given a readable extension source is appointed outside every registered repository
    When the host resolves extension context
    Then OpenLease reads that exact canonical machine-local path
    And does not associate the path with a repository or lease

  Scenario: Reject an unavailable source atomically
    Given a custom configuration source is missing or unreadable
    When the host appoints that source
    Then OpenLease rejects the complete binding
    And retains no partial configuration record

  Scenario: Observe configuration edits live while locked
    Given a locked space has resolved an attached configuration pack
    When the pack content changes and the host requests context again
    Then OpenLease returns the current content with a changed observed generation and digest
    And does not require a refresh operation
    And leaves the lease, graph generation, affected claim, and worktree records unchanged

  Scenario: Refuse stale configuration after a source disappears
    Given a configuration source was resolved previously and is now unavailable
    When the host requests extension context again
    Then OpenLease fails the request without returning cached source content
    And independent lock, release, recovery, and reconciliation operations remain available

  Scenario: Preserve a dependent product root
    Given rebuilt ZPP appoints one `.zpp` product root for OpenLease state and extension storage
    When OpenLease resolves the ZPP extension roots
    Then configuration, data, and cache paths are separately namespaced beneath the appointed root
    And each resolved path reports whether it was defaulted, product-root-derived, or explicitly overridden
    And no pre-existing content is overwritten or treated as owned

  Scenario: Override extension roots independently
    Given a host appoints distinct configuration, data, and cache paths for one extension
    When OpenLease resolves that extension's storage
    Then it returns each exact canonical path with its separate role and provenance
    And keeps other extension namespaces inaccessible

  Scenario: Keep provider configuration outside dependent context
    Given repo 2 depends on an OpenSpec authority hosted by repo 3
    And both repositories have configuration for the same extension
    When the host requests repo 2 context
    Then the dependency relationship is reported
    And repo 3 configuration is excluded
    When the host explicitly requests the repo 3 provider authority
    Then OpenLease resolves repo 3 through its own scope chain

  Scenario: Isolate extension failure from lifecycle authority
    Given a registered extension fails while interpreting an immutable context
    When OpenLease reports the extension request failure
    Then the extension has not acquired or released leases
    And has not changed topology, affected claims, worktree destinations, lifecycle state, or reconciliation state
    And the owner can continue independent lifecycle operations
