from __future__ import annotations

import json
import warnings

from behave import given, then, when
from typer.testing import CliRunner

from features.support.openlease_support import (
    capture,
    ensure_topology,
    repository,
    space,
)
from openlease import (
    ConfigurationConflict,
    ConfigurationDecodeFailed,
    ConfigurationLayout,
    ConfigurationPathChanged,
    ConfigurationReadOnly,
    ConfigurationTarget,
    ExtensionDocumentBinding,
    ExtensionManifest,
    ExtensionRegistration,
    InvalidRequest,
    OpenLease,
)
from openlease.cli import app
from openlease.core.state_codec import StateFormatError


def current_system(context, *identifiers: str) -> OpenLease:
    registrations = tuple(
        ExtensionRegistration(ExtensionManifest(identifier))
        for identifier in identifiers
    )
    context.system = OpenLease(
        context.root / "state",
        openspec=context.openspec,
        extensions=registrations,
    )
    return context.system


def direct_content(codec: str) -> str:
    if codec == "yaml":
        return "runner: argv\ntargets:\n  - bdd\n"
    if codec == "toml":
        return 'runner = "argv"\ntargets = ["bdd"]\n'
    return '{"runner": "argv", "targets": ["bdd"]}'


@given("a current extension and a dedicated {codec} document")
def given_dedicated_document(context, codec: str) -> None:
    current_system(context, "zpp.behave")
    context.codec = codec
    context.source = context.root / f"zpp.behave.{codec}"
    context.source.write_text(direct_content(codec), encoding="utf-8")
    context.before_state = context.system.snapshot()


@when("the host binds that direct document read-only")
def when_bind_read_only(context) -> None:
    context.bound = context.system.bind_extension_document(
        "zpp.behave",
        context.source,
        codec=context.codec,
        layout=ConfigurationLayout.DEDICATED,
    )


@then("the effective configuration contains the equivalent managed values")
def then_equivalent_values(context) -> None:
    assert context.bound.config["runner"] == "argv"
    assert context.bound.config["targets"] == ("bdd",)


@then("no persistent space or configuration binding is created")
def then_no_persistent_binding(context) -> None:
    assert context.system.snapshot() == context.before_state
    assert context.system.snapshot().configuration_sources == ()


@given("a shared TOML document with nested zpp and exact dotted zpp.behave tables")
def given_dotted_toml(context) -> None:
    current_system(context, "zpp.behave")
    context.source = context.root / "shared.toml"
    context.source.write_text(
        '# shared\n[zpp.behave]\nrunner = "nested"\n\n'
        '["zpp.behave"]\nrunner = "exact" # keep\n',
        encoding="utf-8",
    )
    context.bound = context.system.bind_extension_document(
        "zpp.behave", context.source, codec="toml", layout="shared", writable=True
    )


@when("zpp.behave updates its exact shared namespace")
def when_update_dotted(context) -> None:
    context.bound.config["runner"] = "updated"
    context.rendered = context.source.read_text(encoding="utf-8")


@then("the nested zpp table and comments remain unrelated")
def then_nested_unrelated(context) -> None:
    assert "nested" in context.rendered
    assert "# shared" in context.rendered
    assert "# keep" in context.rendered


@then("the dotted identity remains one quoted TOML key")
def then_quoted_identity(context) -> None:
    assert '["zpp.behave"]' in context.rendered
    assert context.bound.config["runner"] == "updated"


@given("current machine repository root and child configuration bindings")
def given_ordered_bindings(context) -> None:
    current_system(context, "extension")
    ensure_topology(context)
    space(context, "work", authorities=("a",))
    values = {
        "machine": {"nested": {"machine": 1}, "machine": True},
        "repository": {"nested": {"repository": 2}},
        "root": {"winner": "root"},
        "child-a": {"winner": "a"},
        "child-b": {"winner": "b"},
    }
    scopes = {
        "machine": ("machine", None),
        "repository": ("repository", "repo-1"),
        "root": ("authority", "root"),
        "child-a": ("authority", "a"),
        "child-b": ("authority", "b"),
    }
    for identifier, value in values.items():
        path = context.root / f"{identifier}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        scope_kind, scope_id = scopes[identifier]
        context.system.bind_configuration_source(
            "extension",
            identifier,
            path,
            scope_kind,
            scope_id,
            codec="json",
            layout="dedicated",
            writable=True,
        )


@when("the host binds child A configuration")
def when_bind_child_a(context) -> None:
    context.bound = context.system.bind_extension(
        "extension", "work", ConfigurationTarget.authority("a")
    )
    context.snapshot = context.bound.config.snapshot_record()


