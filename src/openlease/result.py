from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def json_value(value: object) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: json_value(getattr(value, item.name)) for item in fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return {"encoding": "base64", "value": b64encode(value).decode("ascii")}
    if isinstance(value, dict) or hasattr(value, "items"):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set)):
        return [json_value(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class CommandResult:
    operation: str
    outcome: str = "success"
    changed: bool = True
    data: object | None = None

    def envelope(self) -> dict[str, object]:
        return {
            "ok": True,
            "operation": self.operation,
            "outcome": self.outcome,
            "changed": self.changed,
            "data": json_value(self.data),
        }
