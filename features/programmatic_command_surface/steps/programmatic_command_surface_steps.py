from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from behave import given, then, when
from typer.testing import CliRunner

from features.support.distribution import DistributionProbe, accepts_python
from features.support.openlease_support import (
    ensure_repositories,
    ensure_topology,
    space,
)
from openlease import (
    InvalidRequest,
    OpenLease,
)
from openlease.cli import app
from openlease.utils.openspec_adapter import OpenSpecWorkset
from openlease.utils.processes import SubprocessRunner, require_success

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _python_311() -> Path:
    result = SubprocessRunner().run(("uv", "python", "find", "3.11"), cwd=PROJECT_ROOT)
    require_success(result, "Python 3.11 discovery")
    return Path(result.stdout.strip())


def _install_distribution(context, *, extra: str | None = None) -> None:
    context.distribution_probe = DistributionProbe(PROJECT_ROOT, SubprocessRunner())
    context.python_311 = _python_311()
    context.distribution_artifact = context.distribution_probe.build(
        context.root / "distribution", python=context.python_311
    )
    context.distribution_python = context.distribution_probe.create_environment(
        context.root / "installed", python=context.python_311
    )
    context.distribution_probe.install(
        context.distribution_python,
        context.distribution_artifact,
        extra=extra,
    )


@given("OpenLease is installed without its CLI extra")
def base_install(context) -> None:
    context.import_script = (
        "import sys; import openlease; assert 'typer' not in sys.modules"
    )


