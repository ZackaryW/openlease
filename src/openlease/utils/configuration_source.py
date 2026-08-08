from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from openlease.core.configuration import (
    ConfigurationError,
    PlannedSource,
    SourceKind,
)


@dataclass(frozen=True, slots=True)
class ConfigurationDocument:
    identifier: str
    extension_id: str
    scope_kind: str
    scope_id: str | None
    resolved_path: str
    order: int
    binding_revision: int
    source_kind: SourceKind
    repository_id: str | None
    content: bytes
    content_digest: str
    observed_generation: str


def observed_generation(binding_revision: int, content_digest: str) -> str:
    return sha256(f"{binding_revision}:{content_digest}".encode()).hexdigest()


class ConfigurationSourceReader:
    def __init__(self, *, attempts: int = 3) -> None:
        if attempts < 1:
            raise ValueError("configuration read attempts must be positive")
        self.attempts = attempts

    def read(self, source: PlannedSource) -> ConfigurationDocument:
        path = source.resolved_path.resolve()
        for _attempt in range(self.attempts):
            try:
                before = path.stat()
                content = path.read_bytes()
                after = path.stat()
            except OSError as error:
                raise ConfigurationError(
                    f"configuration source is unavailable: {path}"
                ) from error
            if not path.is_file():
                raise ConfigurationError(f"configuration source is not a file: {path}")
            if _identity(before) != _identity(after):
                continue
            digest = sha256(content).hexdigest()
            return ConfigurationDocument(
                identifier=source.identifier,
                extension_id=source.extension_id,
                scope_kind=source.scope_kind,
                scope_id=source.scope_id,
                resolved_path=str(path),
                order=source.order,
                binding_revision=source.binding_revision,
                source_kind=source.source_kind,
                repository_id=source.repository_id,
                content=content,
                content_digest=digest,
                observed_generation=observed_generation(
                    source.binding_revision, digest
                ),
            )
        raise ConfigurationError(f"configuration source changed during read: {path}")


def _identity(stat_result: object) -> tuple[object, ...]:
    return tuple(
        getattr(stat_result, name)
        for name in ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    )
