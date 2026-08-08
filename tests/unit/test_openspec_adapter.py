from pathlib import Path

import pytest

from openlease.utils.openspec_adapter import OpenSpecAdapter
from openlease.utils.processes import ProcessResult


class FakeRunner:
    def __init__(self, output: str = '{"worksets":[],"status":[]}') -> None:
        self.calls: list[tuple[str, ...]] = []
        self.output = output

    def run(self, arguments, *, cwd=None, env=None):
        del cwd, env
        self.calls.append(arguments)
        return ProcessResult(arguments, 0, self.output, "")


def test_constructs_bounded_workset_commands(tmp_path: Path) -> None:
    runner = FakeRunner()
    adapter = OpenSpecAdapter(runner)
    first = tmp_path / "first"
    second = tmp_path / "second"

    adapter.create_workset("openlease-space", (first, second))
    adapter.open_workset("openlease-space", tool="codex")
    adapter.remove_workset("openlease-space")

    assert runner.calls == [
        (
            "openspec",
            "workset",
            "create",
            "openlease-space",
            "--member",
            str(first),
            "--member",
            str(second),
            "--json",
        ),
        ("openspec", "workset", "open", "openlease-space", "--tool", "codex"),
        ("openspec", "workset", "remove", "openlease-space", "--yes", "--json"),
    ]


def test_parses_worksets_and_rejects_unknown_member_shapes(tmp_path: Path) -> None:
    valid = FakeRunner(
        '{"worksets":[{"name":"space","members":[{"path":"'
        + str(tmp_path).replace("\\", "\\\\")
        + '"}]}]}'
    )
    invalid = FakeRunner('{"worksets":[{"name":"space","members":[42]}]}')

    assert OpenSpecAdapter(valid).list_worksets()[0].members == (tmp_path.resolve(),)
    with pytest.raises(ValueError, match="invalid"):
        OpenSpecAdapter(invalid).list_worksets()
