from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from openlease import (
    BranchSelection,
    ConfigurationLayout,
    ConfigurationTarget,
    ExtensionManifest,
    ExtensionRegistration,
    InvalidRequest,
    OpenLease,
    OpenLeaseError,
    ReconcileSelection,
)
from openlease.core.graph import AccessRole
from openlease.result import CommandResult, json_value
from openlease.utils.git_adapter import IntegrationStrategy

app = typer.Typer(help="Relational OpenSpec authority leasing.", no_args_is_help=True)
register_app = typer.Typer(help="Register topology nodes.")
relate_app = typer.Typer(help="Declare topology relationships.")
space_app = typer.Typer(help="Manage durable spaces.")
affect_app = typer.Typer(help="Manage a space's direct affected claim.")
reconcile_app = typer.Typer(help="Plan and apply explicit integration paths.")
session_app = typer.Typer(help="Select a durable space in terminal context.")
preparation_app = typer.Typer(help="Inspect and recover failed successor preparation.")
extension_app = typer.Typer(help="Inspect extension contexts and storage roots.")
configuration_app = typer.Typer(help="Manage extension configuration sources.")
pack_app = typer.Typer(help="Manage reusable extension configuration packs.")
app.add_typer(register_app, name="register")
app.add_typer(relate_app, name="relate")
app.add_typer(space_app, name="space")
app.add_typer(affect_app, name="affect")
app.add_typer(reconcile_app, name="reconcile")
app.add_typer(session_app, name="session")
app.add_typer(preparation_app, name="preparation")
app.add_typer(extension_app, name="extension")
app.add_typer(configuration_app, name="config")
app.add_typer(pack_app, name="pack")


@dataclass(slots=True)
class Context:
    lifecycle: OpenLease
    space: str | None
    json_output: bool


def _env_path(name: str, fallback: str) -> Path:
    return Path(os.environ.get(name, fallback)).expanduser().resolve()


@app.callback()
def configure(
    ctx: typer.Context,
    state_root: Annotated[
        Path | None,
        typer.Option("--state-root", help="Machine-local OpenLease state root."),
    ] = None,
    worktree_base: Annotated[
        Path | None,
        typer.Option("--worktree-base", help="Base for generated worktree cohorts."),
    ] = None,
    space: Annotated[
        str | None,
        typer.Option("--space", envvar="OPENLEASE_SPACE", help="Selected space."),
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit one JSON result envelope.")
    ] = False,
) -> None:
    root = state_root or _env_path(
        "OPENLEASE_STATE_ROOT", str(Path.home() / ".openlease")
    )
    configured_base = os.environ.get("OPENLEASE_WORKTREE_BASE")
    base = worktree_base or (
        Path(configured_base).expanduser().resolve() if configured_base else None
    )
    ctx.obj = Context(OpenLease(root, worktree_base=base), space, json_output)


def _context(ctx: typer.Context) -> Context:
    return ctx.ensure_object(Context)


def _space(context: Context, explicit: str | None) -> str:
    selected = explicit or context.space
    if not selected:
        raise typer.BadParameter("select a space with --space or OPENLEASE_SPACE")
    return selected


def _run(context: Context, operation: Callable[[], CommandResult]) -> None:
    try:
        result = operation()
    except OpenLeaseError as error:
        _exit_for_error(error)
    if context.json_output:
        typer.echo(json.dumps(result.envelope(), sort_keys=True))
    else:
        typer.echo(f"{result.operation}: {result.outcome}")


def _exit_for_error(error: OpenLeaseError) -> None:
    envelope = {
        "ok": False,
        "operation": "error",
        "outcome": error.outcome,
        "message": str(error),
        "details": json_value(error.details),
    }
    code = getattr(error, "code", None)
    if code is not None:
        envelope["code"] = code
    typer.echo(json.dumps(envelope, sort_keys=True), err=True)
    raise typer.Exit(error.exit_status) from None


def _extension_lifecycle(context: Context, extension_id: str) -> OpenLease:
    lifecycle = context.lifecycle
    return OpenLease(
        lifecycle.state_root,
        worktree_base=lifecycle.worktree_base,
        git=lifecycle.git,
        openspec=lifecycle.openspec,
        extensions=(ExtensionRegistration(ExtensionManifest(extension_id)),),
    )


