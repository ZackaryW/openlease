from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal

from openlease.utils.openspec_adapter import OpenSpecWorkset


@dataclass(frozen=True, slots=True)
class ProjectionOwnership:
    name: str
    members: tuple[Path, ...]
    fingerprint: str
    generation: int


@dataclass(frozen=True, slots=True)
class ProjectionInspection:
    state: Literal["absent", "unmanaged", "current", "conflict"]
    expected: ProjectionOwnership | None
    actual: OpenSpecWorkset | None


def projection_fingerprint(name: str, members: tuple[Path, ...]) -> str:
    document = {"name": name, "members": [str(path.resolve()) for path in members]}
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return sha256(payload).hexdigest()


def inspect_projection(
    expected: ProjectionOwnership | None,
    actual: OpenSpecWorkset | None,
) -> ProjectionInspection:
    if expected is None:
        return ProjectionInspection(
            "absent" if actual is None else "unmanaged", None, actual
        )
    if actual is None or actual.name != expected.name:
        return ProjectionInspection("conflict", expected, actual)
    actual_fingerprint = projection_fingerprint(actual.name, actual.members)
    state: Literal["current", "conflict"] = (
        "current" if actual_fingerprint == expected.fingerprint else "conflict"
    )
    return ProjectionInspection(state, expected, actual)
