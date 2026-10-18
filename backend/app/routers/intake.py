import asyncio

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.check_read import read_check_file
from app.deps import get_current_user
from app.errors import AppError
from app.models import User

router = APIRouter(prefix="/intake", tags=["intake"])

_MAX_FILE = 15 * 1024 * 1024
_MAX_BATCH = 20
_MIMES = {
    "application/pdf": "application/pdf",
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "image/gif": "image/gif",
}


def _error(status: int, message: str) -> AppError:
    return AppError(status, {"message": message, "field_errors": {}, "warnings": []})


def _mime(upload: UploadFile, content: bytes) -> str:
    declared = (upload.content_type or "").split(";")[0].strip().lower()
    name = (upload.filename or "").lower()
    if content.startswith(b"%PDF"):
        return "application/pdf"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG"):
        return "image/png"
    if declared in _MIMES:
        return _MIMES[declared]
    if name.endswith(".pdf"):
        return "application/pdf"
    if name.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".webp"):
        return "image/webp"
    raise _error(422, "Upload a photo or a PDF")


async def _read_one(
    *,
    content: bytes,
    mime: str,
    kind: str,
    filename: str,
    actor_user_id: int,
) -> dict:
    try:
        fields = await asyncio.to_thread(
            read_check_file,
            content,
            mime,
            kind,
            actor_user_id=actor_user_id,
        )
        return {"filename": filename, "fields": fields, "error": None}
    except AppError as exc:
        message = exc.body.get("message") if isinstance(exc.body, dict) else str(exc)
        return {"filename": filename, "fields": None, "error": message}


@router.post("/read")
async def read_intake_file(
    kind: str = Form(...),
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
):
    if kind not in {"delivery_note", "scale"}:
        raise _error(422, "Kind must be delivery_note or scale")
    content = await file.read()
    if not content:
        raise _error(422, "The file is empty")
    if len(content) > _MAX_FILE:
        raise _error(422, "File must be 15 MB or smaller")
    fields = await asyncio.to_thread(
        read_check_file,
        content,
        _mime(file, content),
        kind,
        actor_user_id=_user.id,
    )
    return {"kind": kind, "filename": file.filename or "", "fields": fields}


@router.post("/read-batch")
async def read_intake_batch(
    kind: str = Form(...),
    files: list[UploadFile] = File(...),
    _user: User = Depends(get_current_user),
):
    """Read many photos/notes in parallel (one model call per file)."""
    if kind not in {"delivery_note", "scale"}:
        raise _error(422, "Kind must be delivery_note or scale")
    if not files:
        raise _error(422, "Upload at least one file")
    if len(files) > _MAX_BATCH:
        raise _error(422, f"Upload at most {_MAX_BATCH} files at once")

    prepared: list[tuple[bytes, str, str]] = []
    for upload in files:
        content = await upload.read()
        if not content:
            raise _error(422, f"{upload.filename or 'file'} is empty")
        if len(content) > _MAX_FILE:
            raise _error(422, f"{upload.filename or 'file'} must be 15 MB or smaller")
        prepared.append((content, _mime(upload, content), upload.filename or ""))

    results = await asyncio.gather(
        *[
            _read_one(
                content=content,
                mime=mime,
                kind=kind,
                filename=filename,
                actor_user_id=_user.id,
            )
            for content, mime, filename in prepared
        ]
    )
    return {"kind": kind, "results": list(results)}
