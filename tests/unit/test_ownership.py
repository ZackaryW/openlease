from pathlib import Path

from openlease.utils.openspec_adapter import OpenSpecWorkset
from openlease.utils.ownership import (
    ProjectionOwnership,
    inspect_projection,
    projection_fingerprint,
)


def test_classifies_only_an_intact_owned_projection_as_current(tmp_path: Path) -> None:
    members = (tmp_path / "a", tmp_path / "b")
    expected = ProjectionOwnership(
        "openlease-space",
        members,
        projection_fingerprint("openlease-space", members),
        generation=2,
    )

    current = inspect_projection(expected, OpenSpecWorkset("openlease-space", members))
    modified = inspect_projection(
        expected, OpenSpecWorkset("openlease-space", (members[0],))
    )

    assert current.state == "current"
    assert modified.state == "conflict"
