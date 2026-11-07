"""Idempotency keys for write requests (#47).

A client sends `Idempotency-Key: <uuid>`. The first request with that key runs; every later one with the same key
(same user, same request) gets the stored answer replayed, so a retry after a lost response can't create a second
application or send a second M-Pesa prompt.

  * The key is claimed (status in_progress) in its own committed transaction *before* the work runs, so a
    concurrent duplicate sees it and gets 409 instead of running too.
  * Answers worth repeating (2xx, and 4xx such as validation or a refused transition) are stored and replayed.
  * Temporary failures (503: KRA or M-Pesa down; 5xx) release the key, so the client's retry really retries.
  * Keys are scoped per user and expire after 24 h.
"""
import hashlib
import json
import re
from collections.abc import Callable
from datetime import timedelta

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from . import clock
from .db import SessionLocal
from .models import IdempotencyKeyRow

TTL = timedelta(hours=24)
KEY_FORMAT = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
HEADER = "Idempotency-Key"


def _fingerprint(scope: str, payload) -> str:
    return hashlib.sha256(json.dumps([scope, jsonable_encoder(payload)], sort_keys=True).encode()).hexdigest()


def _claim(user_id: str, key: str, digest: str) -> IdempotencyKeyRow | JSONResponse:
    """Insert the key as in_progress, or return what to answer if it already exists."""
    for _ in range(2):   # second pass only after deleting an expired key
        with SessionLocal() as s:
            s.add(IdempotencyKeyRow(user_id=user_id, key=key, request_hash=digest, status="in_progress",
                                    created_at=clock.now()))
            try:
                s.commit()
                return None
            except IntegrityError:
                s.rollback()
            row = s.scalar(select(IdempotencyKeyRow).where(IdempotencyKeyRow.user_id == user_id, IdempotencyKeyRow.key == key))
            if row is None:
                continue                      # vanished between insert and read (released by its owner): try again
            if clock.aware(row.created_at) < clock.now() - TTL:
                s.delete(row)
                s.commit()
                continue
            if row.request_hash != digest:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                    f"{HEADER} was already used for a different request")
            if row.status == "in_progress":
                raise HTTPException(status.HTTP_409_CONFLICT, "A request with this Idempotency-Key is still in progress, retry shortly",
                                    headers={"Retry-After": "1"})
            return JSONResponse(json.loads(row.response_body), status_code=row.response_status,
                                headers={"Idempotent-Replayed": "true"})
    raise HTTPException(status.HTTP_409_CONFLICT, "Could not claim the Idempotency-Key, retry shortly", headers={"Retry-After": "1"})


def _finish(user_id: str, key: str, code: int | None, body=None) -> None:
    with SessionLocal() as s:
        row = s.scalar(select(IdempotencyKeyRow).where(IdempotencyKeyRow.user_id == user_id, IdempotencyKeyRow.key == key))
        if row is None:
            return
        if code is None:          # temporary failure: forget the key so a retry runs for real
            s.delete(row)
        else:
            row.status, row.response_status, row.response_body = "done", code, json.dumps(jsonable_encoder(body))
        s.commit()


def run_once(key: str | None, user_id: str, scope: str, payload, work: Callable[[], object], success_status: int = 200):
    """Run `work()` at most once per (user, key). `work` returns the JSON-able response body or raises HTTPException."""
    if key is None:
        return work()
    if not KEY_FORMAT.match(key):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{HEADER} must be 8-64 letters, digits, '-' or '_'")
    replay = _claim(user_id, key, _fingerprint(scope, payload))
    if replay is not None:
        return replay
    try:
        body = work()
    except HTTPException as exc:
        if exc.status_code >= 500:
            _finish(user_id, key, None)
        else:
            _finish(user_id, key, exc.status_code, {"detail": exc.detail})
        raise
    except Exception:
        _finish(user_id, key, None)
        raise
    _finish(user_id, key, success_status, body)
    return JSONResponse(jsonable_encoder(body), status_code=success_status)


def prune(db) -> int:
    """Delete expired keys (called by the background sweeper)."""
    r = db.execute(delete(IdempotencyKeyRow).where(IdempotencyKeyRow.created_at < clock.now() - TTL))
    db.commit()
    return r.rowcount or 0
