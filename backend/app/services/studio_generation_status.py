"""Статусы пайплайна архива студии (фаза A)."""

from __future__ import annotations


class StudioGenerationStatus:
    PROCESSING = "processing"
    PROVIDER_READY = "provider_ready"
    ARCHIVING = "archiving"
    READY = "ready"
    FAILED = "failed"
