# ruff: noqa: E501
from __future__ import annotations

from pathlib import Path

from behave import given, then, when

from features.support.openlease_support import (
    capture,
    ensure_topology,
    git,
    space,
)
from openlease import (
    ConfigurationTarget,
    ExtensionManifest,
    ExtensionRegistration,
    InvalidRequest,
    OpenLease,
)


def registered_system(context, resolver=None) -> OpenLease:
    registration = ExtensionRegistration(ExtensionManifest("zpp", 1), resolver)
    system = OpenLease(
        context.root / "state",
        openspec=context.openspec,
        extensions=(registration,),
    )
    context.system = system
    return system


def document(context, name: str, content: str | None = None) -> Path:
    path = context.root / "configuration" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or name, encoding="utf-8")
    return path


def bind(
    context,
    identifier: str,
    scope_kind: str,
    scope_id: str | None = None,
    *,
    source: Path | None = None,
    order: int = 0,
) -> Path:
    path = source or document(context, identifier)
    context.system.bind_configuration_source(
        "zpp", identifier, path, scope_kind, scope_id, order=order
    )
    return path


def basic_context(context) -> None:
    registered_system(context)
    ensure_topology(context)
    space(context, "work")


@given(
    "a host explicitly registers a namespaced extension with a supported contract version"
)
def given_supported_registration(context) -> None:
    basic_context(context)


@when("the host requests that extension through OpenLease")
def when_request_registered_extension(context) -> None:
    context.result = context.system.resolve_extension_context(
        "zpp", "work", ConfigurationTarget.repository("repo-1")
    )


@then("OpenLease makes only that registered namespace available")
def then_only_registered_namespace(context) -> None:
    assert context.system.registered_extensions == ("zpp",)
    assert context.result.data.context.extension_id == "zpp"


@then("does not discover globally installed extension code")
def then_no_global_discovery(context) -> None:
    assert context.system.registered_extensions == ("zpp",)


@given("a host supplies duplicate extension identities")
def given_duplicate_extensions(context) -> None:
    manifest = ExtensionManifest("zpp", 1)
    context.registrations = (
        ExtensionRegistration(manifest),
        ExtensionRegistration(manifest),
    )


@given("a host supplies an unsupported contract version")
def given_unsupported_extension(context) -> None:
    context.registrations = (ExtensionRegistration(ExtensionManifest("zpp", 99)),)


@when("the host constructs OpenLease")
def when_construct_openlease(context) -> None:
    capture(
        context,
        lambda: OpenLease(
            context.root / "state",
            openspec=context.openspec,
            extensions=context.registrations,
        ),
    )


@then("OpenLease rejects the complete extension set")
def then_extension_set_rejected(context) -> None:
    assert isinstance(context.error, InvalidRequest)


@then("no extension context is resolved")
def then_no_extension_context(context) -> None:
    assert context.result is None


@given(
    "repo 1 has machine configuration, two ordered packs, direct space configuration, repository configuration, root authority configuration, and distinct child A and child B configuration"
)
def given_nested_configuration(context) -> None:
    basic_context(context)
    context.system.define_configuration_pack("zpp", "first")
    context.system.define_configuration_pack("zpp", "second")
    context.system.attach_configuration_pack("work", "zpp", "first", order=1)
    context.system.attach_configuration_pack("work", "zpp", "second", order=2)
    bind(context, "machine", "machine")
    bind(context, "pack-first", "pack", "first")
    bind(context, "pack-second", "pack", "second")
    bind(context, "space", "space", "work")
    bind(context, "repository", "repository", "repo-1")
    bind(context, "root", "authority", "root")
    bind(context, "child-a", "authority", "a")
    bind(context, "child-b", "authority", "b")


@given("one space targets child A")
def given_target_child_a(context) -> None:
    context.target = ConfigurationTarget.authority("a")


@when("the host requests child A context for its extension")
def when_resolve_child_a(context) -> None:
    context.result = context.system.resolve_extension_context(
        "zpp", "work", ConfigurationTarget.authority("a")
    )


@then(
    "the documents are ordered from machine through both packs, direct space, repository, root, and child A scopes"
)
def then_nested_order(context) -> None:
    assert tuple(item.identifier for item in context.result.data.context.documents) == (
        "machine",
        "pack-first",
        "pack-second",
        "space",
        "repository",
        "root",
        "child-a",
    )


@then("child B configuration is excluded")
def then_child_b_excluded(context) -> None:
    assert "child-b" not in {
        item.identifier for item in context.result.data.context.documents
    }


