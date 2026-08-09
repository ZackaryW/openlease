from __future__ import annotations

from behave import given, then, when

from features.support.openlease_support import capture
from openlease import (
    ExtensionManifest,
    ExtensionOperation,
    ExtensionRegistration,
    HandlerStatus,
    InvalidRequest,
    OpenLease,
    WriteDispositionKind,
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


@given("two current extensions declare named operations")
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


@then("no managed record is created")
def then_no_record(context) -> None:
    assert not (context.root / "state" / "extensions").exists()


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
