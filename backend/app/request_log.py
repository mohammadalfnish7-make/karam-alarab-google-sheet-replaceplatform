"""HTTP request logging for developer timing/debug."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from app.database import SessionLocal
from app.models import RequestLog
from app.security import read_token

logger = logging.getLogger("karam.requests")

_SKIP_PREFIXES = ("/api/health",)
_SKIP_EXACT = {"/api/request-logs"}


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64] or None
    if request.client:
        return (request.client.host or "")[:64] or None
    return None


def _actor_user_id(request: Request) -> int | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    return read_token(token)


def _should_log(path: str) -> bool:
    if not path.startswith("/api/"):
        return False
    if path in _SKIP_EXACT:
        return False
    return not any(path.startswith(prefix) for prefix in _SKIP_PREFIXES)


def store_request_log(
    *,
    method: str,
    path: str,
    query: str | None,
    status_code: int,
    duration_ms: int,
    actor_user_id: int | None,
    ip: str | None,
    user_agent: str | None,
    error_message: str | None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            RequestLog(
                method=method[:12],
                path=path[:255],
                query=(query[:2000] if query else None),
                status_code=status_code,
                duration_ms=max(0, duration_ms),
                actor_user_id=actor_user_id,
                ip=ip,
                user_agent=(user_agent[:1000] if user_agent else None),
                error_message=(error_message[:2000] if error_message else None),
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    except Exception:
        logger.exception("Could not store request log %s %s", method, path)
        db.rollback()
    finally:
        db.close()


class RequestLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not _should_log(path):
            return await call_next(request)

        started = time.perf_counter()
        status_code = 500
        error_message = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            error_message = str(exc)[:2000]
            raise
        finally:
            duration_ms = int((time.perf_counter() - started) * 1000)
            store_request_log(
                method=request.method,
                path=path,
                query=request.url.query or None,
                status_code=status_code,
                duration_ms=duration_ms,
                actor_user_id=_actor_user_id(request),
                ip=_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                error_message=error_message,
            )
