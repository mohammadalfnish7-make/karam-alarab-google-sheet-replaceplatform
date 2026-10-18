import logging
import time
import traceback
from datetime import datetime, timezone

from app.agents.llm import model_name, provider
from app.database import SessionLocal
from app.errors import AppError
from app.models import AgentRun

logger = logging.getLogger("karam.agents")


def _jsonable(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)


class Trace:
    """One agent execution, committed on its own so a failed request still keeps the log."""

    def __init__(
        self,
        agent_name: str,
        *,
        actor_user_id: int | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        input_json: dict | None = None,
    ):
        self.agent_name = agent_name
        self.actor_user_id = actor_user_id
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.input_json = _jsonable(input_json)
        self.pending_output = None
        self.steps: list[dict] = []
        self.id: int | None = None
        self._closed = False
        self._t0 = time.perf_counter()
        self.started_at = datetime.now(timezone.utc)

    def __enter__(self):
        self._save(
            status="running",
            finished_at=None,
            error_message=None,
            error_stack=None,
            output_json=None,
            duration_ms=None,
        )
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._closed:
            return False
        if exc_type is None:
            self._close(status="ok", output=self.pending_output, error_message=None, error_stack=None)
        else:
            message = exc.body.get("message") if isinstance(exc, AppError) else str(exc)
            stack = "".join(traceback.format_exception(exc_type, exc, tb))
            self._close(
                status="error",
                output=self.pending_output,
                error_message=message,
                error_stack=stack,
            )
        return False

    def step(self, name: str, *, input=None, output=None, error: str | None = None, duration_ms: int | None = None) -> None:
        entry = {
            "name": name,
            "at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms,
            "input": _jsonable(input),
            "output": _jsonable(output),
            "error": error,
        }
        self.steps.append(entry)
        if not self._closed:
            self._save(status="running")

    def _close(self, *, status: str, output, error_message, error_stack) -> None:
        self._closed = True
        finished = datetime.now(timezone.utc)
        duration_ms = max(0, int((time.perf_counter() - self._t0) * 1000))
        self._save(
            status=status,
            output_json=_jsonable(output),
            error_message=error_message,
            error_stack=error_stack,
            finished_at=finished,
            duration_ms=duration_ms,
        )

    def _save(self, **fields) -> None:
        db = SessionLocal()
        try:
            if self.id is None:
                row = AgentRun(
                    agent_name=self.agent_name,
                    status=fields.get("status", "running"),
                    actor_user_id=self.actor_user_id,
                    entity_type=self.entity_type,
                    entity_id=self.entity_id,
                    provider=provider(),
                    model=model_name(),
                    input_json=self.input_json,
                    steps_json=list(self.steps),
                    output_json=fields.get("output_json"),
                    error_message=fields.get("error_message"),
                    error_stack=fields.get("error_stack"),
                    duration_ms=fields.get("duration_ms"),
                    started_at=self.started_at,
                    finished_at=fields.get("finished_at"),
                )
                db.add(row)
                db.commit()
                self.id = row.id
                return
            row = db.get(AgentRun, self.id)
            if row is None:
                return
            row.steps_json = list(self.steps)
            row.provider = provider()
            row.model = model_name()
            for key, value in fields.items():
                setattr(row, key, value)
            db.commit()
        except Exception:
            logger.exception("Could not store agent run %s", self.agent_name)
            db.rollback()
        finally:
            db.close()
