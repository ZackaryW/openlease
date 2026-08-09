from __future__ import annotations

from types import MappingProxyType

from behave import given, then, when

from features.support.openlease_support import capture, ensure_topology, space
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
    to_plain_managed_value,
)


def configured_system(context, handler, *, validator=None):
    registration = ExtensionRegistration(
        ExtensionManifest("zpp.behave"),
        operations=(ExtensionOperation("run", handler),),
        validator=validator,
    )
    context.system = OpenLease(
        context.root / "state",
        openspec=context.openspec,
        extensions=(registration,),
    )
    context.source = context.root / "zpp.behave.json"
    context.source.write_text('{"runner": "argv"}', encoding="utf-8")


def bind(context):
    context.bound = context.system.bind_extension_document(
        "zpp.behave",
        context.source,
        codec="json",
        layout="dedicated",
        writable=True,
    )


@given("two version-three extensions declare named operations")
def given_two_extensions(context) -> None:
    context.calls = []

    def operation(_invocation):
        context.calls.append("operation")

    def validator(_configuration):
        context.calls.append("validator")

    context.registrations = tuple(
        ExtensionRegistration(
            ExtensionManifest(identifier),
            operations=(ExtensionOperation("run", operation),),
            validator=validator,
        )
        for identifier in ("zpp.traits", "zpp.behave")
    )


@given("a version-two extension declares a named operation")
def given_version_two_extension(context) -> None:
    context.calls = []

    def operation(_invocation):
        context.calls.append("operation")

    context.registrations = (
        ExtensionRegistration(
            ExtensionManifest("former", 2),
            operations=(ExtensionOperation("run", operation),),
        ),
    )


@when("the host attempts to construct the bounded runtime")
def when_attempt_construct(context) -> None:
    capture(
        context,
        lambda: OpenLease(
            context.root / "state",
            openspec=context.openspec,
            extensions=context.registrations,
        ),
    )


@then("registration fails with version-three guidance")
def then_version_three_guidance(context) -> None:
    assert isinstance(context.error, InvalidRequest)
    assert context.error.details["version"] == 2
    assert context.error.details["expected_version"] == 3


@then("no extension code or managed write runs")
def then_no_rejected_effects(context) -> None:
    assert context.calls == []
    assert not (context.root / "state" / "extensions").exists()


@when("the host constructs the bounded runtime")
def when_construct(context) -> None:
    context.system = OpenLease(
        context.root / "state",
        openspec=context.openspec,
        extensions=context.registrations,
    )


@then("both exact identities are registered")
def then_registered(context) -> None:
    assert context.system.registered_extensions == ("zpp.traits", "zpp.behave")


@then("no validator operation callback managed write or lifecycle action runs")
def then_inert(context) -> None:
    assert context.calls == []
    assert context.system.snapshot().generation == 0
    assert not (context.root / "state" / "extensions").exists()


@given("a registered operation and configuration that names a runner")
def given_named_operation(context) -> None:
    context.calls = []

    def handler(invocation):
        context.calls.append(invocation.input)
        return "done"

    configured_system(context, handler)


@when("the host binds the configuration without invoking the operation")
def when_bind_only(context) -> None:
    bind(context)


@then("the operation has not run")
def then_not_run(context) -> None:
    assert context.calls == []


@when("the host explicitly invokes the named operation")
def when_invoke(context) -> None:
    if not hasattr(context, "bound"):
        bind(context)
    context.result = context.bound.invoke("run", {"target": "bdd"})


@when("the host explicitly invokes that operation")
def when_invoke_that(context) -> None:
    when_invoke(context)


@then("exactly that operation runs once with opaque input")
def then_once(context) -> None:
    assert context.calls == [{"target": "bdd"}]
    assert context.result.value == "done"


@given("an extension validator rejects the bound configuration")
def given_rejecting_validator(context) -> None:
    context.called = False

    def handler(_invocation):
        context.called = True

    def validator(_value):
        raise ValueError("rejected")

    configured_system(context, handler, validator=validator)


@when("the host attempts to bind the extension")
def when_bind_invalid(context) -> None:
    capture(context, lambda: bind(context))


@then("validation fails before the handler starts")
def then_validation_first(context) -> None:
    assert isinstance(context.error, InvalidRequest)
    assert context.called is False