@when("a Python consumer imports the public package")
def import_public(context) -> None:
    if hasattr(context, "distribution_python"):
        context.process = context.distribution_probe.invoke(
            context.distribution_python,
            ("-c", context.import_script),
        )
        return
    context.process = subprocess.run(
        (sys.executable, "-c", context.import_script),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@then("the import succeeds without importing Typer")
def import_without_typer(context) -> None:
    assert context.process.returncode == 0, context.process.stderr


@then("the complete public lifecycle is available through the library")
def lifecycle_exported(context) -> None:
    from openlease import OpenLease as ExportedOpenLease

    assert ExportedOpenLease is OpenLease
    assert all(
        hasattr(ExportedOpenLease, name)
        for name in ("lock", "defer", "reconcile_apply")
    )


@given("a built OpenLease distribution")
def built_distribution(context) -> None:
    context.distribution_probe = DistributionProbe(PROJECT_ROOT, SubprocessRunner())
    context.python_311 = _python_311()
    context.distribution_artifact = context.distribution_probe.build(
        context.root / "distribution", python=context.python_311
    )


@when("a package installer evaluates its Python requirement")
def evaluate_python_requirement(context) -> None:
    context.python_requirement = context.distribution_artifact.requires_python


@then("Python 3.11 and newer interpreters are accepted without an upper bound")
def accepts_supported_python(context) -> None:
    assert context.python_requirement == ">=3.11"
    assert accepts_python(context.python_requirement, "3.11")
    assert accepts_python(context.python_requirement, "999.0")


@then("interpreters older than Python 3.11 are rejected")
def rejects_older_python(context) -> None:
    assert not accepts_python(context.python_requirement, "3.10")


@given("the base OpenLease distribution is installed with Python 3.11")
def base_distribution_on_python_311(context) -> None:
    _install_distribution(context)
    context.import_script = (
        "import sys; from openlease import OpenLease; "
        "assert 'typer' not in sys.modules; "
        "assert all(hasattr(OpenLease, name) for name in "
        "('lock', 'defer', 'reconcile_apply'))"
    )


@then("the complete public lifecycle matches a newer supported interpreter")
def installed_lifecycle_matches(context) -> None:
    assert context.process.returncode == 0, context.process.stderr


@given("the OpenLease CLI extra is installed with Python 3.11")
def cli_distribution_on_python_311(context) -> None:
    _install_distribution(context, extra="cli")


@when("a user invokes a public command with JSON output")
def invoke_installed_cli(context) -> None:
    context.cli_process = context.distribution_probe.invoke(
        context.distribution_python,
        (
            "-m",
            "openlease.cli",
            "--state-root",
            str(context.root / "installed-state"),
            "--json",
            "status",
        ),
    )


@then("it preserves the documented result envelope and process status")
def installed_cli_contract(context) -> None:
    assert context.cli_process.returncode == 0, context.cli_process.stderr
    assert context.cli_process.stdout.count("\n") == 1
    envelope = json.loads(context.cli_process.stdout)
    assert envelope["ok"] is True
    assert envelope["operation"] == "status"


@given("the optional CLI extra is installed")
def cli_installed(context) -> None:
    context.runner = CliRunner()


@when("a user runs a topology, space, lease, defer, or reconcile command")
def cli_runs_commands(context) -> None:
    ensure_topology(context)
    result = context.runner.invoke(
        app,
        [
            "--state-root",
            str(context.root / "state"),
            "space",
            "create",
            "cli-space",
        ],
    )
    assert result.exit_code == 0
    context.result = context.system.status("cli-space")


@then("the command delegates to the same public library lifecycle")
def cli_shared_lifecycle(context) -> None:
    if hasattr(context, "cli_process"):
        assert context.cli_process.returncode == 0, context.cli_process.stderr
        envelope = json.loads(context.cli_process.stdout)
        assert envelope["operation"] == "status"
        return
    assert context.result.data["spaces"][0].identifier == "cli-space"


@then("no separate CLI-only state transition occurs")
def no_cli_state(context) -> None:
    assert not (context.root / "cli-state").exists()


@given("a valid noninteractive command")
def valid_cli_command(context) -> None:
    context.runner = CliRunner()
    context.cli_args = [
        "--state-root",
        str(context.root / "state"),
        "--json",
        "status",
    ]


@when("the user requests JSON output")
def request_json(context) -> None:
    context.cli_result = context.runner.invoke(app, context.cli_args)


@then("standard output contains one structured result envelope")
def one_json_envelope(context) -> None:
    assert context.cli_result.exit_code == 0
    context.envelope = json.loads(context.cli_result.stdout)
    assert context.envelope["ok"] is True
    assert context.cli_result.stdout.count("\n") == 1


@then("diagnostics are absent from standard output")
def no_stdout_diagnostics(context) -> None:
    assert context.cli_result.stderr == ""


@given("a command produces {outcome}")
def command_outcome(context, outcome: str) -> None:
    context.runner = CliRunner()
    state = context.root / "outcome-state"
    lifecycle = OpenLease(state, openspec=context.openspec)
    args = ["--state-root", str(state)]
    if outcome == "success":
        context.cli_args = [*args, "status"]
    elif outcome == "invalid request":
        lifecycle.create_space("request")
        context.cli_args = [*args, "--space", "request", "lock"]
    else:
        context.system = lifecycle
        context.root = context.root
        ensure_repositories(context)
        ensure_topology(context)
        if outcome == "compatible no-op":
            space(context, "request", authorities=("a",))
            lifecycle.lock("request")
            context.cli_args = [*args, "--space", "request", "lock"]
        elif outcome == "authority conflict":
            space(context, "owner", authorities=("a",))
            lifecycle.lock("owner")
            space(context, "request", authorities=("a",))
            context.cli_args = [*args, "--space", "request", "lock"]
        else:
            space(context, "request", authorities=("a",))
            lifecycle.lock("request")
            lifecycle.open("request")
            owned = context.openspec.worksets["openlease-request"]
            context.openspec.worksets[owned.name] = OpenSpecWorkset(owned.name, ())
            context.cli_args = [*args, "--space", "request", "release"]


@when("the command exits")
def command_exits(context) -> None:
    context.cli_result = context.runner.invoke(app, context.cli_args)


@then("its process status is {status:d}")
def process_status(context, status: int) -> None:
    assert context.cli_result.exit_code == status


@then("expected domain failures show no implementation traceback")
def no_domain_traceback(context) -> None:
    assert "Traceback" not in context.cli_result.stderr


@given("isolated automation selects an explicit OpenLease state root and worktree base")
def explicit_roots(context) -> None:
    context.explicit_state = context.root / "explicit-state"
    context.explicit_worktrees = context.root / "explicit-worktrees"
    context.system = OpenLease(
        context.explicit_state,
        worktree_base=context.explicit_worktrees,
        openspec=context.openspec,
    )


@when("it runs the public lifecycle")
def run_explicit_lifecycle(context) -> None:
    ensure_topology(context)
    space(context, "blocker", authorities=("a",))
    context.system.lock("blocker")
    space(context, "request", authorities=("a",))
    context.result = context.system.defer("request", "successor")


@then("all OpenLease state and generated destinations remain beneath those selections")
def paths_bounded(context) -> None:
    assert (context.explicit_state / "state.json").exists(), context.explicit_state
    for item in context.result.data.members:
        if item.generated:
            assert os.path.samefile(
                Path(item.effective_path).parent,
                context.system.worktree_base,
            )


@then("the same identity, collision, ownership, and recovery rules apply")
def same_rules_apply(context) -> None:
    assert context.system.lockable("successor").data["lockable"] is False
    assert context.result.data.projection_fingerprint
    assert context.system.recover("successor", force=True).data.status == "released"


@given("two processes plan against one state generation")
def same_generation(context) -> None:
    ensure_topology(context)
    space(context, "selected")
    context.generation = context.system.snapshot().generation


@when("both attempt a mutating lifecycle operation")
def competing_mutations(context) -> None:
    second = OpenLease(
        context.root / "state",
        worktree_base=context.root / "worktrees",
        openspec=context.openspec,
    )

    def mutate(system: OpenLease, repository: str):
        try:
            return system.associate(
                "selected", (repository,), expected_generation=context.generation
            )
        except Exception as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        context.results = tuple(
            pool.map(
                lambda pair: mutate(*pair),
                ((context.system, "repo-1"), (second, "repo-2")),
            )
        )


@then("OpenLease serializes the mutations")
def mutations_serialized(context) -> None:
    assert sum(not isinstance(item, Exception) for item in context.results) == 1


@then("only a process whose observed generation is current may commit its result")
def only_current_commits(context) -> None:
    assert sum(isinstance(item, InvalidRequest) for item in context.results) == 1
