import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select


def _random_username() -> str:
    return f"testuser_{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_user_isolation_on_study_target_access(client):
    # user A
    user_a = _random_username()
    pw = "password123"
    await client.post("/auth/register", json={"username": user_a, "password": pw})
    resp_a = await client.post("/auth/login", json={"username": user_a, "password": pw})
    token_a = resp_a.json()["data"]["token"]["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # create a study target as user A
    resp_target = await client.post("/study-targets", json={"title": "私有目标"}, headers=headers_a)
    assert resp_target.status_code == 200
    target_id = resp_target.json()["data"]["target"]["id"]

    # user B
    user_b = _random_username()
    await client.post("/auth/register", json={"username": user_b, "password": pw})
    resp_b = await client.post("/auth/login", json={"username": user_b, "password": pw})
    token_b = resp_b.json()["data"]["token"]["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # user B tries to access user A's target -> expect business-level 404 (code 40401)
    resp_access = await client.get(f"/study-targets/{target_id}", headers=headers_b)
    assert resp_access.status_code == 200
    body = resp_access.json()
    assert body["code"] == 40401


@pytest.mark.asyncio
async def test_admin_permission_enforcement(client):
    from fastapi import Depends

    from app.dependencies.auth import get_current_admin_user
    from app.db.session import AsyncSessionLocal
    from app.models.user import User, UserRole

    username = _random_username()
    pw = "password123"
    await client.post("/auth/register", json={"username": username, "password": pw})
    resp = await client.post("/auth/login", json={"username": username, "password": pw})
    token = resp.json()["data"]["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # register a temporary admin-only test route on the app
    from app.main import app as fastapi_app

    path = f"/_test_admin_only_{uuid.uuid4().hex[:8]}"

    @fastapi_app.get(path)
    async def _admin_only_route(admin=Depends(get_current_admin_user)):
        return {"ok": True}

    # normal user should get 403 with expected message
    resp_forbidden = await client.get(path, headers=headers)
    assert resp_forbidden.status_code == 403
    assert resp_forbidden.json().get("detail") == "需要管理员权限"

    # promote user to admin via DB session
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one()
        user.role = UserRole.admin
        session.add(user)
        await session.commit()

    # call again, should be allowed
    resp_ok = await client.get(path, headers=headers)
    assert resp_ok.status_code == 200
    assert resp_ok.json() == {"ok": True}


@pytest.mark.asyncio
async def test_expired_token_rejected(client):
    from datetime import timedelta

    from app.core.security import create_access_token
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.user import User

    username = _random_username()
    pw = "password123"
    await client.post("/auth/register", json={"username": username, "password": pw})

    # find the user's id in DB
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one()

    # craft an already-expired token
    expired = create_access_token(subject=str(user.id), expires_delta=timedelta(seconds=-10))
    headers = {"Authorization": f"Bearer {expired}"}

    # access an endpoint requiring authentication
    resp = await client.get("/study-targets", headers=headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_missing_token_rejected(client):
    # No Authorization header -> should be 401 with expected detail
    resp = await client.get("/study-targets")
    assert resp.status_code == 401
    body = resp.json()
    assert body.get("detail") == "未提供认证令牌"


@pytest.mark.asyncio
async def test_wrong_scheme_rejected(client):
    # Authorization with wrong scheme should be rejected
    headers = {"Authorization": "Token abc123"}
    resp = await client.get("/study-targets", headers=headers)
    assert resp.status_code == 401
    assert resp.json().get("detail") == "认证令牌类型错误"


@pytest.mark.asyncio
async def test_invalid_token_rejected(client):
    # Bearer with invalid token string
    headers = {"Authorization": "Bearer not-a-real-token"}
    resp = await client.get("/study-targets", headers=headers)
    assert resp.status_code == 401
    assert resp.json().get("detail") == "认证令牌无效或已过期"


@pytest.mark.asyncio
async def test_disabled_user_forbidden(client):
    # register and obtain token
    username = _random_username()
    pw = "password123"
    await client.post("/auth/register", json={"username": username, "password": pw})
    resp = await client.post("/auth/login", json={"username": username, "password": pw})
    token = resp.json()["data"]["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # set user is_active = False
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.user import User

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one()
        user.is_active = False
        session.add(user)
        await session.commit()

    # now call an authenticated endpoint
    resp2 = await client.get("/study-targets", headers=headers)
    assert resp2.status_code == 403
    assert resp2.json().get("detail") == "账号已被禁用"
