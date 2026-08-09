from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Iterator, Mapping, MutableMapping
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from uuid import uuid4

from filelock import FileLock

from openlease.configuration_codec import (
    CodecError,
    CodecRegistry,
    ConfigurationLayout,
    ManagedValue,
    immutable_managed_value,
    plain_managed_value,
    project_namespace,
    replace_namespace,
    validate_managed_value,
)
from openlease.errors import InvalidRequest
from openlease.extension import (
    BindingProvenance,
    BoundExtension,
    EffectiveConfigurationSnapshot,
    ExtensionInvocation,
    ExtensionInvocationResult,
    ExtensionOutcome,
    ExtensionRegistration,
    FailurePhase,
    HandlerStatus,
    WriteDisposition,
    WriteDispositionKind,
)
from openlease.result import json_value


class ConfigurationConflict(InvalidRequest):
    """A managed assignment was based on a stale value for the same local key."""


_MISSING = object()


@dataclass(frozen=True, slots=True)
class RuntimeBinding:
    identifier: str
    extension_id: str
    path: Path
    codec: str
    layout: ConfigurationLayout
    writable: bool
    scope_kind: str = "direct"
    scope_id: str | None = None
    order: int = 0
    revision: int = 0


def resolve_effective_configuration(
    bindings: tuple[RuntimeBinding, ...],
    codecs: CodecRegistry,
    *,
    state_generation: int | None,
    configuration_generation: int | None,
    attempts: int = 3,
) -> EffectiveConfigurationSnapshot:
    effective: dict[str, ManagedValue] = {}
    winners: dict[str, str] = {}
    provenance: list[BindingProvenance] = []
    for binding in bindings:
        path, content = _stable_read(binding.path, attempts=attempts)
        digest = sha256(content).hexdigest()
        try:
            codec = codecs.require(binding.codec)
            document = codec.decode(content)
            selected = project_namespace(
                codec, document, binding.extension_id, binding.layout
            )
        except CodecError as error:
            raise InvalidRequest(
                f"configuration {binding.codec} decode/layout failed: "
                f"{binding.identifier}",
                details={"phase": "decode", "error": str(error)},
            ) from error
        observed = sha256(f"{binding.revision}:{digest}".encode()).hexdigest()
        selected_immutable = MappingProxyType(
            {key: immutable_managed_value(value) for key, value in selected.items()}
        )
        provenance.append(
            BindingProvenance(
                identifier=binding.identifier,
                extension_id=binding.extension_id,
                scope_kind=binding.scope_kind,
                scope_id=binding.scope_id,
                canonical_path=path,
                codec=binding.codec,
                layout=binding.layout,
                writable=binding.writable,
                order=binding.order,
                binding_revision=binding.revision,
                content_digest=digest,
                observed_generation=observed,
                selected=selected_immutable,
            )
        )
        for key, value in selected.items():
            effective[key] = immutable_managed_value(value)
            winners[key] = binding.identifier
    return EffectiveConfigurationSnapshot(
        values=MappingProxyType(effective),
        bindings=tuple(provenance),
        winners=MappingProxyType(winners),
        state_generation=state_generation,
        configuration_generation=configuration_generation,
    )


