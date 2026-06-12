"""Routes for the AI knowledge extraction module.

This router is the HTTP entry point for the frontend. In the learning flow, it
is called after a material has been uploaded and parsed by member A's material
module. The router should stay thin: it checks request-level concerns, then
delegates the real business flow to knowledge_service.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.knowledge import KnowledgeExtractRequest, KnowledgeExtractResponse
from app.schemas.response import ApiResponse
from app.services import knowledge_service
from app.services.material_access_service import get_material_for_ai
from app.utils.responses import success

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


async def _load_material_for_ai(
    db: AsyncSession,
    *,
    user_id: int,
    material_id: int,
) -> tuple[str, str]:
    """Load material parse status and parsed text for AI processing.

    The shared material_access_service hides whether the data comes from the
    real materials table or from temporary mock materials.
    """
    material = await get_material_for_ai(db, user_id=user_id, material_id=material_id)
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material not found.",
        )
    return material.parse_status, material.parsed_text


@router.post("/extract", response_model=ApiResponse[KnowledgeExtractResponse])
async def extract_knowledge(
    payload: KnowledgeExtractRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate and return AI knowledge extraction results for one parsed material.

    Frontend usage:
    - The student clicks "AI 知识提炼" on a material detail page.
    - The frontend sends material_id and optional target_id.
    - The backend returns summary, outline, keywords, key points, and exam points.

    Layer responsibility:
    - Router: authentication, access check, parse-status check, response wrapping.
    - Service: load parsed text, call AI service, save extraction result.
    """
    # Step 1: verify the user owns this material and read its parse status.
    parse_status, parsed_text = await _load_material_for_ai(
        db,
        user_id=current_user.id,
        material_id=payload.material_id,
    )

    # Step 2: only parsed materials can be used for knowledge extraction.
    # Uploaded/parsing/failed materials do not have reliable parsed_text yet.
    if parse_status != "parsed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Material is not parsed yet.",
        )

    # Step 3: delegate business logic to the service layer.
    # TODO: Pass db and user_id into the service when persistence is implemented.
    result = knowledge_service.extract_knowledge(payload, parsed_text=parsed_text)

    # Step 4: return with the project's unified ApiResponse format.
    return success(result)
