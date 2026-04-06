import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_async_db
from app.models.alerts import Alert
from app.schemas.alerts import AlertResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/active", response_model=list[AlertResponse])
async def get_active_alerts(
    symbol: str | None = None,
    provider: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
) -> list[AlertResponse]:
    """
    Return unresolved alerts, newest first.
    Optionally filter by symbol and/or provider.
    """
    q = select(Alert).where(Alert.resolved == False)
    if symbol:
        q = q.where(Alert.symbol == symbol)
    if provider:
        q = q.where(Alert.provider == provider)
    result = await db.execute(q.order_by(Alert.timestamp.desc()).limit(limit))
    return result.scalars().all()


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_async_db),
) -> AlertResponse:
    """
    Mark an alert as resolved.
    """
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()

    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.resolved = True
    await db.commit()
    await db.refresh(alert)

    logger.info(f"[Alerts] Resolved alert {alert_id}")
    return alert