@then("later top-level keys replace earlier complete nested values")
def then_shallow_overlay(context) -> None:
    assert context.snapshot.values["nested"] == {"repository": 2}
    assert context.snapshot.values["winner"] == "a"


@then("child B configuration does not participate")
def then_no_sibling(context) -> None:
    assert "child-b" not in {item.identifier for item in context.snapshot.bindings}


@given("two writable sources for one space-scoped extension")
def given_two_writers(context) -> None:
    given_ordered_bindings(context)
    context.bound = context.system.bind_extension(
        "extension",
        "work",
        ConfigurationTarget.authority("a"),
        writable_source="root",
    )


@when("the host selects the lower source and assigns a shadowed key")
def when_write_shadowed(context) -> None:
    context.bound.config["winner"] = "changed-root"


@then("the lower source is published without a save call")
def then_lower_published(context) -> None:
    root = json.loads((context.root / "root.json").read_text(encoding="utf-8"))
    assert root["winner"] == "changed-root"


@then("the higher source remains the effective winner")
def then_higher_wins(context) -> None:
    assert context.bound.config["winner"] == "a"


@given("two extensions observe different namespaces in one writable JSON document")
def given_two_namespaces(context) -> None:
    current_system(context, "extension-a", "extension-b")
    context.source = context.root / "shared.json"
    context.source.write_text(
        '{"extension-a": {"key": 1}, "extension-b": {"key": 1}}',
        encoding="utf-8",
    )
    context.a = context.system.bind_extension_document(
        "extension-a", context.source, codec="json", layout="shared", writable=True
    )
    context.b = context.system.bind_extension_document(
        "extension-b", context.source, codec="json", layout="shared", writable=True
    )
    assert context.a.config["key"] == context.b.config["key"] == 1


@when("both extensions assign their own keys")
def when_both_assign(context) -> None:
    context.a.config["key"] = 2
    context.b.config["key"] = 3


@then("both completed namespaces remain in the shared document")
def then_both_remain(context) -> None:
    value = json.loads(context.source.read_text(encoding="utf-8"))
    assert value == {"extension-a": {"key": 2}, "extension-b": {"key": 3}}


@given("two handles observe the same writable configuration key")
def given_competing_handles(context) -> None:
    current_system(context, "extension")
    context.source = context.root / "config.json"
    context.source.write_text('{"key": "old"}', encoding="utf-8")
    options = dict(codec="json", layout="dedicated", writable=True)
    context.first = context.system.bind_extension_document(
        "extension", context.source, **options
    )
    context.second = context.system.bind_extension_document(
        "extension", context.source, **options
    )
    assert context.first.config["key"] == context.second.config["key"] == "old"


@given("two handles observe one writable configuration without the new key")
def given_competing_absent_handles(context) -> None:
    current_system(context, "extension")
    context.source = context.root / "config.json"
    context.source.write_text("{}", encoding="utf-8")
    options = dict(codec="json", layout="dedicated", writable=True)
    context.first = context.system.bind_extension_document(
        "extension", context.source, **options
    )
    context.second = context.system.bind_extension_document(
        "extension", context.source, **options
    )
    assert "key" not in context.first.config
    assert "key" not in context.second.config


@when("both handles assign different replacements")
def when_competing_assignments(context) -> None:
    context.first.config["key"] = "first"
    capture(context, lambda: context.second.config.__setitem__("key", "second"))


@then("the second assignment reports configuration_conflict")
def then_conflict(context) -> None:
    assert isinstance(context.error, ConfigurationConflict)
    assert context.error.code == "configuration_conflict"


@then("the first replacement remains authoritative")
def then_first_remains(context) -> None:
    assert json.loads(context.source.read_text(encoding="utf-8"))["key"] == "first"


@given("a writable document is bound before its path becomes an escaping symlink")
def given_replaced_symlink_binding(context) -> None:
    current_system(context, "extension")
    context.source = context.root / "config.json"
    context.external = context.root / "external.json"
    context.source.write_text('{"key": "bound"}', encoding="utf-8")
    context.external.write_text('{"key": "bound"}', encoding="utf-8")
    context.bound = context.system.bind_extension_document(
        "extension",
        context.source,
        codec="json",
        layout="dedicated",
        writable=True,
    )
    context.source.unlink()
    try:
        context.source.symlink_to(context.external)
    except OSError as error:
        context.scenario.skip(f"file symbolic links are unavailable: {error}")


@when("the caller assigns through the replaced binding")
def when_assigning_through_replaced_binding(context) -> None:
    capture(context, lambda: context.bound.config.__setitem__("key", "escaped"))


