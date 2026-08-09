from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import get_type_hints

import pytest

from openlease import (
    BoundExtension,
    CallbackEvent,
    CallbackMode,
    ConfigurationLayout,
    ExtensionCallback,
    ExtensionDocumentBinding,
    ExtensionInvocation,
    ExtensionManifest,
    ExtensionOperation,
    ExtensionRegistration,
    InvalidRequest,
    ManagedConfiguration,
    OpenLease,
)
from openlease.extension import EXTENSION_CONTRACT_VERSION, ManagedMapping


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
    assert EXTENSION_CONTRACT_VERSION == 3
    with pytest.raises(TypeError):
        ExtensionRegistration(  # type: ignore[call-arg]
            ExtensionManifest("former"), resolver=lambda context: context
        )


def test_version_two_registration_is_rejected_with_current_guidance(tmp_path) -> None:
    registration = ExtensionRegistration(ExtensionManifest("former", 2))

    with pytest.raises(InvalidRequest) as captured:
        OpenLease(tmp_path / "state", extensions=(registration,))

    assert captured.value.details == {
        "extension": "former",
        "version": 2,
        "expected_version": 3,
    }


def test_configuration_uses_the_public_protocol_without_widening_other_stores() -> None:
    bound_hints = get_type_hints(BoundExtension)
    invocation_hints = get_type_hints(ExtensionInvocation)

    assert getattr(ManagedConfiguration, "_is_protocol", False) is True
    with pytest.raises(TypeError, match="Protocols cannot be instantiated"):
        ManagedConfiguration()  # type: ignore[call-arg]
    assert bound_hints["config"] is ManagedConfiguration
    assert invocation_hints["config"] is ManagedConfiguration
    assert bound_hints["data"] is ManagedMapping
    assert bound_hints["cache"] is ManagedMapping
    assert invocation_hints["data"] is ManagedMapping
    assert invocation_hints["cache"] is ManagedMapping


def test_reconciliation_verifier_constructor_is_removed(tmp_path) -> None:
    with pytest.raises(TypeError):
        OpenLease(tmp_path / "state", verifier=lambda _scope, _paths: None)  # type: ignore[call-arg]


def test_direct_document_binding_is_frozen_and_requires_explicit_shape(
    tmp_path,
) -> None:
    binding = ExtensionDocumentBinding(
        extension_id="zpp.behave",
        path=tmp_path / "zpp.behave.yaml",
        codec="yaml",
        layout=ConfigurationLayout.DEDICATED,
        writable=True,
    )

    assert binding.codec == "yaml"
    assert binding.layout is ConfigurationLayout.DEDICATED
    with pytest.raises(FrozenInstanceError):
        binding.codec = "json"  # type: ignore[misc]
    with pytest.raises(TypeError):
        ExtensionDocumentBinding(  # type: ignore[call-arg]
            extension_id="zpp.behave",
            path=tmp_path / "missing.yaml",
        )
