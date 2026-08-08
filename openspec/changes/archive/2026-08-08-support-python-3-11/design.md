## Context

See `proposal.md` for motivation. The package currently declares `requires-python = ">=3.14"`, the lockfile repeats that floor, and Ruff formats for `py314`. Repository inspection found two unparenthesized multi-exception clauses that use syntax added in Python 3.14; the remaining Python sources parse with the Python 3.11 grammar once those clauses use the traditional parenthesized form. A dry dependency resolution against CPython 3.11.15 accepts the current runtime, CLI, test, behavior, lint, and build dependency ranges.

## Goals / Non-Goals

**Goals:**

- Make package metadata, source grammar, formatting, dependency resolution, and documentation agree on Python 3.11 as the minimum.
- Prove the built base distribution and optional CLI work on Python 3.11 while retaining the current development-interpreter verification.
- Keep one source tree and one public contract across the supported range.

**Non-Goals:**

- Adding compatibility shims for interpreters older than Python 3.11.
- Changing public APIs, state schemas, lifecycle behavior, or extension semantics.
- Introducing a new runtime dependency or a version-specific implementation fork.
- Claiming support for alternative Python implementations that the project does not otherwise test.

## Decisions

### Make Python 3.11 the single compatibility floor

Set project metadata and the generated lock state to `>=3.11`, and set Ruff's target version to `py311`. Keeping different floors for packaging, locking, or formatting was rejected because a formatter can otherwise reintroduce syntax that the declared interpreter cannot parse.

### Backport syntax without branching product behavior

Use syntax accepted by Python 3.11 throughout shipped source and repository-owned verification code. The two current multi-exception clauses will use parenthesized exception tuples. Conditional runtime branches or compatibility packages were rejected because the current behavior needs no version-dependent implementation.

### Verify the minimum and current development interpreters

Treat Python 3.11 as the compatibility gate: resolve the complete dependency set, run unit/integration and governed behavior verification, build distributions, inspect the built `Requires-Python` metadata, and smoke-test the base import and optional CLI from isolated Python 3.11 environments. Retain the established full verification on the current development interpreter to catch regressions at the other end of the actively exercised range. Running every intermediate minor in the local workflow was rejected as redundant for this small syntax-only backport; a future CI matrix may add them without changing the product contract.

### Regenerate rather than hand-edit lock metadata

Regenerate `uv.lock` from the lowered project constraint and retain dependency versions that resolve for Python 3.11. Hand-editing only the lockfile header was rejected because transitive package markers and artifacts must be resolved consistently with the new range.

## Risks / Trade-offs

- [A future dependency release drops Python 3.11] → Keep the declared dependency range resolvable through the lockfile and add a compatible upper bound only if resolution evidence requires one.
- [A newer formatter introduces post-3.11 syntax] → Keep Ruff targeted at `py311` and include its check in the acceptance gate.
- [Metadata changes while the wheel remains unusable on 3.11] → Install and exercise the built artifacts with the actual Python 3.11 interpreter rather than relying only on source parsing.
- [Testing only range endpoints misses an intermediate-version issue] → Keep code within the 3.11 grammar and dependency markers; add intermediate CI jobs if later platform evidence reveals a version-specific failure.

## Migration Plan

1. Lower the project and toolchain version declarations and regenerate the lockfile.
2. Replace the two Python 3.14-only clauses and confirm the entire repository parses and formats for Python 3.11.
3. Run the Python 3.11 distribution, test, CLI, and behavior gates, followed by the established current-interpreter checks.
4. Update installation documentation only after the minimum-version gates pass.

No state or user-data migration is required. Rollback raises the package requirement and Ruff target to Python 3.14 and regenerates the lockfile; it does not alter persisted OpenLease data.
