import pytest


@pytest.mark.asyncio
async def test_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert "backend is running" in body["data"]["message"]


@pytest.mark.asyncio
async def test_db_health(client):
    resp = await client.get("/health/db")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["db"] == "ok"


@pytest.mark.asyncio
async def test_redis_health(monkeypatch, client):
    class _FakeRedis:
        def __init__(self, *args, **kwargs):
            pass

        async def ping(self):
            return True

        async def aclose(self):
            return None

    monkeypatch.setattr("redis.asyncio.from_url", lambda *_args, **_kwargs: _FakeRedis())

    resp = await client.get("/health/redis")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["redis"] == "ok"