@then("the configuration mutation reports configuration_path_changed")
def then_path_change_reported(context) -> None:
    assert isinstance(context.error, ConfigurationPathChanged)
    assert context.error.code == "configuration_path_changed"


@then("the symlink and its external target remain unchanged")
def then_symlink_target_unchanged(context) -> None:
    assert context.source.is_symlink()
    assert json.loads(context.external.read_text(encoding="utf-8")) == {"key": "bound"}


@given("a direct read-only configuration document")
def given_read_only_direct(context) -> None:
    current_system(context, "extension")
    context.source = context.root / "read-only.json"
    context.source.write_text('{"key": "value"}', encoding="utf-8")
    context.before = context.source.read_bytes()
    context.bound = context.system.bind_extension_document(
        "extension", context.source, codec="json", layout="dedicated"
    )


@when("the caller explicitly sets a configuration key")
def when_set_read_only(context) -> None:
    capture(context, lambda: context.bound.config.set("key", "changed"))


@then("the mutation reports configuration_read_only")
def then_read_only_code(context) -> None:
    assert isinstance(context.error, ConfigurationReadOnly)
    assert context.error.code == "configuration_read_only"


@given("an invalid explicitly declared configuration document")
def given_invalid_cli_document(context) -> None:
    context.cli = CliRunner()
    context.cli_state = context.root / "cli-state"
    context.cli_repo = repository(context.root / "cli-repo")
    context.source = context.root / "invalid.json"
    context.source.write_text("not-json", encoding="utf-8")


@when("the host binds it through the JSON CLI")
def when_bind_invalid_cli(context) -> None:
    for command in (
        ("register", "repository", "repo", str(context.cli_repo)),
        ("space", "create", "work"),
        ("associate", "repo", "--space", "work"),
    ):
        completed = context.cli.invoke(
            app, ["--state-root", str(context.cli_state), *command]
        )
        assert completed.exit_code == 0, completed.output
    context.cli_result = context.cli.invoke(
        app,
        [
            "--state-root",
            str(context.cli_state),
            "--json",
            "config",
            "bind",
            "zpp",
            "machine",
            str(context.source),
            "--scope",
            "machine",
            "--codec",
            "json",
            "--layout",
            "dedicated",
        ],
    )


@then("the CLI reports configuration_decode_failed with an invalid_request outcome")
def then_cli_decode_code(context) -> None:
    envelope = json.loads(context.cli_result.stderr)
    assert envelope["code"] == ConfigurationDecodeFailed.code
    assert envelope["outcome"] == "invalid_request"


@then("exits with status 2")
def then_cli_status_two(context) -> None:
    assert context.cli_result.exit_code == 2


@given("a direct dedicated document contains a nested mapping")
def given_nested_direct(context) -> None:
    current_system(context, "extension")
    context.source = context.root / "config.json"
    context.source.write_text('{"nested": {"key": "value"}}', encoding="utf-8")
    context.bound = context.system.bind_extension_document(
        "extension", context.source, codec="json", layout="dedicated"
    )
    context.before = context.source.read_bytes()


@when("a caller attempts in-place mutation of the returned nested value")
def when_nested_mutation(context) -> None:
    capture(
        context,
        lambda: context.bound.config["nested"].__setitem__("key", "changed"),
    )


@then("the value is immutable")
def then_immutable(context) -> None:
    assert isinstance(context.error, (TypeError, AttributeError))


@then("the source document remains unchanged")
def then_source_unchanged(context) -> None:
    assert context.source.read_bytes() == context.before


@given("a current extension and an absent dedicated YAML path")
def given_absent_path(context) -> None:
    current_system(context, "extension")
    context.source = context.root / "new.yaml"


@when("the host explicitly initializes that writable document")
def when_initialize(context) -> None:
    context.bound = context.system.initialize_extension_document(
        "extension",
        context.source,
        codec="yaml",
        layout="dedicated",
        initial={"key": "value"},
    )


@then("exactly that document is created with the initial mapping")
def then_initialized(context) -> None:
    assert context.source.is_file()
    assert context.bound.config["key"] == "value"


@then("a repeated initialization does not truncate it")
def then_no_truncate(context) -> None:
    before = context.source.read_bytes()
    capture(
        context,
        lambda: context.system.initialize_extension_document(
            "extension",
            context.source,
            codec="yaml",
            layout="dedicated",
            initial={},
        ),
    )
    assert isinstance(context.error, InvalidRequest)
    assert context.source.read_bytes() == before


