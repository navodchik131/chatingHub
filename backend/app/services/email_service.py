"""Отправка писем через SMTP (свой Postfix на VPS или внешний relay)."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate

from app.config import settings

log = logging.getLogger(__name__)


def render_email_body(
    template: str,
    *,
    email: str,
    app_url: str | None = None,
) -> str:
    base = (app_url or settings.public_app_url or "").rstrip("/")
    return (
        template.replace("{{email}}", email)
        .replace("{{app_url}}", base)
        .replace("{{unsubscribe_hint}}", "Чтобы отписаться от рассылок, напишите на support@modelmate.ru")
    )


def _send_smtp_sync(
    *,
    to_email: str,
    subject: str,
    body_html: str,
    body_text: str | None,
) -> None:
    host = settings.smtp_host
    port = settings.smtp_port
    user = settings.smtp_user
    password = settings.smtp_password
    from_email = settings.smtp_from_email
    from_name = settings.smtp_from_name or "ModelMate"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = to_email
    msg["Date"] = formatdate(localtime=True)

    plain = body_text or _html_to_plain(body_html)
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    if settings.smtp_use_ssl:
        server: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=60)
    else:
        server = smtplib.SMTP(host, port, timeout=60)
    try:
        if settings.smtp_use_tls and not settings.smtp_use_ssl:
            server.starttls()
        if user and password:
            server.login(user, password)
        server.sendmail(from_email, [to_email], msg.as_string())
    finally:
        server.quit()


def _html_to_plain(html: str) -> str:
    import re

    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


async def send_email(
    *,
    to_email: str,
    subject: str,
    body_html: str,
    body_text: str | None = None,
) -> None:
    if not settings.smtp_configured:
        raise RuntimeError("SMTP не настроен (SMTP_HOST и SMTP_FROM_EMAIL в .env)")
    import anyio.to_thread

    await anyio.to_thread.run_sync(
        _send_smtp_sync,
        to_email=to_email.strip(),
        subject=subject.strip(),
        body_html=body_html,
        body_text=body_text,
    )
    log.info("Email sent to %s subject=%r", to_email, subject[:80])
