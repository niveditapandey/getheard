"""
notifier.py — Send email and WhatsApp notifications.

Uses Resend for email, Meta WhatsApp Business API for WhatsApp.
Falls back gracefully if credentials not configured yet.

PLACEHOLDER SETUP:
  Email:    Set RESEND_API_KEY in .env
  WhatsApp: Set WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN in .env
            (from Meta Business Manager → WhatsApp → API Setup)
"""
import logging
import httpx
from typing import Optional, List
from config.settings import settings

logger = logging.getLogger(__name__)


async def send_email(
    to: str,
    subject: str,
    html: str,
    from_email: Optional[str] = None,
) -> bool:
    """Send transactional email via Resend. Returns True on success."""
    if not settings.has_resend:
        logger.warning(f"[Notifier] Email skipped (no RESEND_API_KEY): to={to} subject={subject}")
        return False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": from_email or settings.resend_from_email,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info(f"[Notifier] Email sent: {to} — {subject}")
                return True
            else:
                logger.error(f"[Notifier] Email failed: {resp.status_code} {resp.text}")
                return False
    except Exception as e:
        logger.error(f"[Notifier] Email error: {e}", exc_info=True)
        return False


async def send_whatsapp(
    to_number: str,   # E.164 format e.g. +919876543210
    template_name: str,
    template_params: List[str],
    language_code: str = "en",
) -> bool:
    """
    Send WhatsApp template message via Meta Business API.
    Returns True on success.

    SETUP REQUIRED:
    1. Go to business.facebook.com → WhatsApp → API Setup
    2. Copy Phone Number ID → WHATSAPP_PHONE_NUMBER_ID in .env
    3. Copy Access Token → WHATSAPP_ACCESS_TOKEN in .env
    4. Submit message templates at:
       business.facebook.com → WhatsApp → Message Templates

    Required templates:
      study_selected, study_reminder, study_completed, points_redeemed
    """
    if not settings.has_whatsapp_api:
        logger.warning(f"[Notifier] WhatsApp skipped (no credentials): to={to_number} template={template_name}")
        return False

    # Strip non-digits except leading +
    number = to_number.strip()
    if not number.startswith("+"):
        number = "+" + number

    payload = {
        "messaging_product": "whatsapp",
        "to": number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": [{
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in template_params],
            }],
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://graph.facebook.com/v19.0/{settings.whatsapp_phone_number_id}/messages",
                headers={
                    "Authorization": f"Bearer {settings.whatsapp_access_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info(f"[Notifier] WhatsApp sent: {number} — {template_name}")
                return True
            else:
                logger.error(f"[Notifier] WhatsApp failed: {resp.status_code} {resp.text}")
                return False
    except Exception as e:
        logger.error(f"[Notifier] WhatsApp error: {e}", exc_info=True)
        return False


# ── Convenience wrappers for common notifications ──────────────────────────────

async def notify_study_selected(respondent: dict, study_name: str, points: int, link: str) -> None:
    """Notify a respondent they've been selected for a study."""
    name = respondent.get("name", "there")
    wa = respondent.get("whatsapp_number")
    email = respondent.get("email")

    if wa:
        await send_whatsapp(wa, "study_selected", [name, study_name, str(points), link])
    if email:
        await send_email(
            to=email,
            subject=f"You've been selected for a study: {study_name}",
            html=f"""
            <div style="font-family:sans-serif;max-width:500px;margin:0 auto">
              <h2 style="color:#1e3c72">You've been selected!</h2>
              <p>Hi {name},</p>
              <p>You've been selected for a GetHeard research study: <strong>{study_name}</strong></p>
              <p>You'll earn <strong>{points} points</strong> for completing it.</p>
              <a href="{link}" style="display:inline-block;padding:12px 24px;background:#1e3c72;color:#fff;border-radius:8px;text-decoration:none;font-weight:bold">Start Interview &rarr;</a>
              <p style="color:#8fa3c8;font-size:12px;margin-top:24px">GetHeard &middot; Voice has Value &middot; getheard.space</p>
            </div>"""
        )


async def notify_client_milestone(client_email: str, study_name: str, milestone: str, detail: str) -> None:
    """Notify a client that an agent has reached a milestone on their study."""
    await send_email(
        to=client_email,
        subject=f"Update on your study: {study_name}",
        html=f"""
        <div style="font-family:sans-serif;max-width:500px;margin:0 auto">
          <h2 style="color:#1e3c72">Study Update</h2>
          <p><strong>{study_name}</strong></p>
          <p>&#10003; <strong>{milestone}</strong></p>
          <p>{detail}</p>
          <a href="https://getheard.space/listen" style="display:inline-block;padding:12px 24px;background:#1e3c72;color:#fff;border-radius:8px;text-decoration:none;font-weight:bold">View Dashboard &rarr;</a>
          <p style="color:#8fa3c8;font-size:12px;margin-top:24px">GetHeard &middot; getheard.space</p>
        </div>"""
    )