class ManagedConfiguration(MutableMapping[str, ManagedValue]):
    def __init__(
        self,
        *,
        resolver: Callable[[], EffectiveConfigurationSnapshot],
        writable: RuntimeBinding | None,
        publisher: ConfigurationPublisher,
        validator: Callable[[Mapping[str, ManagedValue]], None] | None = None,
        candidate_validator: Callable[
            [RuntimeBinding, Mapping[str, ManagedValue]], None
        ]
        | None = None,
    ) -> None:
        self._resolver = resolver
        self._writable = writable
        self._publisher = publisher
        self._validator = validator
        self._candidate_validator = candidate_validator
        self._baselines: dict[str, object] = {}
        self._writes: list[WriteDisposition] = []
        self.last_write: WriteDisposition | None = None

    def snapshot_record(self) -> EffectiveConfigurationSnapshot:
        snapshot = self._resolver()
        self._remember(snapshot)
        if self._validator is not None:
            try:
                self._validator(snapshot.values)
            except Exception as error:
                raise InvalidRequest(
                    "extension configuration validation failed",
                    details={
                        "phase": FailurePhase.VALIDATION.value,
                        "error": str(error),
                    },
                ) from error
        return snapshot

    def snapshot(self) -> Mapping[str, ManagedValue]:
        return self.snapshot_record().values

    def _remember(self, snapshot: EffectiveConfigurationSnapshot) -> None:
        if self._writable is None:
            return
        source = next(
            (
                item
                for item in snapshot.bindings
                if item.identifier == self._writable.identifier
            ),
            None,
        )
        if source is None:
            return
        for key, value in source.selected.items():
            self._baselines[key] = plain_managed_value(value)

    def __getitem__(self, key: str) -> ManagedValue:
        value = self.snapshot()[key]
        return immutable_managed_value(value)

    def __iter__(self) -> Iterator[str]:
        return iter(tuple(self.snapshot()))

    def __len__(self) -> int:
        return len(self.snapshot())

    def __contains__(self, key: object) -> bool:
        return key in self.snapshot()

    def __setitem__(self, key: str, value: ManagedValue) -> None:
        self._mutate(key, value, delete=False)

    def __delitem__(self, key: str) -> None:
        if key not in self.snapshot():
            raise KeyError(key)
        self._mutate(key, _MISSING, delete=True)

    def _mutate(self, key: str, value: object, *, delete: bool) -> None:
        if self._writable is None or not self._writable.writable:
            raise InvalidRequest("extension configuration is read-only")
        if not isinstance(key, str) or not key:
            raise InvalidRequest("configuration key must be a non-empty string")
        if not delete:
            try:
                validate_managed_value(value)
            except CodecError as error:
                raise InvalidRequest(str(error)) from error
        if key not in self._baselines:
            snapshot = self.snapshot_record()
            source = next(
                item
                for item in snapshot.bindings
                if item.identifier == self._writable.identifier
            )
            self._baselines[key] = plain_managed_value(
                source.selected.get(key, _MISSING)
            )
        disposition = self._publisher.mutate(
            self._writable,
            key,
            value,
            baseline=self._baselines.get(key, _MISSING),
            delete=delete,
            validator=self._candidate_validator,
        )
        self.last_write = disposition
        self._writes.append(disposition)
        refreshed = self.snapshot_record()
        source = next(
            item
            for item in refreshed.bindings
            if item.identifier == self._writable.identifier
        )
        self._baselines[key] = plain_managed_value(source.selected.get(key, _MISSING))

    def writes_since(self, offset: int) -> tuple[WriteDisposition, ...]:
        return tuple(self._writes[offset:])

    @property
    def write_count(self) -> int:
        return len(self._writes)