@given("an explicit binding value with codec layout path and write authority")
def given_explicit_binding_value(context) -> None:
    current_system(context, "extension")
    context.existing = context.root / "existing.yaml"
    context.created = context.root / "created.yaml"
    context.existing.write_text("key: existing\n", encoding="utf-8")
    context.open_binding = ExtensionDocumentBinding(
        "extension",
        context.existing,
        "yaml",
        ConfigurationLayout.DEDICATED,
        False,
    )
    context.initialize_binding = ExtensionDocumentBinding(
        "extension",
        context.created,
        "yaml",
        ConfigurationLayout.DEDICATED,
        True,
    )


@when("the host opens and initializes documents through that binding shape")
def when_use_binding_values(context) -> None:
    context.opened = context.system.bind_extension_document(context.open_binding)
    context.initialized = context.system.initialize_extension_document(
        context.initialize_binding,
        initial={"key": "created"},
        boundary=context.root,
    )


@then("both operations preserve the declared binding metadata")
def then_binding_metadata(context) -> None:
    opened = context.opened.config.snapshot_record().bindings[0]
    initialized = context.initialized.config.snapshot_record().bindings[0]
    assert opened.canonical_path == context.existing.resolve()
    assert initialized.canonical_path == context.created.resolve()
    assert opened.writable is False
    assert initialized.writable is True


@then("neither codec nor layout is inferred")
def then_no_binding_inference(context) -> None:
    for bound in (context.opened, context.initialized):
        binding = bound.config.snapshot_record().bindings[0]
        assert binding.codec == "yaml"
        assert binding.layout is ConfigurationLayout.DEDICATED


@given("equivalent object and scalar direct-document bindings")
def given_equivalent_binding_forms(context) -> None:
    current_system(context, "extension")
    context.source = context.root / "equivalent.json"
    context.source.write_text('{"key": "value"}', encoding="utf-8")
    context.binding = ExtensionDocumentBinding(
        "extension",
        context.source,
        "json",
        ConfigurationLayout.DEDICATED,
    )


@when("the host opens each existing document")
def when_open_both_forms(context) -> None:
    context.object_bound = context.system.bind_extension_document(context.binding)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        context.scalar_bound = context.system.bind_extension_document(
            "extension",
            context.source,
            codec="json",
            layout=ConfigurationLayout.DEDICATED,
        )
    context.binding_warnings = tuple(caught)


@then("both forms produce the same configuration and provenance")
def then_binding_forms_match(context) -> None:
    assert (
        context.object_bound.config.snapshot() == context.scalar_bound.config.snapshot()
    )
    assert context.object_bound.config.snapshot_record().bindings == (
        context.scalar_bound.config.snapshot_record().bindings
    )


@then("the scalar form is not deprecated")
def then_scalar_not_deprecated(context) -> None:
    assert not any(
        issubclass(item.category, DeprecationWarning)
        for item in context.binding_warnings
    )


@given("a prior-schema state references an authored YAML document")
def given_prior_state(context) -> None:
    context.authored = context.root / "authored.yaml"
    context.authored.write_text("key: value\n", encoding="utf-8")
    state_root = context.root / "state"
    state_root.mkdir(exist_ok=True)
    context.old_state = (
        '{"schema_version":2,"generation":0,"configuration_sources":['
        f'{{"path":{json.dumps(str(context.authored))}}}]}}\n'
    ).encode()
    (state_root / "state.json").write_bytes(context.old_state)
    context.before = context.authored.read_bytes()
    context.system = OpenLease(state_root)


@when("current OpenLease opens that state")
def when_open_prior(context) -> None:
    capture(context, context.system.snapshot)


@then("it requests reinitialization without a compatibility decoder")
def then_reinitialize(context) -> None:
    assert isinstance(context.error, StateFormatError)
    assert "reinitialize" in str(context.error)


@then("the authored YAML document is unchanged")
def then_authored_unchanged(context) -> None:
    assert context.authored.read_bytes() == context.before


@given("a current extension uses a custom product root")
def given_product_root(context) -> None:
    current_system(context, "zpp.traits")
    context.product_root = context.root / ".zpp"
    context.system.set_extension_roots("zpp.traits", product_root=context.product_root)


@when("OpenLease resolves its extension storage")
def when_resolve_roots(context) -> None:
    context.roots = context.system.extension_roots("zpp.traits").data


@then("configuration data and cache roots are separately namespaced beneath it")
def then_namespaced_roots(context) -> None:
    paths = {
        context.roots.configuration.path,
        context.roots.data.path,
        context.roots.cache.path,
    }
    assert len(paths) == 3
    assert all(path.is_relative_to(context.product_root.resolve()) for path in paths)


@then("no ZPP-specific home resolver is required")
def then_no_zpp_resolver(context) -> None:
    assert "zpp" not in type(context.system).__module__
