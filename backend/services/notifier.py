import asyncio
import logging
import smtplib
import time
from email.message import EmailMessage

from config import settings

logger = logging.getLogger("notifier")

# ponytail: cooldown lives in memory, so a restart can repeat an alert once;
# persist it in PostgreSQL if that ever becomes noisy.
_last_sent: dict[str, float] = {}


def _now() -> float:
    return time.time()


def _recipients() -> list[str]:
    return [e.strip() for e in settings.ALERT_EMAILS.split(",") if e.strip()]


def _send(recipients: list[str], subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.IMAP_USER
    message["To"] = ", ".join(recipients)
    message["Subject"] = f"[SyncBank] {subject}"
    message.set_content(body)
    with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        smtp.login(settings.IMAP_USER, settings.IMAP_PASS)
        smtp.send_message(message)


async def notify(key: str, subject: str, body: str) -> None:
    """Email an alert to ALERT_EMAILS. Same key is sent at most once per cooldown.
    Never raises: an alert must not break the work it reports on."""
    recipients = _recipients()
    if not recipients:
        return
    now = _now()
    if now - _last_sent.get(key, -1e12) < settings.ALERT_COOLDOWN_MINUTES * 60:
        return
    try:
        await asyncio.to_thread(_send, recipients, subject, body)
    except Exception:
        logger.exception("alert_not_sent", extra={"source": key})
        return
    _last_sent[key] = now
