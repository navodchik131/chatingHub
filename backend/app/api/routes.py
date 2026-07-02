"""Сборка HTTP-маршрутов API."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.analytics_routes import router as analytics_router
from app.api.admin_routes import router as admin_router
from app.api.admin_email_routes import router as admin_email_router
from app.api.billing_routes import router as billing_router
from app.api.referral_routes import router as referral_router
from app.api.chat_routes import router as chat_router
from app.api.integrations_routes import router as integrations_router
from app.api.push_routes import router as push_router
from app.api.studio_routes import router as studio_router
from app.api.studio_workflow_routes import router as studio_workflow_router
from app.api.tribute_routes import router as tribute_router
from app.api.webhooks_routes import router as webhooks_router
from app.api.workspace_routes import router as workspace_router
from app.auth.routes import router as auth_router

router = APIRouter(prefix="/api")
router.include_router(auth_router)
router.include_router(workspace_router)
router.include_router(chat_router)
router.include_router(push_router)
router.include_router(webhooks_router)
router.include_router(tribute_router)
router.include_router(integrations_router)
router.include_router(billing_router)
router.include_router(referral_router)
router.include_router(studio_router)
router.include_router(studio_workflow_router)
router.include_router(analytics_router)
router.include_router(admin_router)
router.include_router(admin_email_router)
