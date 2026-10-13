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

    @model_validator(mode="before")
    @classmethod
    def blanks(cls, data):
        return _blank_to_none(data)


class ExitIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mark: Any = None
    supplier: Any = None
    invoice_no: Any = None
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


class PdfConfirm(BaseModel):
    rows: list[dict]
    confirm_new_customer: bool = False
    confirm_new_company: bool = False
    confirm_new_supplier: bool = False
