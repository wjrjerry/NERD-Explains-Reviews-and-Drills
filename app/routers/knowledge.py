"""Routes for the unified AI knowledge extraction module."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.knowledge import KnowledgeExtractRequest, KnowledgeExtractResponse
from app.schemas.response import ApiResponse
from app.services import knowledge_service
from app.utils.responses import fail, success

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/extract", response_model=ApiResponse[KnowledgeExtractResponse])
async def extract_knowledge(
    payload: KnowledgeExtractRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run material-level or target-level knowledge extraction.

    - material_id: extract a summary for one parsed material.
    - target_id: extract an aggregated target summary and refresh the graph.
    """
    try:
        result = await knowledge_service.extract_knowledge(
            db,
            payload,
            current_user=current_user,
        )
    except ValueError as exc:
        return fail(code=40004, message=str(exc))

    return success(result)
