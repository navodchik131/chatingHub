"""Ошибки LLM companion-бота: retry после исчерпания Grok / rate limit."""

from __future__ import annotations


class CompanionLLMError(RuntimeError):
    """Временная ошибка Grok/OpenAI — job нужно повторить, а не помечать done."""

    retryable: bool = True


def is_retryable_llm_error(exc: BaseException) -> bool:
    """402/429/503 и типичные тексты xAI при нулевом балансе."""
    if isinstance(exc, CompanionLLMError):
        return True
    return is_retryable_llm_error_text(str(exc))


def is_retryable_llm_error_text(message: str) -> bool:
    msg = (message or "").lower()
    if not msg:
        return False
    for token in (
        "openai http 402",
        "openai http 429",
        "openai http 503",
        "http 402",
        "http 429",
        "insufficient",
        "exhausted",
        "credit",
        "balance",
        "billing",
        "rate limit",
        "too many requests",
        "overloaded",
        "temporarily unavailable",
    ):
        if token in msg:
            return True
    return False
