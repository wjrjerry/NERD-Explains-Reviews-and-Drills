"""Routers for target-level knowledge graph generation and querying."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.knowledge_graph import (
    KnowledgeGraphGenerateRequest,
    KnowledgeGraphResponse,
)
from app.schemas.response import ApiResponse
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.llm_service import LlmServiceError
from app.utils.responses import fail, success

router = APIRouter(prefix="/knowledge-graphs", tags=["knowledge-graphs"])


@router.post("/generate", response_model=ApiResponse[KnowledgeGraphResponse])
async def generate_knowledge_graph(
    payload: KnowledgeGraphGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a target-level knowledge graph from all parsed materials."""
    try:
        graph = await KnowledgeGraphService.generate(
            db,
            current_user=current_user,
            payload=payload,
        )
    except ValueError as exc:
        return fail(code=40004, message=str(exc))
    except LlmServiceError as exc:
        return fail(code=50301, message=str(exc))

    return success(graph)


@router.get("/{target_id}", response_model=ApiResponse[KnowledgeGraphResponse])
async def get_knowledge_graph(
    target_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's knowledge graph for one study target."""
    try:
        graph = await KnowledgeGraphService.get_graph(
            db,
            current_user=current_user,
            target_id=target_id,
        )
    except ValueError as exc:
        return fail(code=40401, message=str(exc))

    return success(graph)