@then("the error is configuration_validation_failed")
def then_validation_code(context) -> None:
    assert context.error.code == "configuration_validation_failed"


@then("no managed record is created")
def then_no_record(context) -> None:
    assert not (context.root / "state" / "extensions").exists()


@given("a bound extension with ordered configuration sources")
def given_ordered_configuration(context) -> None:
    context.system = OpenLease(
        context.root / "state",
        openspec=context.openspec,
        extensions=(ExtensionRegistration(ExtensionManifest("zpp.behave")),),
    )
    ensure_topology(context)
    space(context, "work")
    machine = context.root / "machine.json"
    repository = context.repos["repo-1"] / "behavior.json"
    machine.write_text('{"runner": "machine", "low": true}', encoding="utf-8")
    repository.write_text('{"runner": "repository"}', encoding="utf-8")
    context.system.bind_configuration_source(
        "zpp.behave",
        "machine",
        machine,
        "machine",
        codec="json",
        layout="dedicated",
    )
    context.system.bind_configuration_source(
        "zpp.behave",
        "repository",
        repository,
        "repository",
        "repo-1",
        codec="json",
        layout="dedicated",
    )
    context.bound = context.system.bind_extension(
        "zpp.behave",
        "work",
        ConfigurationTarget.repository("repo-1"),
    )


@when("the host requests its public configuration snapshot record")
def when_request_snapshot_record(context) -> None:
    context.snapshot_record = context.bound.config.snapshot_record()


@then("the record identifies every binding and the winning source for each key")
def then_record_explains_sources(context) -> None:
    assert [item.identifier for item in context.snapshot_record.bindings] == [
        "machine",
        "repository",
    ]
    assert context.snapshot_record.winners == {
        "runner": "repository",
        "low": "machine",
    }
    assert all(item.content_digest for item in context.snapshot_record.bindings)


@then("configuration exposes result-returning mutations while data and cache do not")
def then_configuration_protocol_is_specific(context) -> None:
    assert hasattr(context.bound.config, "snapshot_record")
    assert hasattr(context.bound.config, "set")
    assert hasattr(context.bound.config, "delete")
    assert not hasattr(context.bound.data, "snapshot_record")
    assert not hasattr(context.bound.cache, "snapshot_record")


@given("a bound extension with one writable configuration source")
def given_one_writable_source(context) -> None:
    context.system = OpenLease(
        context.root / "state",
        openspec=context.openspec,
        extensions=(ExtensionRegistration(ExtensionManifest("zpp.behave")),),
    )
    context.source = context.root / "config.json"
    context.source.write_text('{"runner": "argv", "remove": true}', encoding="utf-8")
    context.bound = context.system.bind_extension_document(
        "zpp.behave",
        context.source,
        codec="json",
        layout=ConfigurationLayout.DEDICATED,
        writable=True,
    )


@when("the host explicitly sets and deletes configuration keys")
def when_explicitly_mutate(context) -> None:
    context.dispositions = (
        context.bound.config.set("runner", "go-task"),
        context.bound.config.delete("remove"),
    )
    context.bound.config["automatic"] = True


@then("each call returns its exact completed write disposition")
def then_exact_dispositions(context) -> None:
    assert [item.key for item in context.dispositions] == ["runner", "remove"]
    assert all(
        item.kind is WriteDispositionKind.COMMITTED for item in context.dispositions
    )
    assert all(item.path == context.source.resolve() for item in context.dispositions)
    assert all(item.binding_id for item in context.dispositions)


@then("mapping assignment still saves automatically")
def then_assignment_still_saves(context) -> None:
    assert context.bound.config["automatic"] is True
    assert context.bound.config.last_write.key == "automatic"


@given("an immutable managed configuration snapshot with nested values")
def given_immutable_snapshot(context) -> None:
    context.managed = MappingProxyType(
        {"runner": "argv", "nested": MappingProxyType({"targets": ("bdd",)})}
    )


@when("a dependent product converts it through the public plain-value helper")
def when_convert_plain(context) -> None:
    context.plain = to_plain_managed_value(context.managed)


