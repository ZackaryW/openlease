from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openlease.core.configuration import (
    ConfigurationTarget,
    ExtensionRoots,
)
from openlease.utils.configuration_source import ConfigurationDocument

EXTENSION_CONTRACT_VERSION = 1


@dataclass(frozen=True, slots=True)
class ExtensionManifest:
    identifier: str
    contract_version: int = EXTENSION_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class ExtensionMember:
    repository_id: str
    source_path: Path
    effective_path: Path
    starting_commit: str
    branch: str | None
    generated: bool
    access_role: str


@dataclass(frozen=True, slots=True)
class ExtensionAuthority:
    identifier: str
    repository_id: str
    relative_path: str
    effective_path: Path
    access_role: str


@dataclass(frozen=True, slots=True)
class ExtensionRelationship:
    kind: str
    source_id: str
    target_id: str
    access_role: str | None = None


@dataclass(frozen=True, slots=True)
class ExtensionPack:
    identifier: str
    order: int
    observed_generation: str


@dataclass(frozen=True, slots=True)
class ExtensionContext:
    extension_id: str
    space_id: str
    target: ConfigurationTarget
    state_generation: int
    configuration_generation: int
    packs: tuple[ExtensionPack, ...]
    members: tuple[ExtensionMember, ...]
    authorities: tuple[ExtensionAuthority, ...]
    relationships: tuple[ExtensionRelationship, ...]
    documents: tuple[ConfigurationDocument, ...]
    roots: ExtensionRoots


ExtensionResolver = Callable[[ExtensionContext], Any]


@dataclass(frozen=True, slots=True)
class ExtensionRegistration:
    manifest: ExtensionManifest
    resolver: ExtensionResolver | None = None


@dataclass(frozen=True, slots=True)
class ExtensionResolution:
    context: ExtensionContext
    value: object | None = None
