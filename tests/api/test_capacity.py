"""Capacity safeguards (#36): load shedding, fast failure when the DB pool is exhausted, and the pre-start step."""
import asyncio

import httpx
import pytest
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from conftest import CITIZEN

from permitpass.load_shedding import LoadSheddingMiddleware


def _slow_app(release: asyncio.Event, limit: int):
    async def slow(_request):
        await release.wait()
        return JSONResponse({"ok": True})

    async def health(_request):
        return JSONResponse({"status": "ok"})

    inner = Starlette(routes=[Route("/slow", slow), Route("/health", health)])
    return LoadSheddingMiddleware(inner, max_in_flight=limit)


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_requests_beyond_the_limit_get_an_immediate_503(anyio_backend):
    release = asyncio.Event()
    app = _slow_app(release, limit=2)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        busy = [asyncio.create_task(c.get("/slow")) for _ in range(2)]
        await asyncio.sleep(0.05)                                  # both are now in flight
        shed = await asyncio.wait_for(c.get("/slow"), timeout=1)   # must not wait for the slow ones
        assert shed.status_code == 503
        assert shed.headers["retry-after"] == "2"
        assert shed.json() == {"detail": "Server busy, please retry shortly"}
        health = await asyncio.wait_for(c.get("/health"), timeout=1)
        assert health.status_code == 200                           # health is never shed
        release.set()
        assert [r.status_code for r in await asyncio.gather(*busy)] == [200, 200]
        assert (await c.get("/slow")).status_code == 200           # capacity is freed again
    assert app.in_flight == 0 and app.shed == 1


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_limit_zero_means_unlimited(anyio_backend):
    release = asyncio.Event()
    app = _slow_app(release, limit=0)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        tasks = [asyncio.create_task(c.get("/slow")) for _ in range(10)]
        await asyncio.sleep(0.05)
        release.set()
        assert {r.status_code for r in await asyncio.gather(*tasks)} == {200}


def test_db_pool_exhaustion_is_a_fast_503(client):
    from permitpass.db import get_db
    from permitpass.main import app

    def exhausted():
        raise SQLAlchemyTimeoutError("QueuePool limit reached")
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = exhausted
    try:
        r = client.get("/applications", headers=CITIZEN)
    finally:
        app.dependency_overrides.pop(get_db)
    assert r.status_code == 503 and r.headers["retry-after"] == "2"
    assert r.headers["x-content-type-options"] == "nosniff"        # security headers still applied


def test_prestart_is_safe_to_run_repeatedly(client, capsys):
    from permitpass.prestart import main

    main()
    main()
    assert "prestart: database ready" in capsys.readouterr().out
    assert client.get("/auth/me", headers=CITIZEN).status_code == 200
