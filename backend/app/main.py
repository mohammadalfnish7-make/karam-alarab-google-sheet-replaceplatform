import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.bootstrap import seed_admin
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.errors import AppError
from app.importer import import_workbook
from app.models import (  # noqa: F401
    AirCargo,
    AuditLog,
    Company,
    Customer,
    ExitRecord,
    ImportBatch,
    PdfDocument,
    PdfExtraction,
    SeaCargo,
    Supplier,
    User,
)
from app.routers import audit, auth, intake, lookups, pdf, records, users

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("karam")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    if settings.testing:
        Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if seed_admin(db):
            logger.info("Seeded admin user %s", settings.admin_email)
        excel = settings.excel_import_path.strip()
        if excel:
            path = Path(excel)
            if path.is_file():
                result = import_workbook(db, path)
                logger.info("Excel import %s", result)
            else:
                logger.warning("Excel import file not found: %s", excel)
    finally:
        db.close()
    yield


app = FastAPI(title="Karam Al Arab Load Plan", lifespan=lifespan)

origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(AppError)
async def app_error(_request, exc: AppError):
    return JSONResponse(status_code=exc.status, content=exc.body)


@app.get("/api/health")
def health():
    return {"ok": True}


app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(records.router, prefix="/api")
app.include_router(lookups.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(pdf.router, prefix="/api")
app.include_router(intake.router, prefix="/api")
