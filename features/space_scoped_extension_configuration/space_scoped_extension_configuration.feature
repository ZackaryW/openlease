@space-scoped-extension-configuration
Feature: Manage explicit extension configuration documents
  Hosts can bind current YAML, TOML, and JSON documents without transferring
  product semantics, lifecycle ownership, or implicit execution to OpenLease.

  Scenario Outline: Decode equivalent explicit built-in formats
    Given a current extension and a dedicated <codec> document
    When the host binds that direct document read-only
    Then the effective configuration contains the equivalent managed values
    And no persistent space or configuration binding is created

    Examples:
      | codec |
      | yaml  |
      | toml  |
      | json  |

  Scenario: Preserve exact shared identities and unrelated namespaces
    Given a shared TOML document with nested zpp and exact dotted zpp.behave tables
    When zpp.behave updates its exact shared namespace
    Then the nested zpp table and comments remain unrelated
    And the dotted identity remains one quoted TOML key

  Scenario: Overlay space sources shallowly in authority order
    Given current machine repository root and child configuration bindings
    When the host binds child A configuration
    Then later top-level keys replace earlier complete nested values
    And child B configuration does not participate

  Scenario: Save automatically to one exact writable source
    Given two writable sources for one space-scoped extension
    When the host selects the lower source and assigns a shadowed key
    Then the lower source is published without a save call
    And the higher source remains the effective winner

  Scenario: Rebase an unrelated shared document change
    Given two extensions observe different namespaces in one writable JSON document
    When both extensions assign their own keys
    Then both completed namespaces remain in the shared document

  Scenario: Reject a same-key conflict
    Given two handles observe the same writable configuration key
    When both handles assign different replacements
    Then the second assignment reports configuration_conflict
    And the first replacement remains authoritative

  Scenario: Reject a same-key conflict whose baseline was absent
    Given two handles observe one writable configuration without the new key
    When both handles assign different replacements
    Then the second assignment reports configuration_conflict
    And the first replacement remains authoritative

  Scenario: Reject a writable path replaced by an escaping symlink
    Given a writable document is bound before its path becomes an escaping symlink
    When the caller assigns through the replaced binding
    Then the configuration mutation reports configuration_path_changed
    And the symlink and its external target remain unchanged

  Scenario: Reject mutation through a read-only configuration
    Given a direct read-only configuration document
    When the caller explicitly sets a configuration key
    Then the mutation reports configuration_read_only
    And the source document remains unchanged

  Scenario: Report a decode failure through CLI JSON
    Given an invalid explicitly declared configuration document
    When the host binds it through the JSON CLI
    Then the CLI reports configuration_decode_failed with an invalid_request outcome
    And exits with status 2

  Scenario: Keep nested reads defensive
    Given a direct dedicated document contains a nested mapping
    When a caller attempts in-place mutation of the returned nested value
    Then the value is immutable
    And the source document remains unchanged

  Scenario: Initialize one missing direct document explicitly
    Given a current extension and an absent dedicated YAML path
    When the host explicitly initializes that writable document
    Then exactly that document is created with the initial mapping
    And a repeated initialization does not truncate it

  Scenario: Reuse one immutable direct-document binding
    Given an explicit binding value with codec layout path and write authority
    When the host opens and initializes documents through that binding shape
    Then both operations preserve the declared binding metadata
    And neither codec nor layout is inferred

  Scenario: Preserve scalar direct-document calls
    Given equivalent object and scalar direct-document bindings
    When the host opens each existing document
    Then both forms produce the same configuration and provenance
    And the scalar form is not deprecated

  Scenario: Reject prior state without touching referenced documents
    Given a prior-schema state references an authored YAML document
    When current OpenLease opens that state
    Then it requests reinitialization without a compatibility decoder
    And the authored YAML document is unchanged

  Scenario: Preserve a dependent product root
    Given a current extension uses a custom product root
    When OpenLease resolves its extension storage
    Then configuration data and cache roots are separately namespaced beneath it
    And no ZPP-specific home resolver is required
