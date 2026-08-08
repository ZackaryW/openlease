from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ProcessAdapterError(RuntimeError):
    """A required external command failed."""


@dataclass(frozen=True, slots=True)
class ProcessResult:
    arguments: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class ProcessRunner(Protocol):
    def run(
        self,
        arguments: tuple[str, ...],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> ProcessResult: ...


class SubprocessRunner:
    def run(
        self,
        arguments: tuple[str, ...],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> ProcessResult:
        completed = subprocess.run(
            arguments,
            cwd=cwd,
            env=dict(os.environ, **env) if env is not None else None,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return ProcessResult(
            arguments,
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )


def require_success(result: ProcessResult, operation: str) -> ProcessResult:
    if result.returncode == 0:
        return result
    detail = (result.stderr.strip() or result.stdout.strip())[:4000]
    raise ProcessAdapterError(f"{operation} failed: {detail}")
