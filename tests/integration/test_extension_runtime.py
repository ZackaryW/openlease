from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from openlease import (
    ConfigurationLayout,
    ConfigurationTarget,
    ExtensionManifest,
    ExtensionOperation,
    ExtensionRegistration,
    HandlerStatus,
    InvalidRequest,
    OpenLease,
    WriteDispositionKind,
    extension_runtime,
)
from openlease.extension_runtime import ConfigurationConflict


def registration(identifier="zpp.behave", operation=None, validator=None):
    operations = () if operation is None else (ExtensionOperation("run", operation),)
    return ExtensionRegistration(
        ExtensionManifest(identifier), operations=operations, validator=validator
    )


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ("git", "-C", str(repo), *args),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def repository(path: Path) -> Path:
    path.mkdir()
    git(path, "init", "--quiet")
    git(path, "config", "user.email", "tests@openlease.invalid")
    git(path, "config", "user.name", "OpenLease Tests")
    git(path, "commit", "--allow-empty", "--quiet", "-m", "base")
    return path


def test_direct_dedicated_document_is_live_defensive_and_automatically_saved(
    tmp_path: Path,
) -> None:
    source = tmp_path / "zpp.behave.yaml"
    source.write_text("version: 1\ncommands:\n  bdd: [old]\n", encoding="utf-8")
    system = OpenLease(tmp_path / "state", extensions=(registration(),))
    before = system.snapshot()

    bound = system.bind_extension_document(
        "zpp.behave",
        source,
        codec="yaml",
        layout=ConfigurationLayout.DEDICATED,
        writable=True,
    )
    nested = bound.config["commands"]
    with pytest.raises(TypeError):
        nested["bdd"] = ("changed",)  # type: ignore[index]
    bound.config["commands"] = {"bdd": ["new"]}

    assert "new" in source.read_text(encoding="utf-8")
    assert bound.config.snapshot()["commands"] == {"bdd": ("new",)}
    assert system.snapshot() == before
    assert bound.config.last_write.kind is WriteDispositionKind.COMMITTED


def test_shared_document_preserves_other_extension_and_detects_same_key_conflict(
    tmp_path: Path,
) -> None:
    source = tmp_path / "shared.yaml"
    source.write_text(
        "# shared\nextension-a:\n  key: old\nextension-b:\n  key: keep\n",
        encoding="utf-8",
    )
    system = OpenLease(
        tmp_path / "state",
        extensions=(registration("extension-a"), registration("extension-b")),
    )
    first = system.bind_extension_document(
        "extension-a", source, codec="yaml", layout="shared", writable=True
    )
    second = system.bind_extension_document(
        "extension-a", source, codec="yaml", layout="shared", writable=True
    )
    assert first.config["key"] == "old"
    assert second.config["key"] == "old"

    first.config["key"] = "first"
    with pytest.raises(ConfigurationConflict):
        second.config["key"] = "second"

    rendered = source.read_text(encoding="utf-8")
    assert "# shared" in rendered
    assert "first" in rendered
    assert "keep" in rendered


def test_unrelated_shared_namespace_changes_rebase(tmp_path: Path) -> None:
    source = tmp_path / "shared.json"
    source.write_text(
        json.dumps({"extension-a": {"a": 1}, "extension-b": {"b": 1}}),
        encoding="utf-8",
    )
    system = OpenLease(
        tmp_path / "state",
        extensions=(registration("extension-a"), registration("extension-b")),
    )
    a = system.bind_extension_document(
        "extension-a", source, codec="json", layout="shared", writable=True
    )
    b = system.bind_extension_document(
        "extension-b", source, codec="json", layout="shared", writable=True
    )
    assert a.config["a"] == 1
    assert b.config["b"] == 1

    b.config["b"] = 2
    a.config["a"] = 2

    assert json.loads(source.read_text(encoding="utf-8")) == {
        "extension-a": {"a": 2},
        "extension-b": {"b": 2},
    }


def test_read_only_direct_binding_rejects_mutation_before_io(tmp_path: Path) -> None:
    source = tmp_path / "config.json"
    source.write_text('{"key": 1}', encoding="utf-8")
    system = OpenLease(tmp_path / "state", extensions=(registration("extension"),))
    bound = system.bind_extension_document(
        "extension", source, codec="json", layout="dedicated", writable=False
    )
    before = source.read_bytes()

    with pytest.raises(InvalidRequest, match="read-only"):
        bound.config["key"] = 2

    assert source.read_bytes() == before
    assert not (tmp_path / "state" / "locks").exists()


