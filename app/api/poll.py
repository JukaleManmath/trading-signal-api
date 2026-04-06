from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_async_db
from app.models.polling_jobs import PollingJob
from app.schemas.poll import PollingRequest, PollingResponse

router = APIRouter(prefix="/prices", tags=["Polling Jobs Endpoint"])


@router.post("/poll", status_code=status.HTTP_202_ACCEPTED, response_model=PollingResponse)
async def polling_jobs(data: PollingRequest, db: AsyncSession = Depends(get_async_db)):
    job_ids = []

    for symbol in data.symbols:
        job_id = uuid4()
        polling_job = PollingJob(
            id=job_id,
            symbol=symbol,
            provider=data.provider,
            interval=data.interval,
            status="pending",
        )
        db.add(polling_job)
        job_ids.append(str(job_id))

    await db.commit()
    return {
        "job_id": ",".join(job_ids),
        "status": "pending",
        "config": {
            "symbols": data.symbols,
            "interval": data.interval,
        },
    }


@router.delete("/poll/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_polling_job(job_id: UUID, db: AsyncSession = Depends(get_async_db)) -> None:
    result = await db.execute(select(PollingJob).where(PollingJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Polling job not found")
    await db.delete(job)
    await db.commit()
