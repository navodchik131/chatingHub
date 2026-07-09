"""Тесты ограничений workflow для демо-тарифа."""

from __future__ import annotations

from app.db.models import CreditAccount, Subscription, SubscriptionStatus, WorkflowWorkspace
from app.services.billing_plan import BILLING_PLAN_CREDITS
from app.services.studio_workflow_defaults import DEMO_WORKFLOW_NAME
from app.services.workflow_entitlements import (
    assert_workflow_full_access,
    assert_workflow_workspace_allowed,
    is_workflow_demo_limited,
)


def _sub(plan: str = BILLING_PLAN_CREDITS, status: SubscriptionStatus = SubscriptionStatus.none):
    return Subscription(billing_plan=plan, status=status, plan_tier="solo")


def _cr(demo: int = 3, balance: int = 0):
    return CreditAccount(user_id=1, balance=balance, demo_generations_remaining=demo)


def test_is_workflow_demo_limited_credits_with_demo():
    assert is_workflow_demo_limited(_sub(), _cr(demo=2, balance=0))


def test_is_workflow_demo_limited_not_when_credits_balance():
    assert not is_workflow_demo_limited(_sub(), _cr(demo=2, balance=10))


def test_is_workflow_demo_limited_not_when_no_demo():
    assert not is_workflow_demo_limited(_sub(), _cr(demo=0, balance=0))


def test_assert_workflow_workspace_demo_ok():
    row = WorkflowWorkspace(user_id=1, name=DEMO_WORKFLOW_NAME, graph_json="{}")
    assert_workflow_workspace_allowed(row, _sub(), _cr())


def test_assert_workflow_workspace_other_forbidden():
    import pytest
    from fastapi import HTTPException

    row = WorkflowWorkspace(user_id=1, name="Развертка", graph_json="{}")
    with pytest.raises(HTTPException) as exc:
        assert_workflow_workspace_allowed(row, _sub(), _cr())
    assert exc.value.status_code == 403


def test_assert_workflow_full_access_blocks_create():
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        assert_workflow_full_access(_sub(), _cr())
