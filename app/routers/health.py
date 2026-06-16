from fastapi import APIRouter
from sqlalchemy import text
import redis.asyncio as redis

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.schemas.response import ApiResponse
from app.utils.responses import success

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=ApiResponse[dict[str, str]])
def health():
    return success({"status": "ok"})


@router.get("/db", response_model=ApiResponse[dict[str, int | str]])
async def health_db():
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        value = result.scalar()

    return success(
        {
            "db": "ok",
            "result": value,
        }
    )


@router.get("/redis", response_model=ApiResponse[dict[str, bool | str]])
async def health_redis():
    client = redis.from_url(settings.redis_url)

    try:
        result = await client.ping()
    finally:
        await client.aclose()

    return success(
        {
            "redis": "ok",
            "result": result,
        }
    )
