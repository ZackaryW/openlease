## 1. Establish Python 3.11 Compatibility

- [x] 1.1 Add executable compatibility coverage for the Python 3.11 base-library installation, optional CLI installation, and exact minimum-version metadata boundary.
- [x] 1.2 Lower `project.requires-python` and Ruff's target version to Python 3.11, and replace every source construct that the Python 3.11 grammar rejects without changing runtime behavior.
- [x] 1.3 Regenerate `uv.lock` from the lowered interpreter range and confirm the complete runtime, CLI, test, behavior, lint, and build dependency set resolves on Python 3.11.
- [x] 1.4 Update installation documentation to state the verified Python 3.11 minimum.

## 2. Verify the Distribution Contract

- [x] 2.1 Run the unit/integration suite and every governed behavior root with CPython 3.11.
- [x] 2.2 Build the source and wheel distributions, verify their `Requires-Python` metadata, install the base wheel and CLI extra in isolated CPython 3.11 environments, and confirm an interpreter below 3.11 is rejected.
- [x] 2.3 Run the complete current-development-interpreter behavior audit, unit suite, lint, formatting, build, and strict OpenSpec validation.
