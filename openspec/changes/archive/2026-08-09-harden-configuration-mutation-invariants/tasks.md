## 1. Fail-First Regression Contract

- [x] 1.1 Add integration coverage proving that two handles which observed an absent key cannot silently overwrite one another.
- [x] 1.2 Add integration coverage proving that replacing a bound writable document with a symlink cannot modify the symlink target.
- [x] 1.3 Add capability-owned BDD scenarios for absent-key conflicts and post-binding symlink substitution.

## 2. Managed Configuration Hardening

- [x] 2.1 Retain each handle's complete selected writable mapping so absent keys remain observed baselines.
- [x] 2.2 Validate the originally authorized canonical document path before managed reads and publication.
- [x] 2.3 Publish only to the bound path and preserve substituted paths and external targets on rejection.

## 3. Governed Verification Mapping

- [x] 3.1 Declare `bounded-extension-runtime` in both affected and complete-audit mappings using the established argv provider.
- [x] 3.2 Map shared extension runtime and codec inputs to every affected extension capability target.
- [x] 3.3 Validate the committed mapping through `zpp behave init` and pass `zpp behave bdd-audit --all`.

## 4. Complete Verification

- [x] 4.1 Pass focused conflict and symlink regressions plus the complete Python test suite.
- [x] 4.2 Pass repository lint, formatting, lockfile, diff, and strict OpenSpec validation gates.
