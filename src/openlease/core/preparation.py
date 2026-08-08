from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PreparationMember:
    repository_id: str
    source_path: Path
    head: str
    affected: bool


@dataclass(frozen=True, slots=True)
class GeneratedWorktree:
    repository_id: str
    source_path: Path
    destination: Path
    branch: str
    start_commit: str


@dataclass(frozen=True, slots=True)
class PreparationPlan:
    generated: tuple[GeneratedWorktree, ...]
    pinned: tuple[PreparationMember, ...]


@dataclass(frozen=True, slots=True)
class PreparedArtifact:
    repository_id: str
    path: Path
    branch: str
    created_head: str


@dataclass(frozen=True, slots=True)
class ArtifactInspection:
    path: Path
    head: str
    dirty: bool


@dataclass(frozen=True, slots=True)
class RollbackPlan:
    removable: tuple[PreparedArtifact, ...]
    debt: tuple[PreparedArtifact, ...]


def plan_preparation(
    members: tuple[PreparationMember, ...],
    successor_name: str,
    worktree_base: Path | None,
    occupied_paths: frozenset[Path] = frozenset(),
) -> PreparationPlan:
    by_repository: dict[str, PreparationMember] = {}
    for member in members:
        prior = by_repository.get(member.repository_id)
        if prior is not None and prior != member:
            raise ValueError(f"inconsistent preparation member: {member.repository_id}")
        by_repository[member.repository_id] = member
    occupied = {path.resolve() for path in occupied_paths}
    generated: list[GeneratedWorktree] = []
    for member in sorted(by_repository.values(), key=lambda item: item.repository_id):
        if not member.affected:
            continue
        base = worktree_base or member.source_path.parent
        suffix = 1
        destination = (base / f"{member.source_path.name}-olease-{suffix}").resolve()
        while destination in occupied:
            suffix += 1
            destination = (
                base / f"{member.source_path.name}-olease-{suffix}"
            ).resolve()
        occupied.add(destination)
        generated.append(
            GeneratedWorktree(
                member.repository_id,
                member.source_path,
                destination,
                successor_name,
                member.head,
            )
        )
    pinned = tuple(
        member
        for member in sorted(
            by_repository.values(), key=lambda item: item.repository_id
        )
        if not member.affected
    )
    return PreparationPlan(tuple(generated), pinned)


def plan_rollback(
    artifacts: tuple[PreparedArtifact, ...],
    inspections: dict[str, ArtifactInspection],
) -> RollbackPlan:
    removable: list[PreparedArtifact] = []
    debt: list[PreparedArtifact] = []
    for artifact in artifacts:
        inspection = inspections.get(artifact.repository_id)
        if (
            inspection is not None
            and inspection.path.resolve() == artifact.path.resolve()
            and inspection.head == artifact.created_head
            and not inspection.dirty
        ):
            removable.append(artifact)
        else:
            debt.append(artifact)
    return RollbackPlan(tuple(removable), tuple(debt))