@extension_app.command("roots-set")
def extension_roots_set(
    ctx: typer.Context,
    extension: str,
    product_root: Annotated[Path | None, typer.Option("--product-root")] = None,
    configuration_root: Annotated[
        Path | None, typer.Option("--configuration-root")
    ] = None,
    data_root: Annotated[Path | None, typer.Option("--data-root")] = None,
    cache_root: Annotated[Path | None, typer.Option("--cache-root")] = None,
) -> None:
    context = _context(ctx)
    lifecycle = _extension_lifecycle(context, extension)
    _run(
        context,
        lambda: lifecycle.set_extension_roots(
            extension,
            product_root=product_root,
            configuration_root=configuration_root,
            data_root=data_root,
            cache_root=cache_root,
        ),
    )


@extension_app.command("roots-show")
def extension_roots_show(ctx: typer.Context, extension: str) -> None:
    context = _context(ctx)
    lifecycle = _extension_lifecycle(context, extension)
    _run(context, lambda: lifecycle.extension_roots(extension))


@extension_app.command("context")
def extension_context(
    ctx: typer.Context,
    extension: str,
    repository: Annotated[str | None, typer.Option("--repository")] = None,
    authority: Annotated[str | None, typer.Option("--authority")] = None,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    lifecycle = _extension_lifecycle(context, extension)

    def resolve() -> CommandResult:
        if (repository is None) == (authority is None):
            raise InvalidRequest("select exactly one repository or authority target")
        target = (
            ConfigurationTarget.repository(repository)
            if repository is not None
            else ConfigurationTarget.authority(authority or "")
        )
        bound = lifecycle.bind_extension(extension, _space(context, space), target)
        return CommandResult(
            "extension_context",
            changed=False,
            data={
                "context": bound.context,
                "configuration": bound.config.snapshot_record(),
            },
        )

    _run(context, resolve)


@configuration_app.command("bind")
def configuration_bind(
    ctx: typer.Context,
    extension: str,
    identifier: str,
    source: Path,
    scope: Annotated[str, typer.Option("--scope")],
    codec: Annotated[str, typer.Option("--codec")],
    layout: Annotated[ConfigurationLayout, typer.Option("--layout")],
    scope_id: Annotated[str | None, typer.Option("--scope-id")] = None,
    writable: Annotated[bool, typer.Option("--writable/--read-only")] = False,
    order: Annotated[int, typer.Option("--order")] = 0,
) -> None:
    context = _context(ctx)
    lifecycle = _extension_lifecycle(context, extension)
    _run(
        context,
        lambda: lifecycle.bind_configuration_source(
            extension,
            identifier,
            source,
            scope,
            scope_id,
            codec=codec,
            layout=layout.value,
            writable=writable,
            order=order,
        ),
    )


@configuration_app.command("remove")
def configuration_remove(ctx: typer.Context, extension: str, identifier: str) -> None:
    context = _context(ctx)
    lifecycle = _extension_lifecycle(context, extension)
    _run(
        context,
        lambda: lifecycle.remove_configuration_source(extension, identifier),
    )


@pack_app.command("define")
def pack_define(ctx: typer.Context, extension: str, identifier: str) -> None:
    context = _context(ctx)
    lifecycle = _extension_lifecycle(context, extension)
    _run(
        context,
        lambda: lifecycle.define_configuration_pack(extension, identifier),
    )


@pack_app.command("attach")
def pack_attach(
    ctx: typer.Context,
    extension: str,
    identifier: str,
    order: Annotated[int, typer.Option("--order")] = 0,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    lifecycle = _extension_lifecycle(context, extension)
    _run(
        context,
        lambda: lifecycle.attach_configuration_pack(
            _space(context, space), extension, identifier, order=order
        ),
    )


@pack_app.command("detach")
def pack_detach(
    ctx: typer.Context,
    extension: str,
    identifier: str,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    lifecycle = _extension_lifecycle(context, extension)
    _run(
        context,
        lambda: lifecycle.detach_configuration_pack(
            _space(context, space), extension, identifier
        ),
    )


@register_app.command("repository")
def register_repository(ctx: typer.Context, identifier: str, path: Path) -> None:
    context = _context(ctx)
    _run(context, lambda: context.lifecycle.register_repository(identifier, path))


@register_app.command("authority")
def register_authority(
    ctx: typer.Context,
    identifier: str,
    repository: str,
    path: Annotated[str, typer.Option("--path")] = "openspec",
    store_id: Annotated[str | None, typer.Option("--store-id")] = None,
) -> None:
    context = _context(ctx)
    _run(
        context,
        lambda: context.lifecycle.register_authority(
            identifier, repository, path, store_id=store_id
        ),
    )


@relate_app.command("parent")
def relate_parent(ctx: typer.Context, child: str, parent: str) -> None:
    context = _context(ctx)
    _run(context, lambda: context.lifecycle.relate_parent(child, parent))


@relate_app.command("dependency")
def relate_dependency(
    ctx: typer.Context,
    consumer: str,
    authority: str,
    access: Annotated[AccessRole, typer.Option("--access")] = AccessRole.WRITABLE,
) -> None:
    context = _context(ctx)
    _run(
        context,
        lambda: context.lifecycle.relate_dependency(consumer, authority, access),
    )


@space_app.command("create")
def create_space(ctx: typer.Context, identifier: str) -> None:
    context = _context(ctx)
    _run(context, lambda: context.lifecycle.create_space(identifier))


@session_app.command("start")
def session_start(ctx: typer.Context, identifier: str) -> None:
    context = _context(ctx)
    _run(context, lambda: context.lifecycle.create_space(identifier))


@session_app.command("attach")
def session_attach(ctx: typer.Context, identifier: str) -> None:
    context = _context(ctx)
    if context.json_output:
        _run(context, lambda: context.lifecycle.select_space(identifier))
        return
    try:
        context.lifecycle.select_space(identifier)
    except OpenLeaseError as error:
        _exit_for_error(error)
    typer.echo(f"OPENLEASE_SPACE={identifier}")


@session_app.command("close")
def session_close(
    ctx: typer.Context,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(context, lambda: context.lifecycle.close_session(_space(context, space)))


@space_app.command("associate")
def associate(
    ctx: typer.Context,
    repositories: Annotated[list[str], typer.Argument(help="Repository IDs.")],
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(
        context,
        lambda: context.lifecycle.associate(
            _space(context, space), tuple(repositories)
        ),
    )


@app.command("associate")
def associate_alias(
    ctx: typer.Context,
    repositories: Annotated[list[str], typer.Argument(help="Repository IDs.")],
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    associate(ctx, repositories, space)


@affect_app.command("add")
def affect_add(
    ctx: typer.Context,
    repositories: Annotated[list[str] | None, typer.Option("--repository")] = None,
    authorities: Annotated[list[str] | None, typer.Option("--authority")] = None,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(
        context,
        lambda: context.lifecycle.affect_add(
            _space(context, space),
            repository_ids=tuple(repositories or ()),
            authority_ids=tuple(authorities or ()),
        ),
    )


@affect_app.command("remove")
def affect_remove(
    ctx: typer.Context,
    repositories: Annotated[list[str] | None, typer.Option("--repository")] = None,
    authorities: Annotated[list[str] | None, typer.Option("--authority")] = None,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(
        context,
        lambda: context.lifecycle.affect_remove(
            _space(context, space),
            repository_ids=tuple(repositories or ()),
            authority_ids=tuple(authorities or ()),
        ),
    )


@affect_app.command("show")
def affect_show(
    ctx: typer.Context,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(context, lambda: context.lifecycle.plan(_space(context, space)))


@app.command("status")
def status(
    ctx: typer.Context,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(context, lambda: context.lifecycle.status(space or context.space))


@app.command("plan")
def plan(
    ctx: typer.Context,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(context, lambda: context.lifecycle.plan(_space(context, space)))


@app.command("lockable")
def lockable(
    ctx: typer.Context,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(context, lambda: context.lifecycle.lockable(_space(context, space)))


@app.command("lock")
def lock(
    ctx: typer.Context,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(context, lambda: context.lifecycle.lock(_space(context, space)))


@app.command("open")
def open_space(
    ctx: typer.Context,
    tool: Annotated[str | None, typer.Option("--tool")] = None,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(context, lambda: context.lifecycle.open(_space(context, space), tool=tool))


def _branch_selection(mode: str, ref: str | None) -> BranchSelection:
    if mode not in {"new", "local", "remote"}:
        raise typer.BadParameter("branch mode must be new, local, or remote")
    return BranchSelection(mode, ref)  # type: ignore[arg-type]


@app.command("defer")
def defer(
    ctx: typer.Context,
    successor: str,
    branch_mode: Annotated[str, typer.Option("--branch-mode")] = "new",
    branch_ref: Annotated[str | None, typer.Option("--branch-ref")] = None,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    selected = _space(context, space)
    affected = context.lifecycle.plan(selected).data.work_repositories
    branches = {
        repository: _branch_selection(branch_mode, branch_ref)
        for repository in affected
    }
    _run(
        context,
        lambda: context.lifecycle.defer(selected, successor, branches=branches),
    )


@app.command("isolate")
def isolate(
    ctx: typer.Context,
    successor: str,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(
        context,
        lambda: context.lifecycle.isolate(_space(context, space), successor),
    )


@app.command("release")
def release(
    ctx: typer.Context,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(context, lambda: context.lifecycle.release(_space(context, space)))


def _selections(
    repositories: list[str],
    destinations: list[str],
    strategies: list[IntegrationStrategy],
) -> tuple[ReconcileSelection, ...]:
    if not (len(repositories) == len(destinations) == len(strategies)):
        raise typer.BadParameter(
            "provide one repository, destination, and strategy per reconciliation leg"
        )
    return tuple(
        ReconcileSelection(repository, destination, strategy)
        for repository, destination, strategy in zip(
            repositories, destinations, strategies, strict=True
        )
    )


@reconcile_app.command("plan")
def reconcile_plan(
    ctx: typer.Context,
    repositories: Annotated[list[str], typer.Option("--repository")],
    destinations: Annotated[list[str], typer.Option("--destination")],
    strategies: Annotated[list[IntegrationStrategy], typer.Option("--strategy")],
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(
        context,
        lambda: context.lifecycle.reconcile_plan(
            _space(context, space),
            _selections(repositories, destinations, strategies),
        ),
    )


@reconcile_app.command("apply")
def reconcile_apply(
    ctx: typer.Context,
    repositories: Annotated[list[str], typer.Option("--repository")],
    destinations: Annotated[list[str], typer.Option("--destination")],
    strategies: Annotated[list[IntegrationStrategy], typer.Option("--strategy")],
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(
        context,
        lambda: context.lifecycle.reconcile_apply(
            _space(context, space),
            _selections(repositories, destinations, strategies),
        ),
    )


@app.command("recover")
def recover(
    ctx: typer.Context,
    force: Annotated[bool, typer.Option("--force")] = False,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(
        context,
        lambda: context.lifecycle.recover(_space(context, space), force=force),
    )


@app.command("finalize")
def finalize(
    ctx: typer.Context,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(context, lambda: context.lifecycle.finalize(_space(context, space)))


@app.command("handoff")
def handoff(
    ctx: typer.Context,
    disposition: Annotated[str, typer.Option("--disposition")],
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    if disposition not in {"integrated", "abandoned", "superseded"}:
        raise typer.BadParameter(
            "disposition must be integrated, abandoned, or superseded"
        )
    context = _context(ctx)
    _run(
        context,
        lambda: context.lifecycle.set_handoff_disposition(
            _space(context, space),
            disposition,  # type: ignore[arg-type]
        ),
    )


@app.command("abandon")
def abandon(
    ctx: typer.Context,
    repository: Annotated[str, typer.Option("--repository")],
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(
        context,
        lambda: context.lifecycle.abandon_member(_space(context, space), repository),
    )


@app.command("cleanup")
def cleanup(
    ctx: typer.Context,
    repository: Annotated[str, typer.Option("--repository")],
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(
        context,
        lambda: context.lifecycle.cleanup_worktree(_space(context, space), repository),
    )


@preparation_app.command("resume")
def preparation_resume(
    ctx: typer.Context,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(
        context,
        lambda: context.lifecycle.resume_preparation(_space(context, space)),
    )


@preparation_app.command("rollback")
def preparation_rollback(
    ctx: typer.Context,
    space: Annotated[str | None, typer.Option("--space")] = None,
) -> None:
    context = _context(ctx)
    _run(
        context,
        lambda: context.lifecycle.rollback_preparation(_space(context, space)),
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
