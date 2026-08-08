Feature: Use OpenLease through one library-first lifecycle
  Automation and terminal users receive the same deterministic behavior without
  requiring optional CLI dependencies in library-only installations.

  Scenario: Import the base package without Typer
    Given OpenLease is installed without its CLI extra
    When a Python consumer imports the public package
    Then the import succeeds without importing Typer
    And the complete public lifecycle is available through the library

  Scenario: Delegate CLI commands to the public lifecycle
    Given the optional CLI extra is installed
    When a user runs a topology, space, lease, defer, or reconcile command
    Then the command delegates to the same public library lifecycle
    And no separate CLI-only state transition occurs

  Scenario: Return one stable JSON result envelope
    Given a valid noninteractive command
    When the user requests JSON output
    Then standard output contains one structured result envelope
    And diagnostics are absent from standard output

  Scenario Outline: Map command outcomes to stable process statuses
    Given a command produces <outcome>
    When the command exits
    Then its process status is <status>
    And expected domain failures show no implementation traceback

    Examples:
      | outcome            | status |
      | success            | 0      |
      | compatible no-op   | 0      |
      | invalid request    | 2      |
      | authority conflict | 3      |
      | ownership conflict | 4      |

  Scenario: Override the state root without weakening ownership
    Given isolated automation selects an explicit OpenLease state root and worktree base
    When it runs the public lifecycle
    Then all OpenLease state and generated destinations remain beneath those selections
    And the same identity, collision, ownership, and recovery rules apply

  Scenario: Serialize concurrent local mutations
    Given two processes plan against one state generation
    When both attempt a mutating lifecycle operation
    Then OpenLease serializes the mutations
    And only a process whose observed generation is current may commit its result

