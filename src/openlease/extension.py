from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from openlease.configuration_codec import (
    ConfigurationCodec,
    ConfigurationLayout,
    ManagedValue,
    immutable_managed_value,
)
from openlease.core.configuration import ConfigurationTarget, ExtensionRoots

EXTENSION_CONTRACT_VERSION = 4


class CallbackEvent(StrEnum):
    RECONCILE_BEFORE_REPOSITORY = "reconcile.before_repository"
    RECONCILE_AFTER_REPOSITORY = "reconcile.after_repository"
    RECONCILE_AFTER_COHORT = "reconcile.after_cohort"


class CallbackMode(StrEnum):
    OBSERVE = "observe"
    GATE = "gate"


class WriteDispositionKind(StrEnum):
    COMMITTED = "committed"
    UNCOMMITTED = "uncommitted"
    RECOVERY_REQUIRED = "recovery_required"
    CONFLICT = "conflict"


class HandlerStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_STARTED = "not_started"


class FailurePhase(StrEnum):
    REGISTRATION = "registration"
    TARGET = "target"
    BINDING = "binding"
    READ = "read"
    DECODE = "decode"
    LAYOUT = "layout"
    OVERLAY = "overlay"
    VALIDATION = "validation"
    HANDLER = "handler"
    MANAGED_WRITE = "managed_write"
    BATCH_COMMIT = "batch_commit"
    OUTCOME_RECORDING = "outcome_recording"


@dataclass(frozen=True, slots=True)
class ExtensionManifest:
    identifier: str
    contract_version: int = EXTENSION_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class ExtensionOperation:
    name: str
    handler: Callable[[ExtensionInvocation], Any]
    target_kinds: tuple[str, ...] = ("space", "direct", "repository", "authority")


@dataclass(frozen=True, slots=True)
class ExtensionCallback:
    event: CallbackEvent
    operation: str
    modes: tuple[CallbackMode, ...] = (CallbackMode.OBSERVE,)


ExtensionValidator = Callable[[Mapping[str, ManagedValue]], None]


@dataclass(frozen=True, slots=True)
class ExtensionRegistration:
    manifest: ExtensionManifest
    operations: tuple[ExtensionOperation, ...] = ()
    callbacks: tuple[ExtensionCallback, ...] = ()
    validator: ExtensionValidator | None = None
    codecs: tuple[ConfigurationCodec, ...] = ()


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
class BindingProvenance:
    identifier: str
    extension_id: str
    scope_kind: str
    scope_id: str | None
    canonical_path: Path
    codec: str
    layout: ConfigurationLayout
    writable: bool
    order: int
    binding_revision: int
    content_digest: str
    observed_generation: str
    selected: Mapping[str, ManagedValue] = field(repr=False)


@dataclass(frozen=True, slots=True)
class EffectiveConfigurationSnapshot:
    values: Mapping[str, ManagedValue]
    bindings: tuple[BindingProvenance, ...]
    winners: Mapping[str, str]
    state_generation: int | None
    configuration_generation: int | None


@dataclass(frozen=True, slots=True)
class DirectDocumentTarget:
    path: Path
    repository_path: Path | None = None


@dataclass(frozen=True, slots=True)
class ExtensionDocumentBinding:
    extension_id: str
    path: Path
    codec: str
    layout: ConfigurationLayout
    writable: bool = False
    repository_path: Path | None = None


@dataclass(frozen=True, slots=True)
class ExtensionContext:
    extension_id: str
    target_kind: str
    target: ConfigurationTarget | DirectDocumentTarget
    state_generation: int | None
    configuration_generation: int | None
    roots: ExtensionRoots
    space_id: str | None = None
    packs: tuple[ExtensionPack, ...] = ()
    members: tuple[ExtensionMember, ...] = ()
    authorities: tuple[ExtensionAuthority, ...] = ()
    relationships: tuple[ExtensionRelationship, ...] = ()


@dataclass(frozen=True, slots=True)
class WriteDisposition:
    kind: WriteDispositionKind
    store: str
    key: str
    path: Path
    binding_id: str | None = None
    prior_digest: str | None = None
    resulting_digest: str | None = None
    diagnostic: str | None = None


class ManagedMapping(Protocol):
    def __getitem__(self, key: str) -> ManagedValue: ...

    def __setitem__(self, key: str, value: ManagedValue) -> None: ...

    def __delitem__(self, key: str) -> None: ...

    def __iter__(self) -> Iterator[str]: ...

    def __len__(self) -> int: ...

    def snapshot(self) -> Mapping[str, ManagedValue]: ...


class ManagedConfiguration(ManagedMapping, Protocol):
    def snapshot_record(self) -> EffectiveConfigurationSnapshot: ...

    def set(self, key: str, value: ManagedValue) -> WriteDisposition: ...

    def delete(self, key: str) -> WriteDisposition: ...


@dataclass(frozen=True, slots=True)
class ExtensionInvocation:
    input: object
    context: ExtensionContext
    config: ManagedConfiguration
    data: ManagedMapping
    cache: ManagedMapping
    event: ExtensionEvent | None = None
    _batch_factory: Callable[[], Any] | None = field(default=None, repr=False)

    def batch(self):
        if self._batch_factory is None:
            raise RuntimeError("batching is unavailable for this invocation")
        return self._batch_factory()


@dataclass(frozen=True, slots=True)
class ExtensionEvent:
    event: CallbackEvent
    mode: CallbackMode
    repository_id: str | None = None
    cohort_id: str | None = None


@dataclass(frozen=True, slots=True)
class CallbackSelection:
    extension_id: str
    operation: str
    event: CallbackEvent
    mode: CallbackMode
    repository_id: str | None = None
    input: ManagedValue | None = None

    def __post_init__(self) -> None:
        if self.input is not None:
            object.__setattr__(self, "input", immutable_managed_value(self.input))


@dataclass(frozen=True, slots=True)
class ExtensionOutcome:
    version: int
    extension_id: str
    operation: str
    target: str
    handler_status: HandlerStatus
    failure_phase: FailurePhase | None
    callback_event: CallbackEvent | None
    callback_mode: CallbackMode | None
    state_generation: int | None
    configuration_generation: int | None
    binding_digests: Mapping[str, str]
    writes: tuple[WriteDisposition, ...]
    diagnostic: str | None = None


@dataclass(frozen=True, slots=True)
class ExtensionInvocationResult:
    extension_id: str
    operation: str
    target: str
    handler_status: HandlerStatus
    value: object | None
    snapshot: EffectiveConfigurationSnapshot | None
    writes: tuple[WriteDisposition, ...]
    outcome: ExtensionOutcome
    outcome_recording_error: str | None = None


@dataclass(slots=True)
class BoundExtension:
    extension_id: str
    context: ExtensionContext
    config: ManagedConfiguration
    data: ManagedMapping
    cache: ManagedMapping
    _invoke: Callable[[str, object], ExtensionInvocationResult]
    _batch_factory: Callable[[], Any]

    def invoke(self, operation: str, input: object = None) -> ExtensionInvocationResult:
        return self._invoke(operation, input)

    def batch(self):
        return self._batch_factory()