def test_initialize_direct_document_requires_absence_and_writable_authority(
    tmp_path: Path,
) -> None:
    source = tmp_path / "config.yaml"
    system = OpenLease(tmp_path / "state", extensions=(registration("extension"),))

    bound = system.initialize_extension_document(
        "extension",
        source,
        codec="yaml",
        layout="dedicated",
        initial={"key": "value"},
    )

    assert bound.config["key"] == "value"
    with pytest.raises(InvalidRequest, match="already exists"):
        system.initialize_extension_document(
            "extension",
            source,
            codec="yaml",
            layout="dedicated",
            initial={},
        )


def test_named_operation_gets_narrow_mappings_and_persists_truthful_outcome(
    tmp_path: Path,
) -> None:
    source = tmp_path / "config.json"
    source.write_text('{"runner": "argv"}', encoding="utf-8")

    def run(invocation):
        invocation.data["last/result"] = {"ok": True}
        invocation.cache["probe"] = "cached"
        invocation.config["runner"] = "go-task"
        return {"opaque": invocation.input}

    system = OpenLease(tmp_path / "state", extensions=(registration(operation=run),))
    bound = system.bind_extension_document(
        "zpp.behave", source, codec="json", layout="dedicated", writable=True
    )

    result = bound.invoke("run", {"targets": ["bdd"]})

    assert result.handler_status is HandlerStatus.COMPLETED
    assert result.value == {"opaque": {"targets": ["bdd"]}}
    assert {item.store for item in result.writes} == {"configuration", "data", "cache"}
    assert result.outcome.handler_status is HandlerStatus.COMPLETED
    assert result.outcome_recording_error is None
    assert system.inspect_extension_outcomes("zpp.behave")


def test_completed_managed_write_survives_later_handler_failure(tmp_path: Path) -> None:
    source = tmp_path / "config.json"
    source.write_text("{}", encoding="utf-8")

    def fail(invocation):
        invocation.data["completed"] = True
        raise RuntimeError("after effect")

    system = OpenLease(tmp_path / "state", extensions=(registration(operation=fail),))
    bound = system.bind_extension_document(
        "zpp.behave", source, codec="json", layout="dedicated", writable=True
    )

    result = bound.invoke("run")

    assert result.handler_status is HandlerStatus.FAILED
    assert result.writes[0].kind is WriteDispositionKind.COMMITTED
    assert bound.data["completed"] is True
    assert result.outcome.diagnostic == "after effect"


def test_configuration_validator_runs_before_handler(tmp_path: Path) -> None:
    source = tmp_path / "config.json"
    source.write_text('{"invalid": true}', encoding="utf-8")
    called = False

    def validate(value):
        if "runner" not in value:
            raise ValueError("runner required")

    def run(_invocation):
        nonlocal called
        called = True

    system = OpenLease(
        tmp_path / "state",
        extensions=(registration(operation=run, validator=validate),),
    )

    with pytest.raises(InvalidRequest, match="validation"):
        system.bind_extension_document(
            "zpp.behave", source, codec="json", layout="dedicated"
        )
    assert called is False


def test_space_bindings_shallow_overlay_remain_live_and_select_exact_writer(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path / "repo")
    machine = tmp_path / "machine.json"
    scoped = repo / "extension.json"
    machine.write_text(
        '{"nested": {"machine": 1}, "winner": "machine", "low": 1}',
        encoding="utf-8",
    )
    scoped.write_text(
        '{"nested": {"repository": 2}, "winner": "repository"}',
        encoding="utf-8",
    )
    system = OpenLease(tmp_path / "state", extensions=(registration("extension"),))
    system.register_repository("repo", repo)
    system.create_space("work")
    system.associate("work", ("repo",))
    system.bind_configuration_source(
        "extension",
        "machine",
        machine,
        "machine",
        codec="json",
        layout="dedicated",
        writable=True,
    )
    system.bind_configuration_source(
        "extension",
        "repository",
        scoped,
        "repository",
        "repo",
        codec="json",
        layout="dedicated",
        writable=True,
    )

    lower = system.bind_extension(
        "extension",
        "work",
        ConfigurationTarget.repository("repo"),
        writable_source="machine",
    )
    assert lower.config.snapshot() == {
        "nested": {"repository": 2},
        "winner": "repository",
        "low": 1,
    }
    lower.config["winner"] = "changed-below"
    assert lower.config["winner"] == "repository"

    scoped.write_text('{"nested": {"live": 3}, "winner": "edited"}', encoding="utf-8")
    assert lower.config["nested"] == {"live": 3}
    snapshot = lower.config.snapshot_record()
    assert snapshot.bindings[-1].identifier == "repository"
    assert snapshot.winners["winner"] == "repository"


