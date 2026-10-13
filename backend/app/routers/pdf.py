import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.audit import write_audit
from app.config import settings
from app.constants import ENTITY_TYPES
from app.deps import get_current_user, get_db
from app.errors import AppError
from app.models import PdfDocument, PdfExtraction, User
from app.pdf_service import gemini_extract, normalize_extracted_row, parse_model_json
from app.present import freeze
from app.records import apply_cargo, apply_exit
from app.schemas import PdfConfirm
from app.validation import validate_cargo, validate_exit

router = APIRouter(prefix="/pdf", tags=["pdf"])

_MAX_PDF = 15 * 1024 * 1024


def _error(status: int, message: str, **extra) -> AppError:
    body = {"message": message, "field_errors": extra.pop("field_errors", {}), "warnings": []}
    body.update(extra)
    return AppError(status, body)


def _shape(kind: str, values: dict) -> dict:
    frozen = freeze(values)
    if kind == "sea":
        frozen.pop("status", None)
    elif kind == "air":
        frozen.pop("shipping_route", None)
        frozen.pop("stage", None)
    return frozen


def _preview(db: Session, kind: str, raw: dict) -> dict:
    if not isinstance(raw, dict):
        return {
            "values": {},
            "field_errors": {"_row": "Row was not an object"},
            "warnings": [],
            "code": None,
            "proposed": {},
        }
    if kind == "exit":
        result = validate_exit(
            db,
            raw,
            None,
            confirm_new_customer=False,
            confirm_new_supplier=False,
        )
    else:
        result = validate_cargo(
            db,
            kind,
            raw,
            None,
            confirm_new_customer=False,
            confirm_new_company=False,
        )
    return {
        "values": _shape(kind, result.values),
        "field_errors": result.field_errors,
        "warnings": result.warnings,
        "code": result.code,
        "proposed": result.proposed,
    }


@router.post("/upload")
async def upload_pdf(
    request: Request,
    target: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if target not in {"sea", "air", "exit"}:
        raise _error(422, "Target must be sea, air, or exit", field_errors={"target": "Target must be sea, air, or exit"})
    filename = file.filename or "upload.pdf"
    if not filename.lower().endswith(".pdf"):
        raise _error(422, "Upload a PDF file", field_errors={"file": "File must be a PDF"})
    content = await file.read()
    if not content:
        raise _error(422, "The file is empty", field_errors={"file": "The file is empty"})
    if len(content) > _MAX_PDF:
        raise _error(422, "PDF must be 15 MB or smaller", field_errors={"file": "PDF must be 15 MB or smaller"})
    if not content.startswith(b"%PDF"):
        raise _error(422, "File is not a PDF", field_errors={"file": "File is not a PDF"})
    folder = Path(settings.upload_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{uuid.uuid4().hex}.pdf"
    stored.write_bytes(content)
    document = PdfDocument(
        target=target,
        original_filename=filename,
        stored_path=str(stored.resolve()),
        uploaded_by=user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(document)
    db.flush()
    write_audit(
        db,
        actor_user_id=user.id,
        action="pdf_upload",
        entity_type="pdf_document",
        entity_id=document.id,
        before=None,
        after={"target": target, "filename": filename},
        changed=[{"field": "filename", "old": None, "new": filename}],
        request=request,
    )
    db.commit()
    return {
        "id": document.id,
        "target": document.target,
        "filename": document.original_filename,
        "created_at": document.created_at.isoformat(),
    }


@router.post("/{document_id}/extract")
def extract_pdf(
    document_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.get(PdfDocument, document_id)
    if document is None:
        raise AppError(404, {"message": "Not found"})
    path = Path(document.stored_path)
    if not path.is_file():
        raise AppError(404, {"message": "Stored PDF is missing"})
    raw_text = gemini_extract(path.read_bytes(), document.target, document.original_filename)
    extraction = PdfExtraction(
        document_id=document.id,
        raw_response=raw_text,
        created_by=user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(extraction)
    db.flush()
    try:
        rows = parse_model_json(raw_text)
    except ValueError:
        db.commit()
        raise AppError(
            422,
            {
                "message": "The model did not return JSON rows. The upload is kept.",
                "field_errors": {},
                "warnings": [],
                "extraction_id": extraction.id,
            },
        )
    rows = [normalize_extracted_row(document.target, row, document.original_filename) for row in rows]
    previews = [_preview(db, document.target, row) for row in rows]
    extraction.parsed_json = previews
    write_audit(
        db,
        actor_user_id=user.id,
        action="pdf_extract",
        entity_type="pdf_document",
        entity_id=document.id,
        before=None,
        after={"extraction_id": extraction.id, "row_count": len(previews)},
        changed=[],
        request=request,
    )
    db.commit()
    return {"document_id": document.id, "extraction_id": extraction.id, "rows": previews}


@router.post("/{document_id}/confirm")
def confirm_pdf(
    document_id: int,
    body: PdfConfirm,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.get(PdfDocument, document_id)
    if document is None:
        raise AppError(404, {"message": "Not found"})
    if document.confirmed_at is not None:
        raise AppError(409, {"message": "This PDF was already submitted", "field_errors": {}, "warnings": []})
    if not body.rows:
        raise _error(422, "Add at least one row")
    if len(body.rows) > 100:
        raise _error(422, "Submit at most 100 rows at a time")

    prepared = []
    row_errors = []
    for index, raw in enumerate(body.rows):
        if not isinstance(raw, dict):
            row_errors.append(
                {
                    "index": index,
                    "field_errors": {"_row": "Row was not an object"},
                    "warnings": [],
                    "code": None,
                    "proposed": {},
                }
            )
            continue
        flags = {
            "confirm_new_customer": bool(raw.get("confirm_new_customer", body.confirm_new_customer)),
            "confirm_new_company": bool(raw.get("confirm_new_company", body.confirm_new_company)),
            "confirm_new_supplier": bool(raw.get("confirm_new_supplier", body.confirm_new_supplier)),
        }
        if document.target == "exit":
            result = validate_exit(
                db,
                raw,
                None,
                confirm_new_customer=flags["confirm_new_customer"],
                confirm_new_supplier=flags["confirm_new_supplier"],
            )
        else:
            result = validate_cargo(
                db,
                document.target,
                raw,
                None,
                confirm_new_customer=flags["confirm_new_customer"],
                confirm_new_company=flags["confirm_new_company"],
            )
        if result.field_errors:
            row_errors.append(
                {
                    "index": index,
                    "field_errors": result.field_errors,
                    "warnings": result.warnings,
                    "code": result.code,
                    "proposed": result.proposed,
                }
            )
        else:
            prepared.append((index, result))
    if row_errors:
        raise AppError(422, {"field_errors": {}, "warnings": [], "row_errors": row_errors})

    created = []
    row_warnings = []
    for index, result in prepared:
        if document.target == "exit":
            row = apply_exit(db, result, user, request)
            created.append({"entity_type": "exit_record", "id": row.id})
        else:
            row = apply_cargo(db, document.target, result, user, request)
            created.append({"entity_type": ENTITY_TYPES[document.target], "id": row.id})
        row_warnings.append({"index": index, "warnings": result.warnings})

    document.confirmed_row_ids = created
    document.confirmed_at = datetime.now(timezone.utc)
    document.confirmed_by = user.id
    write_audit(
        db,
        actor_user_id=user.id,
        action="pdf_confirm",
        entity_type="pdf_document",
        entity_id=document.id,
        before=None,
        after={"created": created},
        changed=[{"field": "created", "old": None, "new": created}],
        request=request,
    )
    db.commit()
    return {"created": created, "warnings": row_warnings}
