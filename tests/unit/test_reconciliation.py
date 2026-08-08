import pytest

from openlease.core.reconciliation import (
    ReconciliationLeg,
    ReconciliationMember,
    ReconciliationPlanError,
    dependency_order,
    plan_reconciliation,
)
from openlease.utils.git_adapter import IntegrationStrategy


def test_rejects_an_incomplete_merge_path() -> None:
    members = (
        ReconciliationMember("repo-2", "space-branch"),
        ReconciliationMember("repo-3", "space-branch"),
    )
    legs = (ReconciliationLeg("repo-3", "main", IntegrationStrategy.MERGE),)

    with pytest.raises(ReconciliationPlanError, match="repo-2"):
        plan_reconciliation(members, legs)


def test_orders_authority_provider_before_consumer() -> None:
    assert dependency_order(
        ("repo-1", "repo-2", "repo-3"), (("repo-2", "repo-3"),)
    ) == ("repo-1", "repo-3", "repo-2")
