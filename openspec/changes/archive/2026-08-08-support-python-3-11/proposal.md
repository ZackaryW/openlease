## Why

OpenLease currently declares Python 3.14 as its minimum even though its runtime and dependency model can support Python 3.11 with a small syntax backport. The unnecessarily high floor prevents Python 3.11, 3.12, and 3.13 consumers from installing the library or optional CLI.

## What Changes

- Lower the distributed package's minimum supported interpreter from Python 3.14 to Python 3.11, without adding an upper bound.
- Keep the base library and optional CLI behavior available throughout the declared interpreter range.
- Remove Python 3.14-only source syntax and align the formatter, linter, dependency lock, documentation, and build metadata with the Python 3.11 floor.
- Verify the complete product behavior on Python 3.11 and retain verification on the repository's current development interpreter.
- Preserve all public APIs, persisted state formats, lease semantics, and command behavior; this is a compatibility expansion, not a behavioral redesign.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `relational-workset-lifecycle`: Extend the library-first optional CLI distribution requirement so the base package and CLI are installable and operational with Python 3.11 and later supported interpreters.

## Impact

- Affects package metadata and lock state in `pyproject.toml` and `uv.lock`, the documented installation requirement, and the Ruff target version.
- Requires replacing the two currently detected Python 3.14-only multi-exception clauses with Python 3.11-compatible syntax.
- Requires minimum-version test, behavior, lint, formatting, and build verification; dependency resolution already succeeds for the complete current runtime and development dependency set on Python 3.11.
- Does not change OpenLease's public Python surface, optional CLI contract, serialized state, OpenSpec integration, Git behavior, or extension contract.

## Unresolved — Do Not Assume

None. The requested floor is Python 3.11, the declared range remains open-ended above that floor, and compatibility applies to both the base library and the optional CLI.
