"""Routers for exporting learning artifacts."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services import export_service

router = APIRouter(prefix="/exports", tags=["exports"])


def _download_response(
    *,
    content: str,
    media_type: str,
    filename: str,
) -> Response:
    """Build a text download response."""
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/wrong-questions.md", response_class=Response)
async def export_wrong_questions_markdown(
    target_id: int | None = Query(default=None, description="按课程/考试目标筛选"),
    material_id: int | None = Query(default=None, description="按资料筛选"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export current user's wrong-question book as Markdown."""
    try:
        content = await export_service.export_wrong_questions_markdown(
            db,
            user_id=current_user.id,
            target_id=target_id,
            material_id=material_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _download_response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        filename="wrong-questions.md",
    )


@router.get("/review-plan/{plan_id}.md", response_class=Response)
async def export_review_plan_markdown(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export one review plan as Markdown."""
    try:
        content = await export_service.export_review_plan_markdown(
            db,
            user_id=current_user.id,
            plan_id=plan_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _download_response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        filename=f"review-plan-{plan_id}.md",
    )


@router.get("/knowledge-summary/{target_id}.md", response_class=Response)
async def export_knowledge_summary_markdown(
    target_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export target knowledge extraction, graph, and mastery as Markdown."""
    try:
        content = await export_service.export_knowledge_summary_markdown(
            db,
            user_id=current_user.id,
            target_id=target_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _download_response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        filename=f"knowledge-summary-{target_id}.md",
    )


@router.get("/anki/{target_id}.csv", response_class=Response)
async def export_anki_csv(
    target_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export generated questions under one target as Anki-compatible CSV."""
    try:
        content = await export_service.export_anki_csv(
            db,
            user_id=current_user.id,
            target_id=target_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _download_response(
        content=content,
        media_type="text/csv; charset=utf-8",
        filename=f"anki-{target_id}.csv",
    )
