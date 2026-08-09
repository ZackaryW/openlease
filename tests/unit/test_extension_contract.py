from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from openlease import (
    CallbackEvent,
    CallbackMode,
    ExtensionCallback,
    ExtensionManifest,
    ExtensionOperation,
    ExtensionRegistration,
    InvalidRequest,
    OpenLease,
)
from openlease.extension import EXTENSION_CONTRACT_VERSION


def handler(_invocation):
    return "ok"


def test_registration_is_current_immutable_and_inert(tmp_path) -> None:
    calls: list[str] = []

    def operation(_invocation):
        calls.append("called")

    registration = ExtensionRegistration(
        ExtensionManifest("zpp.traits"),
        operations=(ExtensionOperation("resolve", operation),),
    )

    system = OpenLease(tmp_path / "state", extensions=(registration,))

    assert system.registered_extensions == ("zpp.traits",)
    assert calls == []
    assert not (tmp_path / "state" / "extensions").exists()
    with pytest.raises(FrozenInstanceError):
        registration.manifest.identifier = "other"  # type: ignore[misc]


@pytest.mark.parametrize(
    "registration, message",
    [
        (
            ExtensionRegistration(ExtensionManifest("zpp", 1)),
            "unsupported extension contract",
        ),
        (
            ExtensionRegistration(
                ExtensionManifest("zpp"),
                operations=(ExtensionOperation("run", handler),) * 2,
            ),
            "duplicate extension operation",
        ),
        (
            ExtensionRegistration(
                ExtensionManifest("zpp"),
                callbacks=(
                    ExtensionCallback(
                        CallbackEvent.RECONCILE_BEFORE_REPOSITORY,
                        "missing",
                        (CallbackMode.OBSERVE,),
                    ),
                ),
            ),
            "missing operation",
        ),
    ],
)
def test_registration_rejects_invalid_current_contract(
    tmp_path, registration, message
) -> None:
    with pytest.raises(InvalidRequest, match=message):
        OpenLease(tmp_path / "state", extensions=(registration,))


def test_contract_version_is_a_clean_break() -> None:
    assert EXTENSION_CONTRACT_VERSION == 2
    with pytest.raises(TypeError):
        ExtensionRegistration(  # type: ignore[call-arg]
            ExtensionManifest("former"), resolver=lambda context: context
        )


def test_reconciliation_verifier_constructor_is_removed(tmp_path) -> None:
    with pytest.raises(TypeError):
        OpenLease(tmp_path / "state", verifier=lambda _scope, _paths: None)  # type: ignore[call-arg]
