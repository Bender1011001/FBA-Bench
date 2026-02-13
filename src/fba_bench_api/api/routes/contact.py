from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from fba_bench_api.core.database_async import get_async_db_session
from fba_bench_api.models.contact_message import ContactMessageORM, ContactMessageStatus
from fba_bench_core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/contact", tags=["Contact"])


class ContactCreateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    email: EmailStr
    subject: Optional[str] = Field(default=None, max_length=255)
    message: str = Field(min_length=5, max_length=10000)

    # Honeypot (should be empty)
    hp: Optional[str] = Field(default=None, max_length=255)

    # Best-effort metadata from client
    source: Optional[str] = Field(default=None, max_length=255)


class ContactCreateResponse(BaseModel):
    status: str
    id: Optional[str] = None
    emailed: bool = False


def _sanitize_header(s: str) -> str:
    # Prevent header injection in Subject/From fields.
    return s.replace("\r", " ").replace("\n", " ").strip()


def _send_smtp_email(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    mail_from: str,
    mail_to: str,
    subject: str,
    body: str,
    use_tls: bool,
) -> None:
    msg = EmailMessage()
    msg["From"] = _sanitize_header(mail_from)
    msg["To"] = _sanitize_header(mail_to)
    msg["Subject"] = _sanitize_header(subject)
    msg.set_content(body)

    with smtplib.SMTP(host=host, port=int(port), timeout=20) as server:
        if use_tls:
            server.starttls()
        server.login(user, password)
        server.send_message(msg)


@router.post("", response_model=ContactCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_contact_message(
    payload: ContactCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db_session),
) -> ContactCreateResponse:
    # Honeypot: pretend success but do not store/send.
    if payload.hp and payload.hp.strip():
        return ContactCreateResponse(status="ok")

    msg_id = str(uuid4())
    ip = getattr(getattr(request, "client", None), "host", None)
    ua = request.headers.get("user-agent")

    row = ContactMessageORM(
        id=msg_id,
        name=(payload.name.strip() if payload.name else None),
        email=str(payload.email),
        subject=(payload.subject.strip() if payload.subject else None),
        message=payload.message.strip(),
        ip=ip,
        user_agent=(ua[:512] if ua else None),
        source=(payload.source.strip() if payload.source else None),
        status=ContactMessageStatus.received,
    )

    db.add(row)

    # Best-effort email delivery (optional, configured via env).
    settings = get_settings()
    to_email = settings.contact_reply_to
    emailed = False

    if to_email:
        host = (settings.smtp_host or "").strip()
        user = (settings.smtp_user or "").strip()
        password = (settings.smtp_password or "").strip()
        mail_from = (settings.smtp_from or settings.smtp_user or "").strip()

        if host and user and password and mail_from:
            subject = payload.subject.strip() if payload.subject else "New website message"
            body = "\n".join(
                [
                    "New message from the website:",
                    "",
                    f"From: {payload.name or '(no name)'} <{payload.email}>",
                    f"IP: {ip or '(unknown)'}",
                    f"User-Agent: {ua or '(unknown)'}",
                    f"Source: {payload.source or '(unknown)'}",
                    "",
                    payload.message.strip(),
                    "",
                    f"Message ID: {msg_id}",
                ]
            )
            try:
                await asyncio.to_thread(
                    _send_smtp_email,
                    host=host,
                    port=int(settings.smtp_port),
                    user=user,
                    password=password,
                    mail_from=mail_from,
                    mail_to=to_email,
                    subject=f"[FBA-Bench] {subject}",
                    body=body,
                    use_tls=bool(settings.smtp_use_tls),
                )
                emailed = True
                row.status = ContactMessageStatus.emailed
            except Exception as e:
                logger.warning("Failed to send contact email for %s: %s", msg_id, e)
        else:
            logger.info(
                "CONTACT_TO_EMAIL set but SMTP not fully configured; storing message only (id=%s).",
                msg_id,
            )

    try:
        await db.flush()
    except Exception as e:
        logger.error("Failed to persist contact message %s: %s", msg_id, e)
        raise HTTPException(status_code=500, detail="Failed to store message") from e

    return ContactCreateResponse(status="received", id=msg_id, emailed=emailed)

