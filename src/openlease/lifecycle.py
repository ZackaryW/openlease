from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from openlease.core.graph import (
    AccessRole,
    AffectedClaim,
    AuthorityGraph,
    Dependency,
    GraphError,
    Lease,
    ParentRelationship,
    audit_authority_boundaries,
    conflicting_leases,
    resolve_affected_claim,
    validate_graph,
)
from openlease.core.preparation import PreparationMember, plan_preparation
from openlease.core.reconciliation import (
    ReconciliationLeg,
    ReconciliationMember,
    dependency_order,
    plan_reconciliation,
)
from openlease.core.state_codec import (
    AuthorityRecord,
    DependencyRecord,
    LeaseRecord,
    OpenLeaseState,
    ParentRecord,
    PreparedArtifactRecord,
    ReconciliationRecord,
    RepositoryRecord,
    SpaceMemberRecord,
    SpaceRecord,
)
from openlease.errors import (
    AuthorityConflict,
    InvalidRequest,
    OwnershipConflict,
    PreparationFailed,
)
from openlease.result import CommandResult
from openlease.utils.git_adapter import (
    GitAdapter,
    IntegrationStrategy,
    MergeLeg,
    WorktreeRequest,
)
from openlease.utils.openspec_adapter import OpenSpecAdapter
from openlease.utils.ownership import (
    ProjectionOwnership,
    inspect_projection,
    projection_fingerprint,
)
from openlease.utils.state_repository import StaleStateError, StateRepository


@dataclass(frozen=True, slots=True)
class BranchSelection:
    mode: Literal["new", "local", "remote"] = "new"
    ref: str | None = None
    local_name: str | None = None


@dataclass(frozen=True, slots=True)
class ReconcileSelection:
    repository_id: str
    destination_ref: str
    strategy: IntegrationStrategy
    destination_path: Path | None = None


