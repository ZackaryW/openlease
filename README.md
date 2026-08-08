# OpenLease

OpenLease coordinates local OpenSpec work across monorepos, linked worktrees, and
repositories that consume externally hosted OpenSpec authorities. It keeps the
complete working view separate from the smaller affected claim, then leases only
that claim's writable authority closure.

Two spaces may lease sibling OpenSpec authorities in one monorepo at the same
time. A parent and child cannot overlap. A different Git worktree never bypasses
an authority conflict.

## Install

The library has no CLI-framework dependency:

```console
uv add openlease
```

Install the optional terminal surface with:

```console
uv add "openlease[cli]"
```

OpenLease requires Python 3.14 or newer, Git, and the OpenSpec CLI when workset
projections are opened or prepared.

## Model

- A repository is one stable Git common-directory identity. Linked worktrees map
  back to the same repository; unlinked clones remain distinct unless explicitly
  modeled otherwise.
- An authority is a repository-relative OpenSpec root or store.
- A parent relation describes nested authority exclusion.
- A dependency relation describes read-only or writable use of another authority.
- A space contains associated context plus an explicit affected claim.
- A lease atomically owns only the affected writable authority closure.
- A deferred successor contains affected Git worktrees but no lease until its
  blockers have an explicit handoff disposition and its baselines are fresh.

## CLI walkthrough

Global `--state-root`, `--worktree-base`, `--space`, and `--json` options make the
same lifecycle suitable for terminals and isolated automation.

```console
openlease register repository repo1 C:\work\repo1
openlease register repository repo2 C:\work\repo2
openlease register repository repo3 C:\work\repo3

openlease register authority root repo1 --path openspec
openlease register authority a repo1 --path packages/A/openspec
openlease register authority b repo1 --path packages/B/openspec
openlease register authority shared repo3 --path openspec

openlease relate parent a root
openlease relate parent b root
openlease relate dependency repo2 shared --access writable

openlease session start my-change
openlease --space my-change associate repo1 repo2 repo3
openlease --space my-change affect add --authority a
openlease --space my-change --json plan
openlease --space my-change --json lockable
openlease --space my-change lock
```

If `lockable` is false, prepare only affected repositories in a distinct cohort:

```console
openlease --space my-change defer my-change-deferred
```

Machine-local coordination state defaults to `~/.openlease`. Generated worktrees
do not: without an override, each affected repository is materialized beside its
registered checkout as `<repository-directory>-olease-<n>`, using the lowest
available positive suffix. A multi-repository cohort may therefore span several
parent directories while its exact paths remain wired together in state.

Use `--worktree-base PATH` or `OPENLEASE_WORKTREE_BASE` for isolated automation;
the same names are allocated directly beneath that base. Existing files,
directories, symbolic links, durable reservations, and Git-registered worktree
paths consume a suffix. The name is only a visual hint: exact recorded state is
the ownership evidence, so OpenLease never adopts or cleans up a matching path
merely because it contains `-olease-<n>`.

`defer` does not grant conflicting write authority. After every blocker is
released and marked `integrated`, `abandoned`, or `superseded`, explicitly lock
the clean successor. Generated branches remain reconciliation debt after release.
Supply a destination and merge/rebase strategy for every generated repository,
plan first, then apply. Reconciliation advances one repository at a time and
stops at the first Git conflict.

Use `openlease COMMAND --help` for the complete command arguments. Every command
delegates to the public `OpenLease` Python lifecycle and `--json` emits one stable
result envelope.

## Safety boundary

OpenLease serializes cooperative machine-local OpenSpec authority work. It audits
committed and working-copy OpenSpec paths before release and reconciliation,
preserves ambiguous projections and dirty worktrees, and never treats terminal
loss as lease expiry. It does not prevent arbitrary editors or shell commands
from changing files, and it does not coordinate separate machines; Git remains
the integration authority for those cases.

## Development

```console
uv sync --all-extras --dev
uv run pytest -q
zpp behave bdd-audit --all
uv run ruff check src tests features scripts
uv build
```