def test_scope_shorthand_requires_one_eligible_writer(tmp_path: Path) -> None:
    repo = repository(tmp_path / "repo")
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    system = OpenLease(tmp_path / "state", extensions=(registration("extension"),))
    system.register_repository("repo", repo)
    system.create_space("work")
    system.associate("work", ("repo",))
    for identifier, path in (("first", first), ("second", second)):
        system.bind_configuration_source(
            "extension",
            identifier,
            path,
            "machine",
            codec="json",
            layout="dedicated",
            writable=True,
        )

    with pytest.raises(InvalidRequest, match="ambiguous"):
        system.bind_extension(
            "extension",
            "work",
            ConfigurationTarget.repository("repo"),
            writable_scope=("machine", None),
        )


def test_concurrent_unrelated_namespace_writes_are_serialized(tmp_path: Path) -> None:
    source = tmp_path / "shared.json"
    source.write_text(
        '{"extension-a": {"key": 1}, "extension-b": {"key": 1}}',
        encoding="utf-8",
    )
    system = OpenLease(
        tmp_path / "state",
        extensions=(registration("extension-a"), registration("extension-b")),
    )
    a = system.bind_extension_document(
        "extension-a", source, codec="json", layout="shared", writable=True
    )
    b = system.bind_extension_document(
        "extension-b", source, codec="json", layout="shared", writable=True
    )
    assert a.config["key"] == b.config["key"] == 1
    barrier = Barrier(2)

    def write(bound, value):
        barrier.wait()
        bound.config["key"] = value

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(write, a, 2)
        second = pool.submit(write, b, 3)
        first.result(timeout=5)
        second.result(timeout=5)

    assert json.loads(source.read_text(encoding="utf-8")) == {
        "extension-a": {"key": 2},
        "extension-b": {"key": 3},
    }


def test_atomic_publication_failure_preserves_prior_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "config.json"
    source.write_text('{"key": "prior"}', encoding="utf-8")
    system = OpenLease(tmp_path / "state", extensions=(registration("extension"),))
    bound = system.bind_extension_document(
        "extension", source, codec="json", layout="dedicated", writable=True
    )
    assert bound.config["key"] == "prior"
    before = source.read_bytes()

    def fail_replace(_source, _destination):
        raise OSError("injected replacement failure")

    monkeypatch.setattr(extension_runtime.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected"):
        bound.config["key"] = "new"

    assert source.read_bytes() == before
    assert not tuple(tmp_path.glob(".config.json.openlease-*.tmp"))


def test_initialization_is_confined_to_an_explicit_boundary(tmp_path: Path) -> None:
    system = OpenLease(tmp_path / "state", extensions=(registration("extension"),))
    boundary = tmp_path / "allowed"
    boundary.mkdir()

    with pytest.raises(InvalidRequest, match="escapes"):
        system.initialize_extension_document(
            "extension",
            tmp_path / "outside" / "config.json",
            codec="json",
            layout="dedicated",
            initial={},
            boundary=boundary,
            create_parents=True,
        )
    assert not (tmp_path / "outside").exists()


def test_outcome_recording_failure_does_not_retry_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "config.json"
    source.write_text("{}", encoding="utf-8")
    calls = 0

    def handler(invocation):
        nonlocal calls
        calls += 1
        invocation.data["effect"] = calls
        return "opaque"

    system = OpenLease(
        tmp_path / "state", extensions=(registration(operation=handler),)
    )
    bound = system.bind_extension_document(
        "zpp.behave", source, codec="json", layout="dedicated", writable=True
    )
    monkeypatch.setattr(
        system.extension_runtime,
        "_record_outcome",
        lambda _bound, _outcome: (_ for _ in ()).throw(OSError("outcome failed")),
    )

    result = bound.invoke("run")

    assert calls == 1
    assert bound.data["effect"] == 1
    assert result.outcome_recording_error == "outcome failed"
    assert result.handler_status is HandlerStatus.COMPLETED


def test_zpp_and_runner_configuration_remain_opaque_downstream_data(
    tmp_path: Path,
) -> None:
    source = tmp_path / "zpp.behave.yaml"
    source.write_text(
        "version: 1\nrunner:\n  kind: nx\n  argv: [go-task, test]\n",
        encoding="utf-8",
    )
    systems = (
        registration("zpp.traits"),
        registration("zpp.behave"),
    )
    system = OpenLease(tmp_path / ".zpp", extensions=systems)
    bound = system.bind_extension_document(
        "zpp.behave", source, codec="yaml", layout="dedicated"
    )

    assert bound.config["runner"] == {
        "kind": "nx",
        "argv": ("go-task", "test"),
    }
    assert all(
        "zpp" not in type(system.codecs.require(name)).__module__
        for name in system.codecs.names
    )
