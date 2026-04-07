import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_async_db
from app.schemas.webhook import WebhookCreate, WebhookResponse
from app.services.webhook_service import create_webhook, delete_webhook, list_webhooks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def register_webhook(
    payload: WebhookCreate,
    db: AsyncSession = Depends(get_async_db),
) -> WebhookResponse:
    return await create_webhook(db, payload)


@router.get("", response_model=list[WebhookResponse])
async def get_webhooks(
    db: AsyncSession = Depends(get_async_db),
) -> list[WebhookResponse]:
    return await list_webhooks(db)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_async_db),
) -> None:
    deleted = await delete_webhook(db, webhook_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
