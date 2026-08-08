## MODIFIED Requirements

### Requirement: Library-first optional CLI distribution
The product SHALL expose the complete lifecycle through an importable Python library returning deterministic structured results. The distribution SHALL declare Python 3.11 as its minimum supported interpreter without imposing an upper version bound. The base library and every required runtime dependency SHALL remain installable and operational on Python 3.11 or newer, and the base installation SHALL NOT require the optional CLI dependency.

The product SHALL provide an optional Typer CLI that is installable on the same declared interpreter range, delegates to the same public lifecycle, supports machine-readable JSON output, maps expected domain failures to stable nonzero statuses without tracebacks, and accepts explicit state-root and destination overrides for isolated automation without weakening ownership checks. Expanding interpreter compatibility SHALL NOT change public APIs, persisted state formats, lifecycle results, CLI semantics, or extension contracts.

#### Scenario: Use the library without CLI dependencies
- **WHEN** a consumer installs and imports the base package without the optional CLI dependency
- **THEN** the public OpenLease lifecycle remains usable without importing Typer

#### Scenario: Install the base library on Python 3.11
- **WHEN** a consumer installs and imports the base OpenLease package with Python 3.11
- **THEN** installation succeeds and the public lifecycle is available with the same observable contract as on a newer supported interpreter

#### Scenario: Use the optional CLI on Python 3.11
- **WHEN** a consumer installs the CLI extra and invokes OpenLease with Python 3.11
- **THEN** the command surface delegates to the public lifecycle and preserves its documented structured and machine-readable results

#### Scenario: Reject an interpreter below the supported floor
- **WHEN** package metadata is evaluated for an interpreter older than Python 3.11
- **THEN** installation is rejected as outside the declared supported range
