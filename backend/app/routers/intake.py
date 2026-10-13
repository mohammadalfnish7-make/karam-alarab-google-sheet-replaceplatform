from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.check_read import read_check_file
from app.deps import get_current_user
from app.errors import AppError
from app.models import User

router = APIRouter(prefix="/intake", tags=["intake"])

_MAX_FILE = 15 * 1024 * 1024
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
    fields = read_check_file(content, _mime(file, content), kind)
    return {"kind": kind, "filename": file.filename or "", "fields": fields}
