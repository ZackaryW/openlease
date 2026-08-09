import json
from datetime import UTC, date, datetime, time

from openlease.result import CommandResult


def test_command_envelope_converts_managed_temporal_scalars_to_json() -> None:
    result = CommandResult(
        "reconcile_plan",
        changed=False,
        data={
            "date": date(2026, 8, 9),
            "time": time(12, 34, 56),
            "datetime": datetime(2026, 8, 9, 12, 34, 56, tzinfo=UTC),
        },
    )

    envelope = result.envelope()

    assert json.loads(json.dumps(envelope))["data"] == {
        "date": "2026-08-09",
        "time": "12:34:56",
        "datetime": "2026-08-09T12:34:56+00:00",
    }
