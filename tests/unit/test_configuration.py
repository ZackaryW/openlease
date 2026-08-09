from pathlib import Path

import pytest

from openlease.core.configuration import (
    BoundSource,
    ConfigurationError,
    ConfigurationTarget,
    ExtensionRootPolicy,
    MemberLocation,
    RepositoryLocation,
    RootProvenance,
    SourceKind,
    bind_configuration_source,
    plan_configuration_sources,
    resolve_bound_source,
    resolve_extension_roots,
)
from openlease.core.state_codec import (
    AuthorityRecord,
    ConfigurationPackRecord,
    ConfigurationSourceRecord,
    DependencyRecord,
    OpenLeaseState,
    ParentRecord,
    RepositoryRecord,
    SpacePackAttachmentRecord,
    SpaceRecord,
)


def test_resolves_namespaced_roots_with_independent_provenance(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "openlease"
    product_root = tmp_path / ".zpp"
    explicit_cache = tmp_path / "fast-cache"

    roots = resolve_extension_roots(
        state_root,
        "zpp.traits",
        ExtensionRootPolicy(product_root=product_root, cache_root=explicit_cache),
    )

    namespace = product_root / "extensions" / "zpp.traits"
    assert roots.configuration.path == (namespace / "configuration").resolve()
    assert roots.configuration.provenance is RootProvenance.PRODUCT_ROOT
    assert roots.data.path == (namespace / "data").resolve()
    assert roots.data.provenance is RootProvenance.PRODUCT_ROOT
    assert roots.cache.path == explicit_cache.resolve()
    assert roots.cache.provenance is RootProvenance.EXPLICIT
    assert not product_root.exists()


def test_rebinds_a_repository_source_into_the_effective_checkout(
    tmp_path: Path,
) -> None:
    source_checkout = tmp_path / "repo"
    generated_checkout = tmp_path / "repo-olease-1"
    source = source_checkout / ".zpp" / "traits.md"
    effective = generated_checkout / ".zpp" / "traits.md"
    source.parent.mkdir(parents=True)
    effective.parent.mkdir(parents=True)
    source.write_text("source", encoding="utf-8")
    effective.write_text("generated", encoding="utf-8")

    binding = bind_configuration_source(
        source,
        (RepositoryLocation("repo-1", source_checkout),),
    )
    resolved = resolve_bound_source(
        binding,
        (MemberLocation("repo-1", generated_checkout),),
    )

    assert binding.kind is SourceKind.REPOSITORY
    assert binding.repository_id == "repo-1"
    assert binding.path == Path(".zpp/traits.md")
    assert resolved == effective.resolve()


def test_keeps_external_sources_exact_and_rejects_repository_traversal(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    external = tmp_path / "shared" / "traits.md"
    external.parent.mkdir()
    external.write_text("shared", encoding="utf-8")

    bound = bind_configuration_source(
        external, (RepositoryLocation("repo-1", repository),)
    )

    assert bound.kind is SourceKind.EXTERNAL
    assert bound.path == external.resolve()
    with pytest.raises(ConfigurationError, match="relative"):
        resolve_bound_source(
            BoundSource(SourceKind.REPOSITORY, Path("../traits.md"), "repo-1"),
            (MemberLocation("repo-1", repository),),
        )


def test_plans_configuration_in_scope_specificity_order(tmp_path: Path) -> None:
    def external(identifier: str, scope: str, scope_id: str | None, order: int = 0):
        return ConfigurationSourceRecord(
            identifier,
            "zpp",
            scope,
            scope_id,
            "external",
            str((tmp_path / f"{identifier}.md").resolve()),
            codec="json",
            layout="dedicated",
            order=order,
        )

    state = OpenLeaseState(
        repositories=(
            RepositoryRecord("repo-1", str(tmp_path / "repo")),
            RepositoryRecord("repo-3", str(tmp_path / "provider")),
        ),
        authorities=(
            AuthorityRecord("root", "repo-1", "openspec"),
            AuthorityRecord("child-a", "repo-1", "A/openspec"),
            AuthorityRecord("child-b", "repo-1", "B/openspec"),
            AuthorityRecord("provider", "repo-3", "openspec"),
        ),
        parents=(ParentRecord("child-a", "root"), ParentRecord("child-b", "root")),
        dependencies=(DependencyRecord("child-a", "provider", "read_only"),),
        spaces=(SpaceRecord("work", associated_repository_ids=("repo-1", "repo-3")),),
        configuration_packs=(
            ConfigurationPackRecord("first", "zpp"),
            ConfigurationPackRecord("second", "zpp"),
        ),
        space_pack_attachments=(
            SpacePackAttachmentRecord("work", "zpp", "second", 2),
            SpacePackAttachmentRecord("work", "zpp", "first", 1),
        ),
        configuration_sources=(
            external("child-b", "authority", "child-b"),
            external("repository", "repository", "repo-1"),
            external("space", "space", "work"),
            external("pack-second", "pack", "second"),
            external("root", "authority", "root"),
            external("machine", "machine", None),
            external("child-a", "authority", "child-a"),
            external("pack-first", "pack", "first"),
            external("provider", "authority", "provider"),
        ),
    )

    planned = plan_configuration_sources(
        state,
        "zpp",
        "work",
        ConfigurationTarget.authority("child-a"),
    )

    assert tuple(item.identifier for item in planned) == (
        "machine",
        "pack-first",
        "pack-second",
        "space",
        "repository",
        "root",
        "child-a",
    )
