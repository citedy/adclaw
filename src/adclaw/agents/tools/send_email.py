# -*- coding: utf-8 -*-
"""Send email via SMTP (Unosend or any SMTP provider)."""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from agentscope.tool import ToolResponse

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.unosend.co")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "unosend")


def send_email(
    to: str,
    subject: str,
    body: str,
    html: bool = True,
    from_email: str = "",
    from_name: str = "AdClaw",
) -> ToolResponse:
    """Send an email to one or more recipients.

    Args:
        to: Recipient email address (or comma-separated for multiple).
        subject: Email subject line.
        body: Email body (HTML by default, plain text if html=False).
        html: If True, body is treated as HTML. Default True.
        from_email: Sender email. Default: uses SMTP_FROM env or noreply@domain.
        from_name: Sender display name. Default: AdClaw.

    Returns:
        ToolResponse with send status.
    """
    api_key = os.environ.get("UNOSEND_API_KEY", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", api_key)

    if not smtp_password:
        return ToolResponse(
            content=[{
                "type": "text",
                "text": "Email not configured. Set UNOSEND_API_KEY or SMTP_PASSWORD environment variable.",
            }],
            is_error=True,
        )

    sender = from_email or os.environ.get("SMTP_FROM", "")
    if not sender:
        return ToolResponse(
            content=[{
                "type": "text",
                "text": (
                    "Sender email not configured. "
                    "Set SMTP_FROM environment variable "
                    "(e.g. noreply@yourdomain.com)."
                ),
            }],
            is_error=True,
        )
    display_from = f"{from_name} <{sender}>"

    recipients = [r.strip() for r in to.split(",") if r.strip()]
    if not recipients:
        return ToolResponse(
            content=[{"type": "text", "text": "No valid recipients provided."}],
            is_error=True,
        )

    msg = MIMEMultipart("alternative")
    msg["From"] = display_from
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject

    if html:
        msg.attach(MIMEText(body, "html"))
    else:
        msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SMTP_USER, smtp_password)
            server.send_message(msg)

        logger.info("Email sent to %s: %s", to, subject)
        return ToolResponse(
            content=[{
                "type": "text",
                "text": f"Email sent to {to}\nSubject: {subject}",
            }],
        )
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return ToolResponse(
            content=[{"type": "text", "text": f"Failed to send email: {e}"}],
            is_error=True,
        )