@then("it receives independent ordinary dictionaries and lists")
def then_plain_containers(context) -> None:
    assert type(context.plain) is dict
    assert type(context.plain["nested"]) is dict
    assert type(context.plain["nested"]["targets"]) is list
    context.plain["nested"]["targets"].append("unit")
    assert context.managed["nested"]["targets"] == ("bdd",)


@then("supported scalar values retain their meaning")
def then_plain_scalars(context) -> None:
    assert context.plain["runner"] == "argv"


@given("an operation writes durable data and cache before failing")
def given_write_then_fail(context) -> None:
    def handler(invocation):
        invocation.data["durable"] = {"done": True}
        invocation.cache["disposable"] = "cached"
        raise RuntimeError("later failure")

    configured_system(context, handler)


@then("the result reports a failed handler and both committed writes")
def then_failed_with_writes(context) -> None:
    assert context.result.handler_status is HandlerStatus.FAILED
    assert len(context.result.writes) == 2
    assert all(
        item.kind is WriteDispositionKind.COMMITTED for item in context.result.writes
    )


@then("both current managed records remain readable")
def then_records_readable(context) -> None:
    assert context.bound.data["durable"] == {"done": True}
    assert context.bound.cache["disposable"] == "cached"


@given("an operation attempts parent traversal through durable data")
def given_traversal(context) -> None:
    def handler(invocation):
        invocation.data["../outside"] = "forbidden"

    configured_system(context, handler)


@then("the handler fails without creating content outside its extension root")
def then_traversal_rejected(context) -> None:
    assert context.result.handler_status is HandlerStatus.FAILED
    assert not (context.root / "state" / "extensions" / "outside.json").exists()


@then("unrelated lifecycle commands remain available")
def then_lifecycle_available(context) -> None:
    assert context.system.create_space("still-available").operation == "create_space"


@given("an operation can perform two managed assignments")
def given_batch_operation(context) -> None:
    def handler(invocation):
        mode = invocation.input["mode"]
        if mode == "ordinary":
            invocation.data["one"] = 1
        else:
            with invocation.batch() as batch:
                batch.data["two"] = 2
                batch.cache["three"] = 3

    configured_system(context, handler)
    bind(context)


@when("it performs an ordinary assignment")
def when_ordinary(context) -> None:
    context.bound.invoke("run", {"mode": "ordinary"})


@then("no staging or recovery journal is created")
def then_no_journal(context) -> None:
    assert not (context.root / "state" / "recovery").exists()


@when("it explicitly enters a successful bounded batch")
def when_batch(context) -> None:
    context.result = context.bound.invoke("run", {"mode": "batch"})


@then("both batched records are committed")
def then_batch_committed(context) -> None:
    assert context.bound.data["two"] == 2
    assert context.bound.cache["three"] == 3


@then("the batch claims no Git process network or arbitrary filesystem atomicity")
def then_batch_bounded(context) -> None:
    assert context.result.handler_status is HandlerStatus.COMPLETED
    assert not hasattr(context.bound, "git")


@given("a named operation returns an opaque non-JSON object")
def given_opaque_result(context) -> None:
    context.opaque = object()
    configured_system(context, lambda _invocation: context.opaque)


@then("the opaque value is returned separately")
def then_opaque_separate(context) -> None:
    assert context.result.value is context.opaque


@then("the inspectable outcome contains runtime metadata but not the opaque value")
def then_outcome_bounded(context) -> None:
    outcomes = context.system.inspect_extension_outcomes("zpp.behave")
    assert outcomes[0]["extension_id"] == "zpp.behave"
    assert "value" not in outcomes[0]


@given("a named operation inspects its invocation capabilities")
def given_inspecting_operation(context) -> None:
    def handler(invocation):
        return {
            "has_openlease": hasattr(invocation, "openlease"),
            "has_repository": hasattr(invocation, "repository"),
            "has_git": hasattr(invocation, "git"),
            "has_lifecycle": hasattr(invocation, "lifecycle"),
        }

    configured_system(context, handler)


@then("it receives only immutable context and managed mappings")
def then_narrow_capabilities(context) -> None:
    assert context.result.value == {
        "has_openlease": False,
        "has_repository": False,
        "has_git": False,
        "has_lifecycle": False,
    }


@then("cannot acquire leases mutate topology or perform Git integration through them")
def then_no_authority(context) -> None:
    assert context.system.snapshot().leases == ()
