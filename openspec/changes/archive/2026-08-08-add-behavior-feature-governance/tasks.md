## 1. Establish Capability Ownership

- [x] 1.1 Inventory every executable feature and assign it to one named capability root.
- [x] 1.2 Place each feature document, environment hook surface, and step module beneath its owning independently executable root.
- [x] 1.3 Extract reusable fixtures and helpers into shared support without Behave step registration.
- [x] 1.4 Remove the repository-wide step registry and replace every cross-root step dependency with a root-owned binding.

## 2. Configure Affected Verification

- [x] 2.1 Provide a repository runner that executes each selected capability root in a separate Behave invocation.
- [x] 2.2 Declare stable capability targets for affected execution and a separate complete-audit command in `zpp.behave.yaml`.
- [x] 2.3 Map capability-local inputs narrowly, shared inputs to every consumer, and leave uncertain impact conservative.
- [x] 2.4 Update development guidance to use the governed complete-audit command.

## 3. Enforce the Governance Contract

- [x] 3.1 Add structural verification that every declared root exists and shared support registers no executable steps.
- [x] 3.2 Validate every capability root independently so undefined, ambiguous, or cross-root-only steps fail.
- [x] 3.3 Verify that capability-local changes select only their declared target and shared or unknown changes select the complete required set.
- [x] 3.4 Run the complete behavior audit, unit suite, lint, formatting, build, and strict OpenSpec validation.