class ConfigurationPublisher:
    def __init__(self, state_root: Path, codecs: CodecRegistry) -> None:
        self.state_root = state_root.resolve()
        self.codecs = codecs

    def mutate(
        self,
        binding: RuntimeBinding,
        key: str,
        value: object,
        *,
        baseline: object,
        delete: bool,
        validator: Callable[[RuntimeBinding, Mapping[str, ManagedValue]], None] | None,
    ) -> WriteDisposition:
        canonical = binding.path.resolve(strict=True)
        if not canonical.is_file():
            raise InvalidRequest(f"configuration source is not a file: {canonical}")
        lock_path = self._lock_path(canonical)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(lock_path)):
            content = canonical.read_bytes()
            prior_digest = sha256(content).hexdigest()
            codec = self.codecs.require(binding.codec)
            document = codec.decode(content)
            selected = project_namespace(
                codec, document, binding.extension_id, binding.layout
            )
            current = plain_managed_value(selected.get(key, _MISSING))
            if not _same_value(current, baseline):
                raise ConfigurationConflict(
                    f"configuration conflict for {binding.identifier}:{key}",
                    details={
                        "binding": binding.identifier,
                        "path": str(canonical),
                        "key": key,
                        "prior_digest": _digest_value(baseline),
                        "current_digest": _digest_value(current),
                    },
                )
            changed = deepcopy(selected)
            if delete:
                changed.pop(key, None)
            else:
                changed[key] = deepcopy(value)
            if validator is not None:
                try:
                    validator(binding, changed)
                except Exception as error:
                    raise InvalidRequest(
                        "extension configuration validation failed",
                        details={
                            "phase": FailurePhase.VALIDATION.value,
                            "error": str(error),
                        },
                    ) from error
            replace_namespace(
                codec, document, binding.extension_id, binding.layout, changed
            )
            rendered = codec.encode(document)
            resulting_digest = sha256(rendered).hexdigest()
            _atomic_replace(canonical, rendered)
        return WriteDisposition(
            WriteDispositionKind.COMMITTED,
            "configuration",
            key,
            canonical,
            binding_id=binding.identifier,
            prior_digest=prior_digest,
            resulting_digest=resulting_digest,
        )

    def initialize(
        self,
        binding: RuntimeBinding,
        initial: Mapping[str, ManagedValue],
        *,
        validator: Callable[[Mapping[str, ManagedValue]], None] | None,
    ) -> None:
        validate_managed_value(initial)
        if validator is not None:
            validator(initial)
        path = binding.path.absolute()
        if path.exists():
            raise InvalidRequest(f"configuration document already exists: {path}")
        if not path.parent.is_dir():
            raise InvalidRequest(f"configuration parent does not exist: {path.parent}")
        codec = self.codecs.require(binding.codec)
        root = (
            initial
            if binding.layout is ConfigurationLayout.DEDICATED
            else {binding.extension_id: initial}
        )
        rendered = codec.encode(codec.new_document(root))
        lock_path = self._lock_path(path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(lock_path)):
            if path.exists():
                raise InvalidRequest(f"configuration document already exists: {path}")
            _atomic_create(path, rendered)

    def _lock_path(self, canonical: Path) -> Path:
        key = sha256(os.path.normcase(str(canonical)).encode("utf-8")).hexdigest()
        return self.state_root / "locks" / "configuration" / f"{key}.lock"


