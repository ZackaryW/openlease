from __future__ import annotations

from dataclasses import dataclass

from openlease.utils.git_adapter import IntegrationStrategy


class ReconciliationPlanError(ValueError):
    """An explicit reconciliation path is incomplete or inconsistent."""


@dataclass(frozen=True, slots=True)
class ReconciliationMember:
    repository_id: str
    branch: str


@dataclass(frozen=True, slots=True)
class ReconciliationLeg:
    repository_id: str
    destination_ref: str
    strategy: IntegrationStrategy


@dataclass(frozen=True, slots=True)
class ReconciliationPlan:
    members: tuple[ReconciliationMember, ...]
    legs: tuple[ReconciliationLeg, ...]


def plan_reconciliation(
    members: tuple[ReconciliationMember, ...],
    legs: tuple[ReconciliationLeg, ...],
) -> ReconciliationPlan:
    member_ids = [item.repository_id for item in members]
    leg_ids = [item.repository_id for item in legs]
    if len(member_ids) != len(set(member_ids)) or len(leg_ids) != len(set(leg_ids)):
        raise ReconciliationPlanError("duplicate reconciliation repository")
    missing = sorted(set(member_ids) - set(leg_ids))
    extra = sorted(set(leg_ids) - set(member_ids))
    if missing:
        raise ReconciliationPlanError(f"missing merge path for {', '.join(missing)}")
    if extra:
        raise ReconciliationPlanError(f"unknown merge path for {', '.join(extra)}")
    if any(not item.destination_ref for item in legs):
        raise ReconciliationPlanError("empty reconciliation destination")
    return ReconciliationPlan(members, legs)


def dependency_order(
    repository_ids: tuple[str, ...],
    dependencies: tuple[tuple[str, str], ...],
) -> tuple[str, ...]:
    """Order provider repositories before their consumers."""
    remaining = set(repository_ids)
    result: list[str] = []
    while remaining:
        ready = sorted(
            repository
            for repository in remaining
            if not any(
                consumer == repository and provider in remaining
                for consumer, provider in dependencies
            )
        )
        if not ready:
            raise ReconciliationPlanError("repository dependency cycle")
        result.extend(ready)
        remaining.difference_update(ready)
    return tuple(result)
