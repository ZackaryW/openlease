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

OpenLease requires Python 3.11 or newer, Git, and the OpenSpec CLI when workset
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

## Extension configuration

Dependent products explicitly register version-four extensions and delegate generic
configuration and confined storage plumbing to OpenLease. Registration is inert:
configuration never selects a runner, invokes an operation, or authorizes Git.
The extension still owns its schema, defaults, and product meaning.

Each binding records `yaml`, `toml`, `json`, or an explicitly registered custom
codec, plus `shared` or `dedicated` layout and read-only/writable authority. Shared
documents use exact extension identity keys; dots are literal, so TOML writes
`["zpp.behave"]`. Dedicated documents assign the complete root mapping to one
extension, allowing an existing root-level `zpp.behave.yaml` to stay unwrapped.

```python
from pathlib import Path

from openlease import (
    ConfigurationLayout,
    ExtensionDocumentBinding,
    ExtensionManifest,
    ExtensionOperation,
    ExtensionRegistration,
    OpenLease,
)


def verify(invocation):
    runner = invocation.config["runner"]
    invocation.data["last-runner"] = runner
    return {"selected": runner}


zpp_root = Path.home() / ".zpp"
system = OpenLease(
    zpp_root / "openlease",
    extensions=(
        ExtensionRegistration(
            ExtensionManifest("zpp.behave"),
            operations=(ExtensionOperation("verify", verify),),
        ),
    ),
)
system.set_extension_roots("zpp.behave", product_root=zpp_root)
behavior = system.bind_extension_document(
    ExtensionDocumentBinding(
        extension_id="zpp.behave",
        path=Path("zpp.behave.yaml"),
        codec="yaml",
        layout=ConfigurationLayout.DEDICATED,
        writable=True,
    ),
)
write = behavior.config.set("runner", "go-task")  # Saved atomically.
provenance = behavior.config.snapshot_record()
result = behavior.invoke("verify", {"targets": ["bdd"]})
```

Scalar direct-binding calls remain supported. Assignment and deletion also retain
their mapping syntax; use `set()` or `delete()` when the caller needs the completed
`WriteDisposition`. `snapshot()` returns effective immutable values, while
`snapshot_record()` additionally explains bindings, digests, winners, and observed
generations. `to_plain_managed_value()` converts a managed snapshot into independent
ordinary dictionaries and lists for downstream validation.

Configuration failures are public `InvalidRequest` subclasses with stable codes:
`configuration_read_only`, `configuration_validation_failed`,
`configuration_path_changed`, `configuration_decode_failed`, and
`configuration_conflict`. JSON CLI errors include the same code without changing
their `invalid_request` outcome or status 2.

This lets rebuilt ZPP retain `.zpp` as its product root without independently
resolving homes, repositories, saved profiles, or generated worktrees. A reusable
OpenLease configuration pack can replace a profile; direct space configuration
then specializes those pack defaults. Configuration scopes are not child spaces
and never acquire leases.

Managed reads are source-authoritative and nested values are immutable. Writes
target one exact writable binding, coordinate by canonical document path, reject
same-key races, rebase unrelated edits, and publish with atomic replacement.
Writing a lower-precedence source does not change a higher-precedence winner.
Direct configuration/data/cache assignments are immediate and remain published if
a handler later fails. `with extension.batch()` is the only way to request a
bounded grouped managed write; it never claims atomicity over Git, subprocesses,
network calls, or arbitrary filesystem effects.

The optional CLI exposes the same generic operations:

```console
openlease extension roots-set zpp.traits --product-root ~/.zpp
openlease config bind zpp.traits machine ~/.zpp/traits.yaml --scope machine --codec yaml --layout dedicated --read-only
openlease pack define zpp.traits backend
openlease --space current-work pack attach zpp.traits backend --order 1
openlease --space current-work --json extension context zpp.traits --authority package-a
```

Every configuration request reads the currently bound documents. An edit is visible on
the next request even while the space is locked; a missing source fails instead
of returning stale cached content, without changing lease or graph generations.
Repository-contained bindings follow the same relative path into a generated
worktree, while external bindings retain their exact canonical machine path.
Dependency edges are reported but never import provider configuration implicitly.

Configuration state uses schema version 3 and requires codec, layout, and write
authority on every binding. Earlier state and the former resolver/injected-verifier
contracts are rejected with reinitialization guidance. OpenLease performs no
compatibility read or automatic migration and never rewrites referenced authored
YAML, TOML, or JSON while rejecting old state.

Reconciliation callbacks are also explicit. A plan selects exact extension,
operation, event, mode, repository/cohort targets, and immutable managed input such
as `{"command": "bdd", "complete": true}`. The input is visible in callback drift
evidence and is passed unchanged; configuration never chooses it. Only
`reconcile.before_repository` may gate before Git mutation; post-repository and
post-cohort callbacks are observational, and their failures never invent an
"unverified" lifecycle state. Each selected post-cohort callback runs once per
completed repository in reconciliation order with isolated repository context and
both cohort and repository event identity. Source/destination refs, strategies, staging,
commits, merge/rebase, conflict resolution, and finalization remain core
owner-directed OpenLease/Git work, never extension policy.

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