class ManagedRecordMapping(MutableMapping[str, ManagedValue]):
    def __init__(self, root: Path, extension_id: str, role: str) -> None:
        self.root = root.resolve()
        self.extension_id = extension_id
        self.role = role
        self._writes: list[WriteDisposition] = []
        self.last_write: WriteDisposition | None = None

    def _path(self, key: str) -> Path:
        if not isinstance(key, str) or not key:
            raise InvalidRequest("managed record key must be a non-empty string")
        if "\\" in key or ":" in key:
            raise InvalidRequest("managed record key contains an alternate separator")
        pure = PurePosixPath(key)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise InvalidRequest("managed record key escapes its namespace")
        candidate = self.root.joinpath(*pure.parts).with_suffix(
            self.root.joinpath(*pure.parts).suffix + ".json"
        )
        resolved_parent = candidate.parent.resolve()
        try:
            resolved_parent.relative_to(self.root)
        except ValueError as error:
            raise InvalidRequest("managed record key escapes its namespace") from error
        if candidate.exists() and candidate.is_symlink():
            raise InvalidRequest("managed record cannot be a symlink")
        return candidate

    def __getitem__(self, key: str) -> ManagedValue:
        path = self._path(key)
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise KeyError(key) from error
        except (OSError, json.JSONDecodeError) as error:
            raise InvalidRequest(
                f"managed {self.role} record is invalid: {key}"
            ) from error
        if (
            envelope.get("version") != 1
            or envelope.get("extension") != self.extension_id
            or envelope.get("store") != self.role
        ):
            raise InvalidRequest(f"managed {self.role} ownership mismatch: {key}")
        return immutable_managed_value(envelope["value"])

    def __setitem__(self, key: str, value: ManagedValue) -> None:
        try:
            validate_managed_value(value)
        except CodecError as error:
            raise InvalidRequest(str(error)) from error
        path = self._path(key)
        if path.exists():
            self[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "version": 1,
            "extension": self.extension_id,
            "store": self.role,
            "disposable": self.role == "cache",
            "value": plain_managed_value(value),
        }
        rendered = (json.dumps(envelope, ensure_ascii=False, indent=2) + "\n").encode()
        prior = sha256(path.read_bytes()).hexdigest() if path.exists() else None
        _atomic_replace(path, rendered)
        disposition = WriteDisposition(
            WriteDispositionKind.COMMITTED,
            self.role,
            key,
            path,
            prior_digest=prior,
            resulting_digest=sha256(rendered).hexdigest(),
        )
        self.last_write = disposition
        self._writes.append(disposition)

    def __delitem__(self, key: str) -> None:
        path = self._path(key)
        self[key]
        path.unlink()
        disposition = WriteDisposition(
            WriteDispositionKind.COMMITTED, self.role, key, path
        )
        self.last_write = disposition
        self._writes.append(disposition)

    def __iter__(self) -> Iterator[str]:
        if not self.root.exists():
            return iter(())
        keys = []
        for path in self.root.rglob("*.json"):
            if path.is_symlink():
                continue
            relative = path.relative_to(self.root).as_posix()
            keys.append(relative[:-5])
        return iter(sorted(keys))

    def __len__(self) -> int:
        return sum(1 for _item in self)

    def snapshot(self) -> Mapping[str, ManagedValue]:
        return MappingProxyType({key: self[key] for key in self})

    def writes_since(self, offset: int) -> tuple[WriteDisposition, ...]:
        return tuple(self._writes[offset:])

    @property
    def write_count(self) -> int:
        return len(self._writes)


