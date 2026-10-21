from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


def _blank_to_none(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    return {key: (None if value == "" else value) for key, value in data.items()}


class LoginIn(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    email: str
    password: str
    role: str


class UserPatch(BaseModel):
    is_active: bool


class CargoIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    date_received: Any = None
    customer_code: Any = None
    company_name: Any = None
    cartons: Any = None
    gross_weight_kg: Any = None
    gross_is_no_pallet: Any = None
    gross: Any = None
    net_weight_kg: Any = None
    system_code: Any = None
    shipment_number: Any = None
    shipping_route: Any = None
    stage: Any = None
    status: Any = None
    confirm_new_customer: bool = False
    confirm_new_company: bool = False
    confirm_new_supplier: bool = False
    # Intake weight policy payload: originals, overrides, preferred totals, flags.
    intake_check: dict | None = None

    @model_validator(mode="before")
    @classmethod
    def blanks(cls, data):
        return _blank_to_none(data)


class ExitIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mark: Any = None
    supplier: Any = None
    invoice_no: Any = None
    invoice_numbers: Any = None
    cartons: Any = None
    date_of_submission: Any = None
    status: Any = None
    confirm_new_customer: bool = False
    confirm_new_company: bool = False
    confirm_new_supplier: bool = False

    @model_validator(mode="before")
    @classmethod
    def blanks(cls, data):
        return _blank_to_none(data)


class ExpiryDateIn(BaseModel):
    expiry_date: str | None = None


class PdfConfirm(BaseModel):
    rows: list[dict]
    confirm_new_customer: bool = False
    confirm_new_company: bool = False
    confirm_new_supplier: bool = False


class PromptUpdateIn(BaseModel):
    body: str
    note: str | None = None


class PromptRollbackIn(BaseModel):
    version: int


class AppSettingsIn(BaseModel):
    llm_model: str | None = None
    llm_timeout_sec: int | None = None


class ContainerLoadingIn(BaseModel):
    """Create/update payload for standalone container loading rows."""

    model_config = ConfigDict(extra="ignore")

    mark: Any = None
    container_no: Any = None
    container_row_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def blanks(cls, data):
        return _blank_to_none(data)


class ContainerLoadingPlanIn(BaseModel):
    """In-app loading plan editor payload (JSON, not Excel)."""

    model_config = ConfigDict(extra="ignore")

    container_number: Any = None
    filename: Any = None
    lines: list[dict[str, Any]] = []


class LoadingInvoiceIn(BaseModel):
    """Create / patch loading invoice header + link."""

    model_config = ConfigDict(extra="ignore")

    ref: Any = None
    container_loading_id: Any = None
    container_no: Any = None
    invoice_date: Any = None

    @model_validator(mode="before")
    @classmethod
    def blanks(cls, data):
        return _blank_to_none(data)


class LoadingInvoicePut(BaseModel):
    """Full invoice save from the in-app editor."""

    model_config = ConfigDict(extra="ignore")

    ref: Any = None
    container_loading_id: Any = None
    container_no: Any = None
    invoice_date: Any = None
    coo_line: Any = None
    title: Any = None
    plate_line: Any = None
    filename: Any = None
    lines: list[dict[str, Any]] = []


class ExpenseIn(BaseModel):
    """Create/update payload for Qusai expenses."""

    model_config = ConfigDict(extra="ignore")

    mark: Any = None
    date: Any = None
    amount: Any = None
    currency: Any = None
    notes: Any = None

    @model_validator(mode="before")
    @classmethod
    def blanks(cls, data):
        return _blank_to_none(data)


class AirShipmentPictureIn(BaseModel):
    """Create/update payload for standalone air shipment pictures."""

    model_config = ConfigDict(extra="ignore")

    number: Any = None
    date: Any = None
    cartons: Any = None

    @model_validator(mode="before")
    @classmethod
    def blanks(cls, data):
        return _blank_to_none(data)


class ImageInvoiceIn(BaseModel):
    """Create / patch image invoice header."""

    model_config = ConfigDict(extra="ignore")

    title: Any = None

    @model_validator(mode="before")
    @classmethod
    def blanks(cls, data):
        return _blank_to_none(data)


class ImageInvoiceLinesPut(BaseModel):
    """Save all product lines from the editor."""

    model_config = ConfigDict(extra="ignore")

    lines: list[dict[str, Any]] = []


class ImageInvoiceExtractIn(BaseModel):
    """Options for model-base extract on a line."""

    model_config = ConfigDict(extra="ignore")

    overwrite: bool = False
    file_ids: list[int] | None = None


class ImageInvoiceExportIn(BaseModel):
    """Excel export options; filename is the download name (optional .xlsx)."""

    model_config = ConfigDict(extra="ignore")

    filename: Any = None

    @model_validator(mode="before")
    @classmethod
    def blanks(cls, data):
        return _blank_to_none(data)


class SheetRowIn(BaseModel):
    """Loose payload for container-tracker sheets (extra keys ignored)."""

    model_config = ConfigDict(extra="ignore")

    date: Any = None
    inv_no: Any = None
    qr: Any = None
    previous_cont: Any = None
    container_no: Any = None
    kgs: Any = None
    carton: Any = None
    driver_name: Any = None
    driver_contact: Any = None
    info: Any = None
    notes: Any = None
    foreign_invoice: Any = None
    russian_instrct: Any = None
    supplier_buyer: Any = None
    status: Any = None
    stage: Any = None
    ref_no: Any = None
    vendor: Any = None
    airline: Any = None
    item: Any = None
    cartons: Any = None
    weight_kg: Any = None
    awb: Any = None
    comment: Any = None
    sr: Any = None
    inv_number: Any = None
    kjs: Any = None
    grg: Any = None
    k_exit: Any = None
    day: Any = None
    narrow: Any = None
    wide: Any = None
    column_1: Any = None
    extra_json: Any = None

    @model_validator(mode="before")
    @classmethod
    def blanks(cls, data):
        return _blank_to_none(data)
