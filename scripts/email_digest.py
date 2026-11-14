"""Optional private SMTP delivery for the Humble Watch digest."""

from __future__ import annotations

import os
import re
import smtplib
import ssl
from email.message import EmailMessage


REQUIRED_SETTINGS = (
    "DIGEST_EMAIL_FROM",
    "DIGEST_EMAIL_TO",
    "DIGEST_SMTP_HOST",
    "DIGEST_SMTP_USERNAME",
    "DIGEST_SMTP_PASSWORD",
)


def build_email_message(content: str, sender: str, recipients: list[str], generated_at: str) -> EmailMessage:
    if not recipients or any("@" not in address or "\n" in address or "\r" in address for address in recipients):
        raise ValueError("DIGEST_EMAIL_TO must contain valid email addresses")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = f"Humble Watch digest — {generated_at[:10]}"
    plain = re.sub(r"<(https?://[^>]+)>", r"\1", content).replace("**", "").replace("`", "")
    message.set_content(plain)
    return message


def send_email_digest(content: str, generated_at: str) -> bool:
    settings = {key: os.environ.get(key, "").strip() for key in REQUIRED_SETTINGS}
    if not any(settings.values()):
        print("Email digest is not configured; skipping.")
        return False
    missing = [key for key, value in settings.items() if not value]
    if missing:
        raise ValueError("Missing email digest settings: " + ", ".join(missing))

    recipients = [address.strip() for address in settings["DIGEST_EMAIL_TO"].split(",") if address.strip()]
    message = build_email_message(content, settings["DIGEST_EMAIL_FROM"], recipients, generated_at)
    port = int(os.environ.get("DIGEST_SMTP_PORT") or "587")
    if not 1 <= port <= 65535:
        raise ValueError("DIGEST_SMTP_PORT must be between 1 and 65535")
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(settings["DIGEST_SMTP_HOST"], port, timeout=30, context=context) as smtp:
            smtp.login(settings["DIGEST_SMTP_USERNAME"], settings["DIGEST_SMTP_PASSWORD"])
            smtp.send_message(message)
    else:
        with smtplib.SMTP(settings["DIGEST_SMTP_HOST"], port, timeout=30) as smtp:
            smtp.starttls(context=context)
            smtp.login(settings["DIGEST_SMTP_USERNAME"], settings["DIGEST_SMTP_PASSWORD"])
            smtp.send_message(message)
    print(f"Email digest sent to {len(recipients)} recipient(s).")
    return True