class ExtensionRuntime:
    def __init__(
        self,
        state_root: Path,
        registrations: Mapping[str, ExtensionRegistration],
        codecs: CodecRegistry,
        *,
        retention: int = 100,
    ) -> None:
        self.state_root = state_root.resolve()
        self.registrations = registrations
        self.codecs = codecs
        self.publisher = ConfigurationPublisher(self.state_root, codecs)
        self.retention = retention

    def bind(
        self,
        registration: ExtensionRegistration,
        context,
        bindings: tuple[RuntimeBinding, ...],
        *,
        writable_source: str | None = None,
    ) -> BoundExtension:
        writable = None
        if writable_source is not None:
            matching = [item for item in bindings if item.identifier == writable_source]
            if len(matching) != 1:
                raise InvalidRequest(
                    f"writable configuration source is not uniquely available: "
                    f"{writable_source}"
                )
            writable = matching[0]
            if not writable.writable:
                raise InvalidRequest("selected configuration source is read-only")

        def resolve():
            snapshot = resolve_effective_configuration(
                bindings,
                self.codecs,
                state_generation=context.state_generation,
                configuration_generation=context.configuration_generation,
            )
            if registration.validator is not None:
                try:
                    registration.validator(snapshot.values)
                except Exception as error:
                    raise InvalidRequest(
                        "extension configuration validation failed",
                        details={
                            "phase": FailurePhase.VALIDATION.value,
                            "error": str(error),
                        },
                    ) from error
            return snapshot

        def validate_candidate(
            changed_binding: RuntimeBinding,
            changed: Mapping[str, ManagedValue],
        ) -> None:
            if registration.validator is None:
                return
            current = resolve_effective_configuration(
                bindings,
                self.codecs,
                state_generation=context.state_generation,
                configuration_generation=context.configuration_generation,
            )
            effective: dict[str, ManagedValue] = {}
            for source in current.bindings:
                selected = (
                    changed
                    if source.identifier == changed_binding.identifier
                    else source.selected
                )
                effective.update(selected)
            registration.validator(MappingProxyType(effective))

        config = ManagedConfiguration(
            resolver=resolve,
            writable=writable,
            publisher=self.publisher,
            validator=registration.validator,
            candidate_validator=validate_candidate,
        )
        data = ManagedRecordMapping(
            context.roots.data.path / "records",
            registration.manifest.identifier,
            "data",
        )
        cache = ManagedRecordMapping(
            context.roots.cache.path / "records",
            registration.manifest.identifier,
            "cache",
        )
        bound: BoundExtension

        def invoke(operation: str, input: object):
            return self.invoke(registration, bound, operation, input)

        def batch():
            return ManagedBatch(config, data, cache, self.state_root)

        bound = BoundExtension(
            registration.manifest.identifier,
            context,
            config,
            data,
            cache,
            invoke,
            batch,
        )
        config.snapshot_record()
        return bound

    def invoke(
        self,
        registration: ExtensionRegistration,
        bound: BoundExtension,
        operation_name: str,
        input: object,
        *,
        event=None,
    ) -> ExtensionInvocationResult:
        operation = next(
            (item for item in registration.operations if item.name == operation_name),
            None,
        )
        if operation is None:
            raise InvalidRequest(
                f"extension operation not registered: {operation_name}"
            )
        if bound.context.target_kind not in operation.target_kinds:
            raise InvalidRequest(
                f"extension operation rejects target: {bound.context.target_kind}"
            )
        snapshot = bound.config.snapshot_record()
        offsets = (
            bound.config.write_count,
            bound.data.write_count,
            bound.cache.write_count,
        )
        invocation = ExtensionInvocation(
            input,
            bound.context,
            bound.config,
            bound.data,
            bound.cache,
            event,
            bound._batch_factory,
        )
        value = None
        diagnostic = None
        status = HandlerStatus.COMPLETED
        phase = None
        try:
            value = operation.handler(invocation)
        except Exception as error:
            status = HandlerStatus.FAILED
            phase = FailurePhase.HANDLER
            diagnostic = str(error)
        writes = (
            *bound.config.writes_since(offsets[0]),
            *bound.data.writes_since(offsets[1]),
            *bound.cache.writes_since(offsets[2]),
        )
        target = _target_identity(bound.context.target)
        outcome = ExtensionOutcome(
            version=1,
            extension_id=registration.manifest.identifier,
            operation=operation_name,
            target=target,
            handler_status=status,
            failure_phase=phase,
            callback_event=getattr(event, "event", None),
            callback_mode=getattr(event, "mode", None),
            state_generation=bound.context.state_generation,
            configuration_generation=bound.context.configuration_generation,
            binding_digests=MappingProxyType(
                {item.identifier: item.content_digest for item in snapshot.bindings}
            ),
            writes=tuple(writes),
            diagnostic=diagnostic,
        )
        outcome_error = None
        try:
            self._record_outcome(bound, outcome)
        except Exception as error:
            outcome_error = str(error)
        return ExtensionInvocationResult(
            registration.manifest.identifier,
            operation_name,
            target,
            status,
            value,
            snapshot,
            tuple(writes),
            outcome,
            outcome_error,
        )

    def _record_outcome(self, bound: BoundExtension, outcome: ExtensionOutcome) -> None:
        root = bound.context.roots.data.path / "outcomes"
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{uuid4().hex}.json"
        payload = {"version": 1, "outcome": json_value(outcome)}
        _atomic_create(
            path,
            (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode(),
        )
        paths = sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime_ns)
        for old in paths[: max(0, len(paths) - self.retention)]:
            old.unlink()

    def outcomes(self, extension_id: str, data_root: Path) -> tuple[Mapping, ...]:
        root = data_root / "outcomes"
        if not root.exists():
            return ()
        results = []
        for path in sorted(root.glob("*.json")):
            results.append(json.loads(path.read_text(encoding="utf-8"))["outcome"])
        return tuple(results)


