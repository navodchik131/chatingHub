"""
Доступ к workflow для тарифа Credits с демо-генерациями.

Шаблоны: при регистрации создаётся «Смена модели»; на демо-тарифе
в UI и API доступен только этот проект. После пополнения кредитов или подписки
provision_full_workflow_workspaces() догружает остальные (идемпотентно).
"""

from __future__ import annotations

from fastapi import HTTPException

from app.db.models import CreditAccount, Subscription, WorkflowWorkspace
from app.services.billing_plan import is_credits_plan, normalize_billing_plan
from app.services.entitlements import subscription_is_paid_active
from app.services.studio_workflow_defaults import DEMO_WORKFLOW_NAME

__all__ = [
    "DEMO_WORKFLOW_NAME",
    "assert_workflow_full_access",
    "assert_workflow_workspace_allowed",
    "is_workflow_demo_limited",
]


def is_workflow_demo_limited(
    sub: Subscription | None,
    cr: CreditAccount | None,
) -> bool:
    """
    Credits без оплаченной подписки, есть демо и нет купленных кредитов —
    только шаблон «Смена модели».
    """
    plan = normalize_billing_plan(sub.billing_plan if sub else None)
    if not is_credits_plan(plan):
        return False
    if subscription_is_paid_active(sub):
        return False
    demo_rem = int(cr.demo_generations_remaining) if cr else 0
    balance = int(cr.balance) if cr else 0
    return demo_rem > 0 and balance <= 0


def assert_workflow_full_access(sub: Subscription | None, cr: CreditAccount | None) -> None:
    if is_workflow_demo_limited(sub, cr):
        raise HTTPException(
            status_code=403,
            detail=(
                "На демо-тарифе доступен только workflow «Смена модели». "
                "Пополните кредиты или оформите Standard / Pro для других проектов."
            ),
        )


def assert_workflow_workspace_allowed(
    row: WorkflowWorkspace,
    sub: Subscription | None,
    cr: CreditAccount | None,
) -> None:
    if not is_workflow_demo_limited(sub, cr):
        return
    if (row.name or "").strip() != DEMO_WORKFLOW_NAME:
        raise HTTPException(
            status_code=403,
            detail=(
                "На демо-тарифе доступен только workflow «Смена модели». "
                "Пополните кредиты для остальных шаблонов."
            ),
        )