@then("OpenLease preserves each opaque document for extension-owned interpretation")
def then_documents_are_opaque(context) -> None:
    for item in context.result.data.context.documents:
        assert item.content == item.identifier.encode()
        assert item.source_kind.value == "external"
        assert item.repository_id is None


@given(
    "root, child A, and child B configuration scopes participate in one durable space"
)
def given_separate_config_scopes(context) -> None:
    basic_context(context)
    bind(context, "root", "authority", "root")
    bind(context, "child-a", "authority", "a")
    bind(context, "child-b", "authority", "b")
    context.before = context.system.snapshot()


@when(
    "the host attaches a reusable configuration pack and resolves each child separately"
)
def when_attach_pack_and_resolve_children(context) -> None:
    context.system.define_configuration_pack("zpp", "shared")
    bind(context, "pack", "pack", "shared")
    context.system.attach_configuration_pack("work", "zpp", "shared")
    context.a = context.system.resolve_extension_context(
        "zpp", "work", ConfigurationTarget.authority("a")
    )
    context.b = context.system.resolve_extension_context(
        "zpp", "work", ConfigurationTarget.authority("b")
    )


@then(
    "the pack participates between machine and repository configuration for both children"
)
def then_pack_in_both(context) -> None:
    assert "pack" in {item.identifier for item in context.a.data.context.documents}
    assert "pack" in {item.identifier for item in context.b.data.context.documents}


@then(
    "each resolved context identifies the participating pack and its observed generation"
)
def then_pack_generation(context) -> None:
    for result in (context.a, context.b):
        assert len(result.data.context.packs) == 1
        pack = result.data.context.packs[0]
        assert pack.identifier == "shared"
        assert pack.observed_generation


@then("no configuration scope or pack becomes a child space or leased authority")
def then_config_not_leased(context) -> None:
    state = context.system.snapshot()
    assert tuple(item.identifier for item in state.spaces) == ("work",)
    assert state.leases == ()


@then("the affected claim remains unchanged")
def then_claim_unchanged(context) -> None:
    before = next(item for item in context.before.spaces if item.identifier == "work")
    after = next(
        item for item in context.system.snapshot().spaces if item.identifier == "work"
    )
    assert after.affected_repository_ids == before.affected_repository_ids
    assert after.affected_authority_ids == before.affected_authority_ids


@given(
    "a successor space has one generated repository member and one pinned repository member"
)
def given_successor_with_generated_and_pinned(context) -> None:
    registered_system(context)
    ensure_topology(context)
    source = context.repos["repo-1"] / ".zpp" / "traits.md"
    source.parent.mkdir()
    source.write_text("source", encoding="utf-8")
    git(context.repos["repo-1"], "add", ".zpp/traits.md")
    git(context.repos["repo-1"], "commit", "--quiet", "-m", "config")
    space(context, "blocker", authorities=("a",))
    space(context, "request", authorities=("a",))
    context.system.lock("blocker")
    context.system.defer("request", "successor")
    context.system.bind_configuration_source(
        "zpp", "repo-source", source, "authority", "a"
    )
    context.target_space = "successor"


@when("the host requests an explicit repository or authority context")
def when_request_successor_context(context) -> None:
    context.result = context.system.resolve_extension_context(
        "zpp", context.target_space, ConfigurationTarget.authority("a")
    )


@then("generated authorities use their recorded effective worktree paths")
def then_generated_effective(context) -> None:
    member = next(
        item
        for item in context.result.data.context.members
        if item.repository_id == "repo-1"
    )
    assert member.generated
    assert "-olease-" in member.effective_path.name


@then("pinned authorities use their exact recorded context paths")
def then_pinned_exact(context) -> None:
    member = next(
        item
        for item in context.result.data.context.members
        if item.repository_id == "repo-2"
    )
    assert not member.generated
    assert member.effective_path == context.repos["repo-2"].resolve()


@then(
    "the result includes immutable relationship, access, branch, and commit provenance"
)
def then_context_provenance(context) -> None:
    resolved = context.result.data.context
    assert resolved.relationships
    assert all(item.starting_commit for item in resolved.members)
    assert all(item.access_role for item in resolved.members)
    try:
        resolved.space_id = "changed"
    except AttributeError, TypeError:
        pass
    else:
        raise AssertionError("extension context is mutable")


@given(
    "an extension source is appointed at a repository-relative path in a source checkout"
)
def given_repository_source(context) -> None:
    given_successor_with_generated_and_pinned(context)


@given("the selected successor records a generated worktree for that repository")
def given_successor_records_worktree(context) -> None:
    assert context.target_space == "successor"


@when("the host resolves extension context in the successor")
def when_resolve_successor(context) -> None:
    when_request_successor_context(context)


