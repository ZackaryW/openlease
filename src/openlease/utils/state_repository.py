from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from filelock import FileLock

from openlease.core.state_codec import OpenLeaseState, decode_state, encode_state

StateTransform = Callable[[OpenLeaseState], OpenLeaseState]


class StaleStateError(RuntimeError):
    """A caller planned against an obsolete state generation."""


class StateRepository:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.index_path = self.root / "state.json"
        self.lock_path = self.root / "state.lock"
        self.backup_path = self.root / "state.v1.json"

    def load(self) -> OpenLeaseState:
        if not self.index_path.exists():
            return OpenLeaseState()
        return decode_state(self.index_path.read_bytes())

    def mutate(
        self, expected_generation: int, transform: StateTransform
    ) -> OpenLeaseState:
        self.root.mkdir(parents=True, exist_ok=True)
        with FileLock(self.lock_path, timeout=10):
            original = (
                self.index_path.read_bytes() if self.index_path.exists() else None
            )
            current = (
                decode_state(original) if original is not None else OpenLeaseState()
            )
            if current.generation != expected_generation:
                raise StaleStateError(
                    f"state generation changed from {expected_generation} "
                    f"to {current.generation}"
                )
            candidate = replace(transform(current), generation=current.generation + 1)
            if (
                original is not None
                and _schema_version(original) == 1
                and not self.backup_path.exists()
            ):
                atomic_write(self.backup_path, original)
            atomic_write(self.index_path, encode_state(candidate))
            return candidate


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _schema_version(source: bytes) -> object:
    try:
        document = json.loads(source.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None
    return document.get("schema_version") if isinstance(document, dict) else None
