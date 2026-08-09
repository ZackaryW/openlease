@bounded-extension-runtime
Feature: Invoke explicitly registered bounded extensions
  OpenLease provides narrow managed configuration and storage without making
  registration or configuration an execution or lifecycle authority.

  Scenario: Version-three registration is inert
    Given two version-three extensions declare named operations
    When the host constructs the bounded runtime
    Then both exact identities are registered
    And no validator operation callback managed write or lifecycle action runs

  Scenario: Reject a version-two registration
    Given a version-two extension declares a named operation
    When the host attempts to construct the bounded runtime
    Then registration fails with version-three guidance
    And no extension code or managed write runs

  Scenario: Configuration presence does not activate an operation
    Given a registered operation and configuration that names a runner
    When the host binds the configuration without invoking the operation
    Then the operation has not run
    When the host explicitly invokes the named operation
    Then exactly that operation runs once with opaque input

  Scenario: Validate effective configuration before handler effects
    Given an extension validator rejects the bound configuration
    When the host attempts to bind the extension
    Then validation fails before the handler starts
    And the error is configuration_validation_failed
    And no managed record is created

  Scenario: Explain effective configuration through the public contract
    Given a bound extension with ordered configuration sources
    When the host requests its public configuration snapshot record
    Then the record identifies every binding and the winning source for each key
    And configuration exposes result-returning mutations while data and cache do not

  Scenario: Return the completed explicit configuration write
    Given a bound extension with one writable configuration source
    When the host explicitly sets and deletes configuration keys
    Then each call returns its exact completed write disposition
    And mapping assignment still saves automatically

  Scenario: Convert managed configuration for downstream validation
    Given an immutable managed configuration snapshot with nested values
    When a dependent product converts it through the public plain-value helper
    Then it receives independent ordinary dictionaries and lists
    And supported scalar values retain their meaning

  Scenario: Preserve completed writes after handler failure
    Given an operation writes durable data and cache before failing
    When the host explicitly invokes that operation
    Then the result reports a failed handler and both committed writes
    And both current managed records remain readable

  Scenario: Reject cross-namespace managed keys
    Given an operation attempts parent traversal through durable data
    When the host explicitly invokes that operation
    Then the handler fails without creating content outside its extension root
    And unrelated lifecycle commands remain available

  Scenario: Batch only when explicitly entered
    Given an operation can perform two managed assignments
    When it performs an ordinary assignment
    Then no staging or recovery journal is created
    When it explicitly enters a successful bounded batch
    Then both batched records are committed
    And the batch claims no Git process network or arbitrary filesystem atomicity

  Scenario: Store bounded outcomes without opaque values
    Given a named operation returns an opaque non-JSON object
    When the host explicitly invokes that operation
    Then the opaque value is returned separately
    And the inspectable outcome contains runtime metadata but not the opaque value

  Scenario: Extension code receives no lifecycle authority
    Given a named operation inspects its invocation capabilities
    When the host explicitly invokes that operation
    Then it receives only immutable context and managed mappings
    And cannot acquire leases mutate topology or perform Git integration through them