@then("OpenLease reads the same relative source beneath the effective worktree")
def then_source_rebound(context) -> None:
    item = context.result.data.context.documents[0]
    assert "-olease-" in item.resolved_path
    assert item.content == b"source"


@then("does not copy, adopt, rewrite, or lease the source")
def then_source_not_adopted(context) -> None:
    assert (context.repos["repo-1"] / ".zpp" / "traits.md").read_text() == "source"


@given("a readable extension source is appointed outside every registered repository")
def given_external_source(context) -> None:
    basic_context(context)
    context.external = bind(context, "external", "machine")


@when("the host resolves extension context")
def when_resolve_repository_context(context) -> None:
    context.result = context.system.resolve_extension_context(
        "zpp", "work", ConfigurationTarget.repository("repo-1")
    )


@then("OpenLease reads that exact canonical machine-local path")
def then_external_exact(context) -> None:
    assert Path(context.result.data.context.documents[0].resolved_path) == (
        context.external.resolve()
    )


@then("does not associate the path with a repository or lease")
def then_external_not_owned(context) -> None:
    source = context.system.snapshot().configuration_sources[0]
    assert source.repository_id is None
    assert context.system.snapshot().leases == ()


@given("a custom configuration source is missing or unreadable")
def given_missing_source(context) -> None:
    basic_context(context)
    context.missing = context.root / "missing.md"
    context.before = context.system.snapshot()


@when("the host appoints that source")
def when_bind_missing(context) -> None:
    capture(
        context,
        lambda: context.system.bind_configuration_source(
            "zpp", "missing", context.missing, "machine"
        ),
    )


@then("OpenLease rejects the complete binding")
def then_binding_rejected(context) -> None:
    assert isinstance(context.error, InvalidRequest)


@then("retains no partial configuration record")
def then_no_partial_binding(context) -> None:
    assert context.system.snapshot().configuration_sources == (
        context.before.configuration_sources
    )


@given("a locked space has resolved an attached configuration pack")
def given_locked_pack(context) -> None:
    registered_system(context)
    ensure_topology(context)
    space(context, "work", authorities=("a",))
    context.pack_path = document(context, "pack", "first")
    context.system.define_configuration_pack("zpp", "shared")
    bind(context, "pack", "pack", "shared", source=context.pack_path)
    context.system.attach_configuration_pack("work", "zpp", "shared")
    context.system.lock("work")
    context.first = context.system.resolve_extension_context(
        "zpp", "work", ConfigurationTarget.authority("a")
    )
    context.before = context.system.snapshot()


@when("the pack content changes and the host requests context again")
def when_pack_changes(context) -> None:
    context.pack_path.write_text("second-content", encoding="utf-8")
    context.second = context.system.resolve_extension_context(
        "zpp", "work", ConfigurationTarget.authority("a")
    )


@then(
    "OpenLease returns the current content with a changed observed generation and digest"
)
def then_live_content(context) -> None:
    first = context.first.data.context.documents[0]
    second = context.second.data.context.documents[0]
    assert second.content == b"second-content"
    assert second.content_digest != first.content_digest
    assert second.observed_generation != first.observed_generation


@then("does not require a refresh operation")
def then_no_refresh(context) -> None:
    assert context.second.operation == "resolve_extension_context"


@then(
    "leaves the lease, graph generation, affected claim, and worktree records unchanged"
)
def then_lifecycle_unchanged(context) -> None:
    after = context.system.snapshot()
    assert after.leases == context.before.leases
    assert after.graph_generation == context.before.graph_generation
    assert after.spaces == context.before.spaces


@given("a configuration source was resolved previously and is now unavailable")
def given_source_disappears(context) -> None:
    given_external_source(context)
    when_resolve_repository_context(context)
    context.external.unlink()


@when("the host requests extension context again")
def when_resolve_again(context) -> None:
    capture(
        context,
        lambda: context.system.resolve_extension_context(
            "zpp", "work", ConfigurationTarget.repository("repo-1")
        ),
    )


@then("OpenLease fails the request without returning cached source content")
def then_no_stale_context(context) -> None:
    assert isinstance(context.error, InvalidRequest)
    assert context.result is None


@then(
    "independent lock, release, recovery, and reconciliation operations remain available"
)
def then_lifecycle_available(context) -> None:
    assert context.system.snapshot().spaces


@given(
    "rebuilt ZPP appoints one `.zpp` product root for OpenLease state and extension storage"
)
def given_zpp_root(context) -> None:
    registered_system(context)
    context.product_root = context.root / ".zpp"
    context.system.set_extension_roots("zpp", product_root=context.product_root)