@dataclass(slots=True)
class _BatchView:
    config: MutableMapping[str, ManagedValue]
    data: MutableMapping[str, ManagedValue]
    cache: MutableMapping[str, ManagedValue]


class _StagedMapping(MutableMapping[str, ManagedValue]):
    def __init__(self, base: MutableMapping[str, ManagedValue]) -> None:
        self.base = base
        self.pending: dict[str, tuple[bool, ManagedValue | None]] = {}

    def __getitem__(self, key):
        if key in self.pending:
            delete, value = self.pending[key]
            if delete:
                raise KeyError(key)
            return value
        return self.base[key]

    def __setitem__(self, key, value):
        validate_managed_value(value)
        self.pending[key] = (False, value)

    def __delitem__(self, key):
        self[key]
        self.pending[key] = (True, None)

    def __iter__(self):
        keys = set(self.base)
        for key, (delete, _value) in self.pending.items():
            if delete:
                keys.discard(key)
            else:
                keys.add(key)
        return iter(sorted(keys))

    def __len__(self):
        return sum(1 for _item in self)


class ManagedBatch:
    def __init__(self, config, data, cache, state_root: Path) -> None:
        self.state_root = state_root
        self.config = _StagedMapping(config)
        self.data = _StagedMapping(data)
        self.cache = _StagedMapping(cache)
        self.view = _BatchView(self.config, self.data, self.cache)
        self.dispositions: tuple[WriteDisposition, ...] = ()

    def __enter__(self):
        return self.view

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is not None:
            return False
        completed: list[WriteDisposition] = []
        try:
            for staged in (self.config, self.data, self.cache):
                base = staged.base
                for key, (delete, value) in staged.pending.items():
                    if delete:
                        del base[key]
                    else:
                        base[key] = value
                    disposition = getattr(base, "last_write", None)
                    if disposition is not None:
                        completed.append(disposition)
        except Exception:
            if completed:
                journal = self.state_root / "recovery" / f"batch-{uuid4().hex}.json"
                journal.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "version": 1,
                    "completed": json_value(tuple(completed)),
                    "recovery_required": True,
                }
                _atomic_create(journal, json.dumps(payload).encode())
            raise
        self.dispositions = tuple(completed)
        return False


def _stable_read(path: Path, *, attempts: int) -> tuple[Path, bytes]:
    try:
        canonical = path.resolve(strict=True)
    except OSError as error:
        raise InvalidRequest(f"configuration source is unavailable: {path}") from error
    for _attempt in range(attempts):
        try:
            before = canonical.stat()
            content = canonical.read_bytes()
            after = canonical.stat()
        except OSError as error:
            raise InvalidRequest(
                f"configuration source is unavailable: {canonical}"
            ) from error

        def identity(stat):
            return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)

        if identity(before) == identity(after):
            if not canonical.is_file():
                break
            return canonical, content
    raise InvalidRequest(f"configuration source changed repeatedly: {canonical}")


def _same_value(left: object, right: object) -> bool:
    if left is _MISSING or right is _MISSING:
        return left is right
    return left == right


def _digest_value(value: object) -> str | None:
    if value is _MISSING:
        return None
    encoded = json.dumps(
        plain_managed_value(value), sort_keys=True, default=str
    ).encode()
    return sha256(encoded).hexdigest()


def _atomic_replace(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.openlease-", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_create(path: Path, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        _sync_directory(path.parent)
    except Exception:
        with suppress(OSError):
            path.unlink()
        raise


def _sync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass


def _target_identity(target: object) -> str:
    path = getattr(target, "path", None)
    if path is not None:
        return str(path)
    kind = getattr(target, "kind", "target")
    identifier = getattr(target, "identifier", "unknown")
    kind = getattr(kind, "value", kind)
    return f"{kind}:{identifier}"
