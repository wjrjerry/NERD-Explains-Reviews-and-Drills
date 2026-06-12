"""Business service for material-based AI question answering."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.qa import QaRecord
from app.repositories.qa_repository import QaRepository
from app.schemas.qa import QaAskRequest, QaAskResponse, QaHistoryItem, QaReference
from app.services import ai_service


def _normalize_references(
    references: list[dict[str, int | str]] | object,
) -> list[QaReference]:
    """Convert stored JSON references to response schema objects."""
    if not isinstance(references, list):
        return []

    normalized: list[QaReference] = []
    for reference in references:
        if not isinstance(reference, dict):
            continue

        try:
            normalized.append(
                QaReference(
                    material_id=int(reference["material_id"]),
                    snippet=str(reference["snippet"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    return normalized


def _to_history_item(record: QaRecord) -> QaHistoryItem:
    """Map one QaRecord ORM object to the public history response."""
    return QaHistoryItem(
        qa_record_id=record.id,
        material_id=record.material_id,
        question=record.question,
        answer=record.answer,
        references=_normalize_references(record.references),
        ai_provider=record.ai_provider,
        ai_model=record.ai_model,
        created_at=record.created_at.isoformat(),
    )


async def ask_question(
    db: AsyncSession,
    payload: QaAskRequest,
    *,
    user_id: int,
    parsed_text: str,
) -> QaAskResponse:
    """Coordinate material-based AI answering and QA response assembly.

    Expected final workflow:
    1. Receive QaAskRequest from the router.
    2. Load parsed material text by payload.material_id.
    3. Call ai_service.answer_question(parsed_text, question).
    4. Save question, answer, references, user_id, and material_id.
    5. Return the saved QA record for display.

    The router is still responsible for authentication and material loading.
    This service only coordinates AI generation and QA record persistence.
    """
    generated = ai_service.answer_question(
        parsed_text,
        payload.question,
        material_id=payload.material_id,
    )
    references = [
        QaReference(
            material_id=int(reference["material_id"]),
            snippet=str(reference["snippet"]),
        )
        for reference in generated["references"]
    ]

    record = await QaRepository.create_qa_record(
        db,
        user_id=user_id,
        material_id=payload.material_id,
        question=payload.question,
        answer=str(generated["answer"]),
        references=[reference.model_dump() for reference in references],
        ai_provider=settings.ai_provider,
        ai_model=settings.ai_model,
    )

    return QaAskResponse(
        qa_record_id=record.id,
        question=record.question,
        answer=record.answer,
        references=references,
        created_at=record.created_at.isoformat(),
    )


async def list_history(
    db: AsyncSession,
    *,
    user_id: int,
    material_id: int | None,
    page: int,
    page_size: int,
) -> tuple[list[QaHistoryItem], int]:
    """List saved QA records owned by the current user."""
    records, total = await QaRepository.list_qa_records(
        db,
        user_id=user_id,
        material_id=material_id,
        page=page,
        page_size=page_size,
    )
    return [_to_history_item(record) for record in records], total
