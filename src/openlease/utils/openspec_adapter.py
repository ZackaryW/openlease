from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from openlease.utils.processes import ProcessRunner, SubprocessRunner, require_success


@dataclass(frozen=True, slots=True)
class OpenSpecWorkset:
    name: str
    members: tuple[Path, ...]


class OpenSpecAdapter:
    def __init__(self, runner: ProcessRunner | None = None) -> None:
        self.runner = runner or SubprocessRunner()

    def list_worksets(self) -> tuple[OpenSpecWorkset, ...]:
        result = require_success(
            self.runner.run(("openspec", "workset", "list", "--json")),
            "OpenSpec workset listing",
        )
        try:
            document = json.loads(result.stdout)
            values = document["worksets"]
            if not isinstance(values, list):
                raise TypeError
            worksets = []
            for value in values:
                if not isinstance(value, dict) or not isinstance(
                    value.get("name"), str
                ):
                    raise TypeError
                raw_members = value.get("members", [])
                if not isinstance(raw_members, list):
                    raise TypeError
                members: list[Path] = []
                for item in raw_members:
                    member = item.get("path") if isinstance(item, dict) else item
                    if not isinstance(member, str) or not member:
                        raise TypeError
                    members.append(Path(member).resolve())
                worksets.append(OpenSpecWorkset(value["name"], tuple(members)))
            return tuple(worksets)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ValueError("OpenSpec workset output is invalid") from error

    def create_workset(self, name: str, members: tuple[Path, ...]) -> None:
        arguments = ["openspec", "workset", "create", name]
        for member in members:
            arguments.extend(("--member", str(member)))
        arguments.append("--json")
        require_success(
            self.runner.run(tuple(arguments)),
            "OpenSpec workset creation",
        )

    def open_workset(self, name: str, tool: str | None = None) -> None:
        arguments = ["openspec", "workset", "open", name]
        if tool is not None:
            arguments.extend(("--tool", tool))
        require_success(
            self.runner.run(tuple(arguments)),
            "OpenSpec workset opening",
        )

    def remove_workset(self, name: str) -> None:
        require_success(
            self.runner.run(("openspec", "workset", "remove", name, "--yes", "--json")),
            "OpenSpec workset removal",
        )
