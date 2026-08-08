from __future__ import annotations

from tempfile import TemporaryDirectory

from support import MemoryOpenSpec, new_system


def before_scenario(context, scenario) -> None:
    del scenario
    context.temporary = TemporaryDirectory(prefix="openlease-behave-")
    from pathlib import Path

    context.root = Path(context.temporary.name)
    context.openspec = MemoryOpenSpec()
    context.system = new_system(context)
    context.selected = None
    context.result = None
    context.error = None


def after_scenario(context, scenario) -> None:
    del scenario
    context.temporary.cleanup()