class OpenLease:
    """Library-first owner of one machine-local relational lease state."""

    def __init__(
        self,
        state_root: Path,
        *,
        worktree_base: Path | None = None,
        git: GitAdapter | None = None,
        openspec: OpenSpecAdapter | None = None,
        verifier: Callable[[str, tuple[Path, ...]], None] | None = None,
    ) -> None:
        self.state_root = state_root.resolve()
        self.worktree_base = (
            worktree_base.resolve()
            if worktree_base is not None
            else (self.state_root / "worktrees").resolve()
        )
        self.repository = StateRepository(self.state_root)
        self.git = git or GitAdapter()
        self.openspec = openspec or OpenSpecAdapter()
        self.verifier = verifier or self._verify_clean_checkouts

    def snapshot(self) -> OpenLeaseState:
        return self.repository.load()

    def register_repository(self, identifier: str, path: Path) -> CommandResult:
        checkout = self.git.inspect(path)

        def transform(state: OpenLeaseState) -> OpenLeaseState:
            self._ensure_graph_mutable(state)
            if self._repository(state, identifier, required=False) is not None:
                raise InvalidRequest(f"repository already registered: {identifier}")
            record = RepositoryRecord(
                identifier, str(checkout.root), str(checkout.common_dir)
            )
            return replace(
                state,
                repositories=(*state.repositories, record),
                graph_generation=state.graph_generation + 1,
            )

        updated = self._mutate(transform)
        return CommandResult(
            "register_repository", data=self._repository(updated, identifier)
        )

    def register_authority(
        self,
        identifier: str,
        repository_id: str,
        relative_path: str = "openspec",
        *,
        store_id: str | None = None,
    ) -> CommandResult:
        normalized = Path(relative_path).as_posix().strip("/")
        if (
            not normalized
            or Path(normalized).is_absolute()
            or ".." in Path(normalized).parts
        ):
            raise InvalidRequest("authority path must be repository-relative")

        def transform(state: OpenLeaseState) -> OpenLeaseState:
            self._ensure_graph_mutable(state)
            self._repository(state, repository_id)
            if self._authority(state, identifier, required=False) is not None:
                raise InvalidRequest(f"authority already registered: {identifier}")
            record = AuthorityRecord(identifier, repository_id, normalized, store_id)
            candidate = replace(
                state,
                authorities=(*state.authorities, record),
                graph_generation=state.graph_generation + 1,
            )
            self._validated_graph(candidate)
            return candidate

        updated = self._mutate(transform)
        return CommandResult(
            "register_authority", data=self._authority(updated, identifier)
        )

    def relate_parent(self, child_id: str, parent_id: str) -> CommandResult:
        def transform(state: OpenLeaseState) -> OpenLeaseState:
            self._ensure_graph_mutable(state)
            record = ParentRecord(child_id, parent_id)
            if record in state.parents:
                return state
            candidate = replace(
                state,
                parents=(*state.parents, record),
                graph_generation=state.graph_generation + 1,
            )
            self._validated_graph(candidate)
            return candidate

        before = self.snapshot()
        updated = self._mutate_graph_error(transform)
        return CommandResult(
            "relate_parent",
            changed=updated.graph_generation != before.graph_generation,
            data={"child": child_id, "parent": parent_id},
        )

    def relate_dependency(
        self,
        consumer_id: str,
        authority_id: str,
        access: AccessRole = AccessRole.WRITABLE,
    ) -> CommandResult:
        def transform(state: OpenLeaseState) -> OpenLeaseState:
            self._ensure_graph_mutable(state)
            record = DependencyRecord(consumer_id, authority_id, access.value)
            if record in state.dependencies:
                return state
            candidate = replace(
                state,
                dependencies=(*state.dependencies, record),
                graph_generation=state.graph_generation + 1,
            )
            self._validated_graph(candidate)
            return candidate

        before = self.snapshot()
        updated = self._mutate_graph_error(transform)
        return CommandResult(
            "relate_dependency",
            changed=updated.graph_generation != before.graph_generation,
            data={
                "consumer": consumer_id,
                "authority": authority_id,
                "access": access.value,
            },
        )

    def create_space(self, identifier: str) -> CommandResult:
        def transform(state: OpenLeaseState) -> OpenLeaseState:
            if self._space(state, identifier, required=False) is not None:
                raise InvalidRequest(f"space already exists: {identifier}")
            return replace(state, spaces=(*state.spaces, SpaceRecord(identifier)))

        updated = self._mutate(transform)
        return CommandResult("create_space", data=self._space(updated, identifier))

    def select_space(self, identifier: str) -> CommandResult:
        state = self.snapshot()
        self._space(state, identifier)
        return CommandResult(
            "select_space",
            changed=False,
            data={"space": identifier, "environment": {"OPENLEASE_SPACE": identifier}},
        )

    def close_session(self, identifier: str) -> CommandResult:
        state = self.snapshot()
        self._space(state, identifier)
        return CommandResult(
            "close_session",
            changed=False,
            data={"space": identifier, "unset_environment": "OPENLEASE_SPACE"},
        )

    def associate(
        self,
        space_id: str,
        repository_ids: tuple[str, ...],
        *,
        expected_generation: int | None = None,
    ) -> CommandResult:
        def transform(state: OpenLeaseState) -> OpenLeaseState:
            space = self._editable_space(state, space_id)
            for repository_id in repository_ids:
                self._repository(state, repository_id)
            associated = tuple(
                dict.fromkeys(space.associated_repository_ids + repository_ids)
            )
            return self._replace_space(
                state, replace(space, associated_repository_ids=associated)
            )

        updated = self._mutate(transform, expected_generation=expected_generation)
        return CommandResult("associate", data=self._space(updated, space_id))

    def set_affected(
        self,
        space_id: str,
        *,
        repository_ids: tuple[str, ...] = (),
        authority_ids: tuple[str, ...] = (),
    ) -> CommandResult:
        def transform(state: OpenLeaseState) -> OpenLeaseState:
            space = self._editable_space(state, space_id)
            for repository_id in repository_ids:
                self._repository(state, repository_id)
            for authority_id in authority_ids:
                self._authority(state, authority_id)
            return self._replace_space(
                state,
                replace(
                    space,
                    affected_repository_ids=tuple(dict.fromkeys(repository_ids)),
                    affected_authority_ids=tuple(dict.fromkeys(authority_ids)),
                ),
            )

        updated = self._mutate(transform)
        return CommandResult("set_affected", data=self._space(updated, space_id))

    def affect_add(
        self,
        space_id: str,
        *,
        repository_ids: tuple[str, ...] = (),
        authority_ids: tuple[str, ...] = (),
    ) -> CommandResult:
        state = self.snapshot()
        space = self._space(state, space_id)
        return self.set_affected(
            space_id,
            repository_ids=tuple(
                dict.fromkeys(space.affected_repository_ids + repository_ids)
            ),
            authority_ids=tuple(
                dict.fromkeys(space.affected_authority_ids + authority_ids)
            ),
        )

    def affect_remove(
        self,
        space_id: str,
        *,
        repository_ids: tuple[str, ...] = (),
        authority_ids: tuple[str, ...] = (),
    ) -> CommandResult:
        state = self.snapshot()
        space = self._space(state, space_id)
        return self.set_affected(
            space_id,
            repository_ids=tuple(
                item
                for item in space.affected_repository_ids
                if item not in repository_ids
            ),
            authority_ids=tuple(
                item
                for item in space.affected_authority_ids
                if item not in authority_ids
            ),
        )

    def plan(self, space_id: str) -> CommandResult:
        state = self.snapshot()
        space = self._space(state, space_id)
        plan = self._affected_plan(state, space)
        return CommandResult("plan", changed=False, data=plan)

    def lockable(self, space_id: str) -> CommandResult:
        state = self.snapshot()
        space = self._space(state, space_id)
        plan = self._affected_plan(state, space)
        conflicts = self._conflicts(state, space_id, plan)
        blockers = tuple(sorted({item.owner_id for item in conflicts}))
        promotion = self._promotion_issues(state, space)
        return CommandResult(
            "lockable",
            changed=False,
            data={
                "lockable": not conflicts and not promotion,
                "plan": plan,
                "conflicts": conflicts,
                "blockers": blockers,
                "promotion_issues": promotion,
            },
        )

    def lock(self, space_id: str) -> CommandResult:
        for _attempt in range(4):
            state = self.snapshot()
            space = self._space(state, space_id)
            plan = self._affected_plan(state, space)
            if (
                space.status == "locked"
                and space.held_authority_ids == plan.held_authorities
            ):
                return CommandResult(
                    "lock", outcome="compatible_noop", changed=False, data=space
                )
            conflicts = self._conflicts(state, space_id, plan)
            if conflicts:
                raise AuthorityConflict(
                    "affected authority closure is not lockable", details=conflicts
                )
            issues = self._promotion_issues(state, space)
            if issues:
                raise InvalidRequest(
                    "deferred successor is not promotable", details=issues
                )
            members = space.members or self._canonical_members(state, space, plan)

            def transform(
                current: OpenLeaseState,
                locked_members: tuple[SpaceMemberRecord, ...] = members,
            ) -> OpenLeaseState:
                current_space = self._space(current, space_id)
                current_plan = self._affected_plan(current, current_space)
                current_conflicts = self._conflicts(current, space_id, current_plan)
                if current_conflicts:
                    raise AuthorityConflict(
                        "affected authority closure is not lockable",
                        details=current_conflicts,
                    )
                leases = tuple(
                    item for item in current.leases if item.owner_id != space_id
                ) + tuple(
                    LeaseRecord(authority_id, space_id)
                    for authority_id in current_plan.held_authorities
                )
                locked = replace(
                    current_space,
                    status="locked",
                    held_authority_ids=current_plan.held_authorities,
                    members=locked_members,
                    graph_generation=current.graph_generation,
                )
                return self._replace_space(current, locked, leases=leases)

            try:
                updated = self.repository.mutate(state.generation, transform)
            except StaleStateError:
                continue
            return CommandResult("lock", data=self._space(updated, space_id))
        raise InvalidRequest("state changed repeatedly during lock")

    def open(self, space_id: str, *, tool: str | None = None) -> CommandResult:
        state = self.snapshot()
        space = self._space(state, space_id)
        members = self._projection_members(state, space)
        name = space.projection_name or f"openlease-{space.identifier}"
        expected = (
            ProjectionOwnership(
                name,
                members,
                space.projection_fingerprint or "",
                state.generation,
            )
            if space.projection_name is not None
            else None
        )
        actual = next(
            (item for item in self.openspec.list_worksets() if item.name == name), None
        )
        inspection = inspect_projection(expected, actual)
        if inspection.state in {"conflict", "unmanaged"}:
            raise OwnershipConflict(
                f"OpenSpec projection is not safely owned: {name}",
                details=inspection,
            )
        changed = inspection.state == "absent"
        if changed:
            self.openspec.create_workset(name, members)
        fingerprint = projection_fingerprint(name, members)

        def transform(current: OpenLeaseState) -> OpenLeaseState:
            current_space = self._space(current, space_id)
            return self._replace_space(
                current,
                replace(
                    current_space,
                    projection_name=name,
                    projection_fingerprint=fingerprint,
                ),
            )

        updated = self.repository.mutate(state.generation, transform)
        self.openspec.open_workset(name, tool)
        return CommandResult(
            "open", changed=changed, data=self._space(updated, space_id)
        )

    def defer(
        self,
        space_id: str,
        successor_name: str,
        *,
        branches: dict[str, BranchSelection] | None = None,
    ) -> CommandResult:
        return self._prepare_successor(
            space_id, successor_name, branches or {}, acquire=False
        )

    def isolate(
        self,
        space_id: str,
        successor_name: str,
        *,
        branches: dict[str, BranchSelection] | None = None,
    ) -> CommandResult:
        return self._prepare_successor(
            space_id, successor_name, branches or {}, acquire=True
        )

    def release(self, space_id: str) -> CommandResult:
        state = self.snapshot()
        space = self._space(state, space_id)
        self._assert_boundary_safe(state, space)
        self._remove_owned_projection(state, space)
        records = tuple(
            ReconciliationRecord(space_id, member.repository_id)
            for member in space.members
            if member.generated
        )

        def transform(current: OpenLeaseState) -> OpenLeaseState:
            current_space = self._space(current, space_id)
            released = replace(
                current_space,
                status="released",
                held_authority_ids=(),
                projection_name=None,
                projection_fingerprint=None,
            )
            reconciliations = (
                tuple(
                    item
                    for item in current.reconciliations
                    if item.space_id != space_id
                )
                + records
            )
            return self._replace_space(
                current,
                released,
                leases=tuple(
                    item for item in current.leases if item.owner_id != space_id
                ),
                reconciliations=reconciliations,
            )

        updated = self.repository.mutate(state.generation, transform)
        return CommandResult("release", data=self._space(updated, space_id))

    def set_handoff_disposition(
        self,
        space_id: str,
        disposition: Literal["integrated", "abandoned", "superseded"],
    ) -> CommandResult:
        def transform(state: OpenLeaseState) -> OpenLeaseState:
            space = self._space(state, space_id)
            if space.status not in {"released", "finalized"}:
                raise InvalidRequest("blocker must be released before disposition")
            return self._replace_space(
                state, replace(space, handoff_disposition=disposition)
            )

        updated = self._mutate(transform)
        return CommandResult(
            "set_handoff_disposition", data=self._space(updated, space_id)
        )

    def reconcile_plan(
        self, space_id: str, selections: tuple[ReconcileSelection, ...]
    ) -> CommandResult:
        state = self.snapshot()
        space = self._space(state, space_id)
        self._assert_boundary_safe(state, space)
        generated = tuple(member for member in space.members if member.generated)
        plan_reconciliation(
            tuple(
                ReconciliationMember(member.repository_id, member.branch or "")
                for member in generated
            ),
            tuple(
                ReconciliationLeg(
                    selection.repository_id,
                    selection.destination_ref,
                    selection.strategy,
                )
                for selection in selections
            ),
        )
        selection_by_repo = {item.repository_id: item for item in selections}
        repository_dependencies = self._repository_dependencies(state)
        default_order = dependency_order(
            tuple(member.repository_id for member in generated),
            repository_dependencies,
        )
        previews = []
        for member in generated:
            selection = selection_by_repo[member.repository_id]
            destination_path = selection.destination_path or Path(member.source_path)
            leg = MergeLeg(
                destination_path,
                member.branch or "",
                selection.destination_ref,
                selection.strategy,
                source_checkout=Path(member.effective_path),
            )
            checkout = self.git.inspect(destination_path)
            previews.append(
                {
                    "repository_id": member.repository_id,
                    "dirty": checkout.dirty,
                    "preview": self.git.preview_integration(leg),
                    "destination_path": destination_path,
                    "strategy": selection.strategy,
                }
            )
        return CommandResult(
            "reconcile_plan",
            changed=False,
            data={
                "default_order": default_order,
                "legs": tuple(previews),
                "verification": {
                    "repository": "configured verifier after each completed leg",
                    "cohort": "configured verifier after every selected leg",
                },
            },
        )

    def reconcile_apply(
        self, space_id: str, selections: tuple[ReconcileSelection, ...]
    ) -> CommandResult:
        plan = self.reconcile_plan(space_id, selections)
        state = self.snapshot()
        space = self._space(state, space_id)
        members = {item.repository_id: item for item in space.members if item.generated}
        selection_by_repo = {item.repository_id: item for item in selections}
        completed: list[str] = []
        for repository_id in plan.data["default_order"]:  # type: ignore[index]
            member = members[repository_id]
            selection = selection_by_repo[repository_id]
            destination_path = selection.destination_path or Path(member.source_path)
            preview = self.git.preview_integration(
                MergeLeg(
                    destination_path,
                    member.branch or "",
                    selection.destination_ref,
                    selection.strategy,
                    source_checkout=Path(member.effective_path),
                )
            )
            try:
                result = self.git.apply_integration(
                    MergeLeg(
                        destination_path,
                        member.branch or "",
                        selection.destination_ref,
                        selection.strategy,
                        source_checkout=Path(member.effective_path),
                        expected_destination_commit=preview.destination_commit,
                    )
                )
            except Exception as error:
                raise InvalidRequest(
                    f"reconciliation stopped at {repository_id}",
                    details={
                        "completed": tuple(completed),
                        "conflicted": repository_id,
                        "remaining": tuple(
                            item
                            for item in plan.data["default_order"]  # type: ignore[index]
                            if item not in completed and item != repository_id
                        ),
                    },
                ) from error
            self.verifier(repository_id, (destination_path,))

            def transform(
                current: OpenLeaseState,
                current_repository_id: str = repository_id,
                current_selection: ReconcileSelection = selection,
                current_destination_commit: str = preview.destination_commit,
                current_result_commit: str = result.head,
            ) -> OpenLeaseState:
                records = tuple(
                    replace(
                        item,
                        destination_ref=current_selection.destination_ref,
                        destination_commit=current_destination_commit,
                        strategy=current_selection.strategy.value,
                        status="reconciled",
                        result_commit=current_result_commit,
                    )
                    if item.space_id == space_id
                    and item.repository_id == current_repository_id
                    else item
                    for item in current.reconciliations
                )
                return replace(current, reconciliations=records)

            current = self.snapshot()
            self.repository.mutate(current.generation, transform)
            completed.append(repository_id)
        destination_paths = tuple(
            selection_by_repo[repository_id].destination_path
            or Path(members[repository_id].source_path)
            for repository_id in completed
        )
        self.verifier("cohort", destination_paths)
        return CommandResult("reconcile_apply", data={"completed": completed})

    def abandon_member(self, space_id: str, repository_id: str) -> CommandResult:
        def transform(state: OpenLeaseState) -> OpenLeaseState:
            found = False
            records = []
            for item in state.reconciliations:
                if item.space_id == space_id and item.repository_id == repository_id:
                    item = replace(item, status="abandoned")
                    found = True
                records.append(item)
            if not found:
                raise InvalidRequest("reconciliation member not found")
            return replace(state, reconciliations=tuple(records))

        updated = self._mutate(transform)
        return CommandResult("abandon_member", data=updated.reconciliations)

    def cleanup_worktree(self, space_id: str, repository_id: str) -> CommandResult:
        state = self.snapshot()
        space = self._space(state, space_id)
        member = next(
            (
                item
                for item in space.members
                if item.repository_id == repository_id and item.generated
            ),
            None,
        )
        if member is None:
            raise InvalidRequest("generated member not found")
        checkout = self.git.inspect(Path(member.effective_path))
        if checkout.dirty:
            raise InvalidRequest("generated worktree is dirty")
        source = self.git.inspect(Path(member.source_path))
        self.git.remove_worktree(source, Path(member.effective_path))
        return CommandResult(
            "cleanup_worktree",
            data={"repository_id": repository_id, "branch_preserved": member.branch},
        )

    def rollback_preparation(self, space_id: str) -> CommandResult:
        state = self.snapshot()
        space = self._space(state, space_id)
        if space.status != "preparation_failed":
            raise InvalidRequest("space has no failed preparation")
        removed: list[str] = []
        retained: list[str] = []
        for artifact in space.preparation_artifacts:
            path = Path(artifact.path)
            try:
                checkout = self.git.inspect(path)
                if checkout.dirty or checkout.head != artifact.created_head:
                    retained.append(artifact.repository_id)
                    continue
                source = self.git.inspect(
                    Path(
                        next(
                            item.source_path
                            for item in space.members
                            if item.repository_id == artifact.repository_id
                        )
                    )
                )
                self.git.remove_worktree(source, path)
                removed.append(artifact.repository_id)
            except Exception:
                retained.append(artifact.repository_id)
        if not retained:
            current = self.snapshot()
            rolled_back = replace(self._space(current, space_id), status="rolled_back")
            self.repository.mutate(
                current.generation,
                lambda value: self._replace_space(value, rolled_back),
            )
        return CommandResult(
            "rollback_preparation",
            data={"removed": tuple(removed), "retained": tuple(retained)},
        )

    def resume_preparation(self, space_id: str) -> CommandResult:
        state = self.snapshot()
        space = self._space(state, space_id)
        if space.status != "preparation_failed":
            raise InvalidRequest("space has no failed preparation")
        plan = self._affected_plan(state, space)
        completed = {item.repository_id for item in space.members if item.generated}
        missing = tuple(
            item for item in plan.work_repositories if item not in completed
        )
        return CommandResult(
            "resume_preparation",
            changed=False,
            data={
                "resumable": not missing,
                "completed": tuple(sorted(completed)),
                "missing": missing,
            },
        )

    def recover(self, space_id: str, *, force: bool = False) -> CommandResult:
        if not force:
            raise InvalidRequest("recovery requires explicit force authority")
        state = self.snapshot()
        space = self._space(state, space_id)
        self._remove_owned_projection(state, space)

        def transform(current: OpenLeaseState) -> OpenLeaseState:
            current_space = self._space(current, space_id)
            recovered = replace(
                current_space,
                status="released",
                held_authority_ids=(),
                projection_name=None,
                projection_fingerprint=None,
            )
            existing = {
                (item.space_id, item.repository_id) for item in current.reconciliations
            }
            debt = tuple(
                ReconciliationRecord(space_id, item.repository_id)
                for item in current_space.members
                if item.generated and (space_id, item.repository_id) not in existing
            )
            return self._replace_space(
                current,
                recovered,
                leases=tuple(
                    item for item in current.leases if item.owner_id != space_id
                ),
                reconciliations=current.reconciliations + debt,
            )

        updated = self.repository.mutate(state.generation, transform)
        return CommandResult("recover", data=self._space(updated, space_id))

    def finalize(self, space_id: str) -> CommandResult:
        state = self.snapshot()
        space = self._space(state, space_id)
        outstanding = tuple(
            item
            for item in state.reconciliations
            if item.space_id == space_id and item.status == "pending"
        )
        existing = tuple(
            member.repository_id
            for member in space.members
            if member.generated and Path(member.effective_path).exists()
        )
        if outstanding or existing:
            raise InvalidRequest(
                "generated work remains undisposed",
                details={"pending": outstanding, "worktrees": existing},
            )

        def transform(current: OpenLeaseState) -> OpenLeaseState:
            return self._replace_space(
                current, replace(self._space(current, space_id), status="finalized")
            )

        updated = self.repository.mutate(state.generation, transform)
        return CommandResult("finalize", data=self._space(updated, space_id))

    def status(self, space_id: str | None = None) -> CommandResult:
        state = self.snapshot()
        data = {
            "generation": state.generation,
            "graph_generation": state.graph_generation,
            "repositories": state.repositories,
            "authorities": state.authorities,
            "parents": state.parents,
            "dependencies": state.dependencies,
            "leases": state.leases,
            "spaces": (
                (self._space(state, space_id),)
                if space_id is not None
                else state.spaces
            ),
            "reconciliations": state.reconciliations,
        }
        if space_id is not None:
            space = self._space(state, space_id)
            try:
                data["affected_plan"] = self._affected_plan(state, space)
            except InvalidRequest as error:
                data["affected_plan"] = None
                data["planning_issue"] = str(error)
            data["member_status"] = self._member_status(space)
        return CommandResult("status", changed=False, data=data)

    def resolve_authority(self, checkout_path: Path, relative_path: str) -> str | None:
        checkout = self.git.inspect(checkout_path)
        state = self.snapshot()
        repository = next(
            (
                item
                for item in state.repositories
                if item.common_dir is not None
                and Path(item.common_dir).resolve() == checkout.common_dir
            ),
            None,
        )
        if repository is None:
            return None
        normalized = Path(relative_path).as_posix().strip("/")
        authority = next(
            (
                item
                for item in state.authorities
                if item.repository_id == repository.identifier
                and item.relative_path == normalized
            ),
            None,
        )
        return authority.identifier if authority is not None else None

    def authority_path(self, space_id: str, authority_id: str) -> Path:
        state = self.snapshot()
        space = self._space(state, space_id)
        authority = self._authority(state, authority_id)
        member = next(
            item
            for item in space.members
            if item.repository_id == authority.repository_id
        )
        return Path(member.effective_path) / authority.relative_path

    def _prepare_successor(
        self,
        space_id: str,
        successor_name: str,
        branches: dict[str, BranchSelection],
        *,
        acquire: bool,
    ) -> CommandResult:
        state = self.snapshot()
        source = self._space(state, space_id)
        if self._space(state, successor_name, required=False) is not None:
            raise InvalidRequest(f"successor already exists: {successor_name}")
        plan = self._affected_plan(state, source)
        conflicts = self._conflicts(state, space_id, plan)
        if acquire and conflicts:
            raise AuthorityConflict("space is not isolatable", details=conflicts)
        if not acquire and not conflicts:
            raise InvalidRequest("defer is available only when lockable is false")
        repositories = {item.identifier: item for item in state.repositories}
        all_ids = tuple(
            dict.fromkeys(source.associated_repository_ids + plan.work_repositories)
        )
        preparation = plan_preparation(
            tuple(
                PreparationMember(
                    repository_id,
                    Path(repositories[repository_id].path),
                    self.git.inspect(Path(repositories[repository_id].path)).head,
                    repository_id in plan.work_repositories,
                )
                for repository_id in all_ids
            ),
            successor_name,
            self.worktree_base / successor_name,
        )
        requests = {
            item.repository_id: self._worktree_request(
                item,
                successor_name,
                branches.get(item.repository_id, BranchSelection()),
            )
            for item in preparation.generated
        }
        collisions = tuple(
            str(request.destination)
            for request in requests.values()
            if request.destination.exists() or request.destination.is_symlink()
        )
        if collisions:
            raise PreparationFailed(
                "successor preparation preflight found unavailable destinations",
                details={"collisions": collisions},
            )
        blocker_ids = tuple(sorted({item.owner_id for item in conflicts}))
        preparing = SpaceRecord(
            successor_name,
            status="preparing",
            associated_repository_ids=source.associated_repository_ids,
            affected_repository_ids=source.affected_repository_ids,
            affected_authority_ids=source.affected_authority_ids,
            blockers=blocker_ids,
            source_space_id=space_id,
            graph_generation=state.graph_generation,
        )
        reserved = self.repository.mutate(
            state.generation,
            lambda current: replace(current, spaces=(*current.spaces, preparing)),
        )
        artifacts: list[PreparedArtifactRecord] = []
        generated_members: list[SpaceMemberRecord] = []
        try:
            for item in preparation.generated:
                request = requests[item.repository_id]
                created = self.git.create_worktree(
                    self.git.inspect(item.source_path), request
                )
                artifact = PreparedArtifactRecord(
                    item.repository_id,
                    str(created.root),
                    created.branch or request.branch,
                    created.head,
                )
                artifacts.append(artifact)
                generated_members.append(
                    SpaceMemberRecord(
                        item.repository_id,
                        str(item.source_path.resolve()),
                        str(created.root),
                        item.start_commit,
                        created.branch,
                        True,
                    )
                )
            pinned_members = tuple(
                SpaceMemberRecord(
                    item.repository_id,
                    str(item.source_path.resolve()),
                    str(item.source_path.resolve()),
                    item.head,
                    self.git.inspect(item.source_path).branch,
                    False,
                )
                for item in preparation.pinned
            )
            members = tuple(generated_members) + pinned_members
            projected = replace(preparing, members=members)
            projection_members = self._projection_members(reserved, projected)
            projection_name = f"openlease-{successor_name}"
            self.openspec.create_workset(projection_name, projection_members)
            fingerprint = projection_fingerprint(projection_name, projection_members)
        except Exception as error:
            current = self.snapshot()
            failed = replace(
                self._space(current, successor_name),
                status="preparation_failed",
                members=tuple(generated_members),
                preparation_artifacts=tuple(artifacts),
            )
            self.repository.mutate(
                current.generation,
                lambda value: self._replace_space(value, failed),
            )
            raise PreparationFailed(
                f"successor preparation failed: {error}", details=failed
            ) from error
        current = self.snapshot()

        def publish(value: OpenLeaseState) -> OpenLeaseState:
            successor = self._space(value, successor_name)
            current_conflicts = self._conflicts(value, successor_name, plan)
            if acquire and current_conflicts:
                raise AuthorityConflict(
                    "authority became unavailable during isolation",
                    details=current_conflicts,
                )
            published = replace(
                successor,
                status="locked" if acquire else "deferred",
                held_authority_ids=plan.held_authorities if acquire else (),
                members=members,
                preparation_artifacts=tuple(artifacts),
                projection_name=projection_name,
                projection_fingerprint=fingerprint,
            )
            leases = value.leases
            if acquire:
                leases += tuple(
                    LeaseRecord(authority_id, successor_name)
                    for authority_id in plan.held_authorities
                )
            return self._replace_space(value, published, leases=leases)

        try:
            updated = self.repository.mutate(current.generation, publish)
        except Exception as error:
            latest = self.snapshot()
            failed = replace(
                self._space(latest, successor_name),
                status="preparation_failed",
                members=members,
                preparation_artifacts=tuple(artifacts),
                projection_name=projection_name,
                projection_fingerprint=fingerprint,
            )
            self.repository.mutate(
                latest.generation, lambda value: self._replace_space(value, failed)
            )
            raise PreparationFailed(
                f"successor publication failed: {error}", details=failed
            ) from error
        return CommandResult(
            "isolate" if acquire else "defer",
            data=self._space(updated, successor_name),
        )

    def _worktree_request(
        self, item, successor_name: str, selection: BranchSelection
    ) -> WorktreeRequest:
        if selection.mode == "new":
            return WorktreeRequest(item.destination, successor_name, item.start_commit)
        if selection.mode == "local":
            if not selection.ref:
                raise InvalidRequest("local branch selection requires a branch")
            return WorktreeRequest(
                item.destination,
                selection.ref,
                item.start_commit,
                create_branch=False,
            )
        if selection.mode == "remote":
            if not selection.ref:
                raise InvalidRequest("remote branch selection requires a ref")
            local_name = selection.local_name or selection.ref.rsplit("/", 1)[-1]
            return WorktreeRequest(item.destination, local_name, selection.ref)
        raise InvalidRequest(f"unknown branch selection: {selection.mode}")

    def _assert_boundary_safe(self, state: OpenLeaseState, space: SpaceRecord) -> None:
        plan = self._affected_plan(state, space)
        changed: dict[str, tuple[str, ...]] = {}
        for member in space.members:
            checkout = self.git.inspect(Path(member.effective_path))
            changed[member.repository_id] = tuple(
                item.path
                for item in self.git.worktree_changed_paths(
                    checkout, member.starting_commit
                )
            )
        audit = audit_authority_boundaries(self._validated_graph(state), plan, changed)
        if audit.violations:
            raise InvalidRequest(
                "changed OpenSpec paths exceed the held authority boundary",
                details=audit,
            )

    def _remove_owned_projection(
        self, state: OpenLeaseState, space: SpaceRecord
    ) -> None:
        if space.projection_name is None:
            return
        actual = next(
            (
                item
                for item in self.openspec.list_worksets()
                if item.name == space.projection_name
            ),
            None,
        )
        expected = ProjectionOwnership(
            space.projection_name,
            self._projection_members(state, space),
            space.projection_fingerprint or "",
            state.generation,
        )
        inspection = inspect_projection(expected, actual)
        if inspection.state == "conflict":
            raise OwnershipConflict(
                f"OpenSpec projection was modified: {space.projection_name}",
                details=inspection,
            )
        if inspection.state == "current":
            self.openspec.remove_workset(space.projection_name)

    def _promotion_issues(
        self, state: OpenLeaseState, space: SpaceRecord
    ) -> tuple[str, ...]:
        if space.status != "deferred":
            return ()
        issues: list[str] = []
        if space.graph_generation != state.graph_generation:
            issues.append("authority graph changed after deferral")
        for blocker_id in space.blockers:
            blocker = self._space(state, blocker_id, required=False)
            if blocker is None or blocker.handoff_disposition not in {
                "integrated",
                "abandoned",
                "superseded",
            }:
                issues.append(f"blocker handoff unresolved: {blocker_id}")
                continue
            if blocker.handoff_disposition == "integrated":
                blocker_members = {item.repository_id: item for item in blocker.members}
                successor_members = {item.repository_id: item for item in space.members}
                for repository_id in blocker_members.keys() & successor_members.keys():
                    prior = blocker_members[repository_id]
                    successor = successor_members[repository_id]
                    if prior.branch is None or successor.branch is None:
                        continue
                    preview = self.git.preview_integration(
                        MergeLeg(
                            Path(successor.effective_path),
                            prior.branch,
                            successor.branch,
                            IntegrationStrategy.MERGE,
                        )
                    )
                    if preview.merge_base != preview.source_commit:
                        issues.append(
                            "successor baseline omits blocker commit: "
                            f"{blocker_id}/{repository_id}"
                        )
        for member in space.members:
            checkout = self.git.inspect(Path(member.effective_path))
            if member.generated and checkout.dirty:
                issues.append(f"deferred member is dirty: {member.repository_id}")
            if not member.generated and checkout.head != member.starting_commit:
                issues.append(f"pinned member drifted: {member.repository_id}")
        return tuple(issues)

    def _verify_clean_checkouts(self, scope: str, paths: tuple[Path, ...]) -> None:
        dirty = tuple(
            str(checkout.root)
            for checkout in (self.git.inspect(path) for path in paths)
            if checkout.dirty
        )
        if dirty:
            raise InvalidRequest(
                f"{scope} verification found dirty integration destinations",
                details={"dirty": dirty},
            )

    def _member_status(self, space: SpaceRecord) -> tuple[dict[str, object], ...]:
        results: list[dict[str, object]] = []
        for member in space.members:
            try:
                checkout = self.git.inspect(Path(member.effective_path))
                preview = (
                    self.git.preview_integration(
                        MergeLeg(
                            checkout.root,
                            member.branch,
                            member.starting_commit,
                            IntegrationStrategy.MERGE,
                        )
                    )
                    if member.branch is not None
                    else None
                )
                results.append(
                    {
                        "repository_id": member.repository_id,
                        "path": checkout.root,
                        "missing": False,
                        "dirty": checkout.dirty,
                        "current_head": checkout.head,
                        "starting_commit": member.starting_commit,
                        "ahead": preview.ahead if preview is not None else None,
                        "behind": preview.behind if preview is not None else None,
                    }
                )
            except Exception as error:
                results.append(
                    {
                        "repository_id": member.repository_id,
                        "path": member.effective_path,
                        "missing": True,
                        "error": str(error),
                    }
                )
        return tuple(results)

    def _canonical_members(
        self, state: OpenLeaseState, space: SpaceRecord, plan
    ) -> tuple[SpaceMemberRecord, ...]:
        repository_ids = tuple(
            dict.fromkeys(space.associated_repository_ids + plan.work_repositories)
        )
        records = {item.identifier: item for item in state.repositories}
        members = []
        for repository_id in repository_ids:
            checkout = self.git.inspect(Path(records[repository_id].path))
            members.append(
                SpaceMemberRecord(
                    repository_id,
                    str(checkout.root),
                    str(checkout.root),
                    checkout.head,
                    checkout.branch,
                    False,
                )
            )
        return tuple(members)

    def _projection_members(
        self, state: OpenLeaseState, space: SpaceRecord
    ) -> tuple[Path, ...]:
        if space.members:
            roots = {
                item.repository_id: Path(item.effective_path) for item in space.members
            }
        else:
            roots = {
                item.identifier: Path(item.path)
                for item in state.repositories
                if item.identifier in space.associated_repository_ids
            }
        values: list[Path] = []
        for repository_id in space.associated_repository_ids:
            if repository_id in roots:
                values.append(roots[repository_id].resolve())
        for authority_id in self._affected_plan(state, space).held_authorities:
            authority = self._authority(state, authority_id)
            if authority.repository_id in roots:
                values.append(
                    (roots[authority.repository_id] / authority.relative_path).resolve()
                )
        return tuple(dict.fromkeys(values))

    def _repository_dependencies(
        self, state: OpenLeaseState
    ) -> tuple[tuple[str, str], ...]:
        authorities = {item.identifier: item for item in state.authorities}
        results = []
        for item in state.dependencies:
            if item.consumer_id in {repo.identifier for repo in state.repositories}:
                results.append(
                    (
                        item.consumer_id,
                        authorities[item.authority_id].repository_id,
                    )
                )
        return tuple(results)

    def _affected_plan(self, state: OpenLeaseState, space: SpaceRecord):
        if not state.authorities:
            raise InvalidRequest("an explicit authority graph is required")
        if not space.affected_repository_ids and not space.affected_authority_ids:
            raise InvalidRequest("an explicit affected claim is required")
        try:
            return resolve_affected_claim(
                self._validated_graph(state),
                AffectedClaim(
                    space.affected_repository_ids, space.affected_authority_ids
                ),
            )
        except GraphError as error:
            raise InvalidRequest(str(error)) from error

    def _conflicts(self, state: OpenLeaseState, owner_id: str, plan):
        leases = tuple(
            Lease(item.authority_id, item.owner_id)
            for item in state.leases
            if item.owner_id != owner_id
        )
        return conflicting_leases(self._validated_graph(state), plan, leases)

    def _validated_graph(self, state: OpenLeaseState) -> AuthorityGraph:
        return validate_graph(
            AuthorityGraph(
                state.repositories,
                state.authorities,
                tuple(
                    ParentRelationship(item.child_id, item.parent_id)
                    for item in state.parents
                ),
                tuple(
                    Dependency(
                        item.consumer_id,
                        item.authority_id,
                        AccessRole(item.access),
                    )
                    for item in state.dependencies
                ),
            )
        )

    def _ensure_graph_mutable(self, state: OpenLeaseState) -> None:
        if state.leases:
            raise InvalidRequest(
                "authority graph cannot change while leases are active"
            )

    def _editable_space(self, state: OpenLeaseState, space_id: str) -> SpaceRecord:
        space = self._space(state, space_id)
        if space.status != "draft":
            raise InvalidRequest("locked or prepared space shape is immutable")
        return space

    def _repository(
        self, state: OpenLeaseState, identifier: str, *, required: bool = True
    ) -> RepositoryRecord | None:
        result = next(
            (item for item in state.repositories if item.identifier == identifier), None
        )
        if result is None and required:
            raise InvalidRequest(f"repository not found: {identifier}")
        return result

    def _authority(
        self, state: OpenLeaseState, identifier: str, *, required: bool = True
    ) -> AuthorityRecord | None:
        result = next(
            (item for item in state.authorities if item.identifier == identifier), None
        )
        if result is None and required:
            raise InvalidRequest(f"authority not found: {identifier}")
        return result

    def _space(
        self, state: OpenLeaseState, identifier: str, *, required: bool = True
    ) -> SpaceRecord | None:
        result = next(
            (item for item in state.spaces if item.identifier == identifier), None
        )
        if result is None and required:
            raise InvalidRequest(f"space not found: {identifier}")
        return result

    def _replace_space(
        self,
        state: OpenLeaseState,
        space: SpaceRecord,
        *,
        leases: tuple[LeaseRecord, ...] | None = None,
        reconciliations: tuple[ReconciliationRecord, ...] | None = None,
    ) -> OpenLeaseState:
        return replace(
            state,
            spaces=tuple(
                space if item.identifier == space.identifier else item
                for item in state.spaces
            ),
            leases=state.leases if leases is None else leases,
            reconciliations=(
                state.reconciliations if reconciliations is None else reconciliations
            ),
        )

    def _mutate(
        self,
        transform: Callable[[OpenLeaseState], OpenLeaseState],
        *,
        expected_generation: int | None = None,
    ) -> OpenLeaseState:
        current = self.snapshot()
        observed = (
            current.generation if expected_generation is None else expected_generation
        )
        try:
            return self.repository.mutate(observed, transform)
        except StaleStateError as error:
            raise InvalidRequest(str(error)) from error

    def _mutate_graph_error(
        self, transform: Callable[[OpenLeaseState], OpenLeaseState]
    ) -> OpenLeaseState:
        try:
            return self._mutate(transform)
        except GraphError as error:
            raise InvalidRequest(str(error)) from error