@when("OpenLease resolves the ZPP extension roots")
def when_resolve_roots(context) -> None:
    context.result = context.system.extension_roots("zpp")


@then(
    "configuration, data, and cache paths are separately namespaced beneath the appointed root"
)
def then_roots_namespaced(context) -> None:
    roots = context.result.data
    assert len({roots.configuration.path, roots.data.path, roots.cache.path}) == 3
    assert all(
        path.is_relative_to(context.product_root.resolve())
        for path in (roots.configuration.path, roots.data.path, roots.cache.path)
    )


@then(
    "each resolved path reports whether it was defaulted, product-root-derived, or explicitly overridden"
)
def then_root_provenance(context) -> None:
    roots = context.result.data
    assert roots.configuration.provenance.value == "product_root"
    assert roots.data.provenance.value == "product_root"
    assert roots.cache.provenance.value == "product_root"


@then("no pre-existing content is overwritten or treated as owned")
def then_roots_not_created(context) -> None:
    assert not context.product_root.exists()


@given(
    "a host appoints distinct configuration, data, and cache paths for one extension"
)
def given_independent_roots(context) -> None:
    registered_system(context)
    context.paths = tuple(context.root / name for name in ("cfg", "data", "cache"))
    context.system.set_extension_roots(
        "zpp",
        configuration_root=context.paths[0],
        data_root=context.paths[1],
        cache_root=context.paths[2],
    )


@when("OpenLease resolves that extension's storage")
def when_resolve_storage(context) -> None:
    when_resolve_roots(context)


@then("it returns each exact canonical path with its separate role and provenance")
def then_independent_roots(context) -> None:
    roots = context.result.data
    assert (roots.configuration.path, roots.data.path, roots.cache.path) == tuple(
        item.resolve() for item in context.paths
    )
    assert all(
        item.provenance.value == "explicit"
        for item in (roots.configuration, roots.data, roots.cache)
    )


@then("keeps other extension namespaces inaccessible")
def then_other_namespace_inaccessible(context) -> None:
    capture(context, lambda: context.system.extension_roots("other"))
    assert isinstance(context.error, InvalidRequest)


@given("repo 2 depends on an OpenSpec authority hosted by repo 3")
def given_repo_dependency(context) -> None:
    basic_context(context)


@given("both repositories have configuration for the same extension")
def given_dependency_configuration(context) -> None:
    bind(context, "consumer", "repository", "repo-2")
    bind(context, "provider", "authority", "shared")


@when("the host requests repo 2 context")
def when_resolve_consumer(context) -> None:
    context.consumer = context.system.resolve_extension_context(
        "zpp", "work", ConfigurationTarget.repository("repo-2")
    )


@then("the dependency relationship is reported")
def then_dependency_reported(context) -> None:
    assert any(
        item.kind == "dependency"
        and item.source_id == "repo-2"
        and item.target_id == "shared"
        for item in context.consumer.data.context.relationships
    )


@then("repo 3 configuration is excluded")
def then_provider_excluded(context) -> None:
    assert tuple(
        item.identifier for item in context.consumer.data.context.documents
    ) == ("consumer",)


@when("the host explicitly requests the repo 3 provider authority")
def when_resolve_provider(context) -> None:
    context.provider = context.system.resolve_extension_context(
        "zpp", "work", ConfigurationTarget.authority("shared")
    )


@then("OpenLease resolves repo 3 through its own scope chain")
def then_provider_resolved(context) -> None:
    assert tuple(
        item.identifier for item in context.provider.data.context.documents
    ) == ("provider",)


@given("a registered extension fails while interpreting an immutable context")
def given_failing_resolver(context) -> None:
    def fail(_context):
        raise RuntimeError("extension failed")

    registered_system(context, fail)
    ensure_topology(context)
    space(context, "work", authorities=("a",))
    context.before = context.system.snapshot()


@when("OpenLease reports the extension request failure")
def when_resolver_fails(context) -> None:
    capture(
        context,
        lambda: context.system.resolve_extension_context(
            "zpp", "work", ConfigurationTarget.authority("a")
        ),
    )


@then("the extension has not acquired or released leases")
def then_failure_no_leases(context) -> None:
    assert context.system.snapshot().leases == context.before.leases


@then(
    "has not changed topology, affected claims, worktree destinations, lifecycle state, or reconciliation state"
)
def then_failure_no_mutation(context) -> None:
    assert context.system.snapshot() == context.before


@then("the owner can continue independent lifecycle operations")
def then_owner_continues(context) -> None:
    assert context.system.lockable("work").data["lockable"]
