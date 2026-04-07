import hashlib
import hmac
import json
import logging
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.alerts import Alert
from app.models.webhook import Webhook
from app.schemas.webhook import WebhookCreate

logger = logging.getLogger(__name__)

_SEVERITY_RANK: dict[str, int] = {"low": 1, "medium": 2, "high": 3}


# ---------------------------------------------------------------------------
# Async CRUD — used by FastAPI routes (AsyncSession)
# ---------------------------------------------------------------------------


async def create_webhook(db: AsyncSession, payload: WebhookCreate) -> Webhook:
    row = Webhook(
        id=uuid4(),
        url=str(payload.url),
        event_type=payload.event_type,
        symbol=payload.symbol.upper() if payload.symbol else None,
        min_severity=payload.min_severity,
        secret=payload.secret,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info("webhook_created", extra={"id": str(row.id), "url": row.url})
    return row


async def list_webhooks(db: AsyncSession) -> list[Webhook]:
    result = await db.execute(select(Webhook).order_by(Webhook.created_at.desc()))
    return list(result.scalars().all())


async def delete_webhook(db: AsyncSession, webhook_id: UUID) -> bool:
    result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
    row = result.scalar_one_or_none()
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    logger.info("webhook_deleted", extra={"id": str(webhook_id)})
    return True


# ---------------------------------------------------------------------------
# Sync dispatch — called from the anomaly consumer (confluent_kafka is blocking)
# ---------------------------------------------------------------------------


def dispatch_alerts(alerts: list[Alert], db: Session) -> None:
    """
    Called by the anomaly consumer after AnomalyDetector.detect_and_store().
    Queries active webhooks and fires an HTTP POST for each (alert, webhook) pair
    that passes the symbol and severity filters.
    """
    if not alerts:
        return

    webhooks: list[Webhook] = (
        db.query(Webhook)
        .filter(Webhook.is_active.is_(True), Webhook.event_type == "alert.created")
        .all()
    )
    if not webhooks:
        return

    for alert in alerts:
        for webhook in webhooks:
            if webhook.symbol and webhook.symbol != alert.symbol.upper():
                continue
            if webhook.min_severity:
                alert_rank = _SEVERITY_RANK.get(alert.severity, 0)
                min_rank = _SEVERITY_RANK.get(webhook.min_severity, 0)
                if alert_rank < min_rank:
                    continue
            _send_with_retry(webhook, alert)


def _build_payload(alert: Alert) -> dict:
    return {
        "event": "alert.created",
        "alert_id": str(alert.id),
        "symbol": alert.symbol,
        "provider": alert.provider,
        "anomaly_type": alert.anomaly_type,
        "severity": alert.severity,
        "price": alert.price,
        "timestamp": alert.timestamp.isoformat(),
    }


def _send_with_retry(webhook: Webhook, alert: Alert) -> None:
    payload = _build_payload(alert)
    body_bytes = json.dumps(payload).encode()

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if webhook.secret:
        sig = hmac.new(webhook.secret.encode(), body_bytes, hashlib.sha256).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={sig}"

    for attempt in range(1, settings.webhook_max_retries + 1):
        try:
            with httpx.Client(timeout=settings.webhook_timeout_seconds) as client:
                resp = client.post(webhook.url, content=body_bytes, headers=headers)
                resp.raise_for_status()
            logger.info(
                "webhook_dispatched",
                extra={"url": webhook.url, "alert_id": str(alert.id), "attempt": attempt},
            )
            return
        except Exception as exc:
            logger.warning(
                "webhook_dispatch_failed",
                extra={
                    "url": webhook.url,
                    "alert_id": str(alert.id),
                    "attempt": attempt,
                    "error": str(exc),
                },
            )

    logger.error(
        "webhook_dispatch_exhausted",
        extra={"url": webhook.url, "alert_id": str(alert.id)},
    )


# ---------------------------------------------------------------------------
# Async dispatch — called from the risk engine (runs on FastAPI event loop)
# ---------------------------------------------------------------------------


async def async_dispatch_alerts(alerts: list[Alert], db: AsyncSession) -> None:
    """
    Called by RiskEngine after threshold breach alerts are persisted.
    Uses httpx.AsyncClient so it does not block the event loop.
    """
    if not alerts:
        return

    result = await db.execute(
        select(Webhook).where(
            Webhook.is_active.is_(True),
            Webhook.event_type == "alert.created",
        )
    )
    webhooks = list(result.scalars().all())
    if not webhooks:
        return

    async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
        for alert in alerts:
            for webhook in webhooks:
                if webhook.symbol and webhook.symbol != alert.symbol.upper():
                    continue
                if webhook.min_severity:
                    alert_rank = _SEVERITY_RANK.get(alert.severity, 0)
                    min_rank = _SEVERITY_RANK.get(webhook.min_severity, 0)
                    if alert_rank < min_rank:
                        continue
                await _async_send_with_retry(client, webhook, alert)


async def _async_send_with_retry(
    client: httpx.AsyncClient,
    webhook: Webhook,
    alert: Alert,
) -> None:
    payload = _build_payload(alert)
    body_bytes = json.dumps(payload).encode()

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if webhook.secret:
        sig = hmac.new(webhook.secret.encode(), body_bytes, hashlib.sha256).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={sig}"

    for attempt in range(1, settings.webhook_max_retries + 1):
        try:
            resp = await client.post(webhook.url, content=body_bytes, headers=headers)
            resp.raise_for_status()
            logger.info(
                "webhook_dispatched",
                extra={"url": webhook.url, "alert_id": str(alert.id), "attempt": attempt},
            )
            return
        except Exception as exc:
            logger.warning(
                "webhook_dispatch_failed",
                extra={
                    "url": webhook.url,
                    "alert_id": str(alert.id),
                    "attempt": attempt,
                    "error": str(exc),
                },
            )

    logger.error(
        "webhook_dispatch_exhausted",
        extra={"url": webhook.url, "alert_id": str(alert.id)},
    )
