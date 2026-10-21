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
from app.container_import import import_container_tracker
from app.expiry_import import import_document_expiry
from app.importer import import_workbook, repair_dates_after_today, repair_invoice_numbers
from app.models import (  # noqa: F401
    AgentRun,
    AirCargo,
    AirShipmentPicture,
    AirShipmentTrackerRow,
    AppSetting,
    AuditLog,
    CargoFile,
    Company,
    ContainerLoading,
    ContainerRow,
    CooRow,
    Expense,
    Customer,
    DocumentExpiry,
    ExitRecord,
    FlightScheduleRow,
    ImageInvoice,
    ImageInvoiceLine,
    ImportBatch,
    LoadingInvoice,
    PdfDocument,
    PdfExtraction,
    PromptKey,
    PromptVersion,
    RequestLog,
    SeaCargo,
    Supplier,
    User,
)
from app.request_log import RequestLogMiddleware
from app.routers import (
    agent_runs,
    air_shipment_pictures,
    audit,
    auth,
    container_loading,
    container_tracker,
    expenses,
    knowledge_graph,
    image_invoices,
    loading_invoices,
    expiry,
    intake,
    lookups,
    overview,
    pdf,
    records,
    request_logs,
    settings as settings_router,
    users,
)

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
        repaired = repair_dates_after_today(db)
        if repaired["received_corrected"] or repaired["exit_corrected"]:
            logger.info("Date repair %s", repaired)
        invoices = repair_invoice_numbers(db)
        if invoices["invoices_split"]:
            logger.info("Invoice repair %s", invoices)
        expiry_path = settings.document_expiry_path.strip()
        if expiry_path:
            path = Path(expiry_path)
            if path.is_file():
                result = import_document_expiry(db, path)
                logger.info("Document expiry import %s", result)
            else:
                logger.warning("Document expiry file not found: %s", expiry_path)
        tracker_path = settings.container_tracker_path.strip()
        if tracker_path:
            path = Path(tracker_path)
            if path.is_file():
                result = import_container_tracker(db, path)
                logger.info("Container tracker import %s", result)
            else:
                logger.warning("Container tracker file not found: %s", tracker_path)
    finally:
        db.close()
    yield


app = FastAPI(title="Karam Al Arab Load Plan", lifespan=lifespan)
app.add_middleware(RequestLogMiddleware)

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
app.include_router(overview.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(records.router, prefix="/api")
app.include_router(lookups.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(agent_runs.router, prefix="/api")
app.include_router(request_logs.router, prefix="/api")
app.include_router(pdf.router, prefix="/api")
app.include_router(intake.router, prefix="/api")
app.include_router(expiry.router, prefix="/api")
app.include_router(container_tracker.router, prefix="/api")
app.include_router(container_loading.router, prefix="/api")
app.include_router(loading_invoices.router, prefix="/api")
app.include_router(image_invoices.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(air_shipment_pictures.router, prefix="/api")
app.include_router(knowledge_graph.router, prefix="/api")
