import pytest
from sqlalchemy import select

from app.models.material import Material, MaterialParseStatus, MaterialType
from app.models.question import Question, QuestionDifficulty, QuestionType
from app.models.study_target import StudyTarget, StudyTargetType
from app.models.user import User

from tests.test_boundary_frontend import _register_and_login


async def _seed_question(db, *, username: str):
    user = (await db.execute(select(User).where(User.username == username))).scalar_one()
    target = StudyTarget(
        user_id=user.id,
        title="Compiler",
        target_type=StudyTargetType.course,
    )
    db.add(target)
    await db.flush()
    material = Material(
        user_id=user.id,
        target_id=target.id,
        original_filename="chapter.txt",
        stored_filename=f"question-explain-{user.id}.txt",
        file_path="/tmp/chapter.txt",
        file_type=MaterialType.txt,
        content_type="text/plain",
        file_size=100,
        parse_status=MaterialParseStatus.parsed,
        parsed_text="Compiler parsing notes",
    )
    db.add(material)
    await db.flush()
    question = Question(
        user_id=user.id,
        material_id=material.id,
        target_id=target.id,
        question_type=QuestionType.single_choice,
        stem="Which phase builds an AST?",
        options=[{"key": "A", "text": "Parsing", "analysis": "Parsing checks syntax."}],
        correct_answer=["A"],
        analysis="Parsing builds an AST from tokens.",
        hints=[],
        knowledge_points=["Parsing"],
        difficulty=QuestionDifficulty.medium,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return question.id


@pytest.mark.asyncio
async def test_question_explain_returns_answer_for_owner(client, async_session_factory):
    token, username = await _register_and_login(client)

    async with async_session_factory() as db:
        question_id = await _seed_question(db, username=username)

    resp = await client.post(
        f"/questions/{question_id}/explain",
        json={"question": "为什么是 Parsing？"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["question_id"] == question_id
    assert body["data"]["answer"]


@pytest.mark.asyncio
async def test_question_explain_rejects_other_user_question(client, async_session_factory):
    token_a, username_a = await _register_and_login(client)
    token_b, _ = await _register_and_login(client)

    async with async_session_factory() as db:
        question_id = await _seed_question(db, username=username_a)

    resp = await client.post(
        f"/questions/{question_id}/explain",
        json={"question": "为什么？"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    assert resp.status_code == 404
