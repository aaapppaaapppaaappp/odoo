import os
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


ODOO_BASE_URL = _required_env("ODOO_BASE_URL").rstrip("/")
ODOO_DATABASE = _required_env("ODOO_DATABASE")
ODOO_API_KEY = _required_env("ODOO_API_KEY")
ODOO_TIMEOUT_SECONDS = float(os.getenv("ODOO_TIMEOUT_SECONDS", "20"))
PROXY_BEARER_TOKEN = os.getenv("PROXY_BEARER_TOKEN", "").strip()

DEFAULT_LOOKUP_FIELDS = [
    "id",
    "partner_name",
    "email_from",
    "partner_phone",
    "job_id",
    "stage_id",
    "application_status",
    "create_date",
]

DEFAULT_CREATE_RETURN_FIELDS = [
    "id",
    "partner_name",
    "email_from",
    "partner_phone",
    "job_id",
    "stage_id",
    "application_status",
    "create_date",
]


class LookupRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    partner_name: str | None = None
    email_from: str | None = None
    partner_phone: str | None = None
    job_id: int | None = None
    include_archived: bool = False
    limit: int = Field(default=5, ge=1, le=100)
    order: str | None = None
    fields: list[str] | None = None

    @model_validator(mode="after")
    def _check_at_least_one_filter(self) -> "LookupRequest":
        if not any([self.partner_name, self.email_from, self.partner_phone, self.job_id]):
            raise ValueError("Provide at least one filter: partner_name, email_from, partner_phone, or job_id")
        return self


class CreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    partner_name: str = Field(min_length=1)
    email_from: str | None = None
    partner_phone: str | None = None
    linkedin_profile: str | None = None
    job_id: int | None = None
    stage_id: int | None = None
    user_id: int | None = None
    company_id: int | None = None
    source_id: int | None = None
    medium_id: int | None = None
    campaign_id: int | None = None
    type_id: int | None = None
    availability: str | None = None
    applicant_notes: str | None = None
    categ_ids: list[int] | None = None
    return_fields: list[str] | None = None


def _or_domain(conditions: list[list[Any]]) -> list[Any]:
    if not conditions:
        return []
    if len(conditions) == 1:
        return [conditions[0]]
    domain: list[Any] = ["|"] * (len(conditions) - 1)
    domain.extend(conditions)
    return domain


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def _require_proxy_token(authorization: str | None = Header(default=None)) -> None:
    if not PROXY_BEARER_TOKEN:
        return
    incoming = _extract_bearer_token(authorization)
    if incoming != PROXY_BEARER_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid proxy bearer token",
        )


async def _call_odoo(model: str, method: str, payload: dict[str, Any]) -> Any:
    url = f"{ODOO_BASE_URL}/json/2/{model}/{method}"
    headers = {
        "Authorization": f"Bearer {ODOO_API_KEY}",
        "X-Odoo-Database": ODOO_DATABASE,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=ODOO_TIMEOUT_SECONDS) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach Odoo: {exc}",
        ) from exc

    if response.status_code >= 400:
        detail: Any
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise HTTPException(
            status_code=response.status_code,
            detail=detail,
        )

    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Odoo returned non-JSON response: {response.text}",
        ) from exc


app = FastAPI(title="Odoo Applicant Proxy", version="1.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/applicants/lookup", dependencies=[Depends(_require_proxy_token)])
async def lookup_applicants(body: LookupRequest) -> dict[str, Any]:
    conditions: list[list[Any]] = []
    if body.partner_name:
        conditions.append(["partner_name", "ilike", body.partner_name])
    if body.email_from:
        conditions.append(["email_from", "ilike", body.email_from])
    if body.partner_phone:
        conditions.append(["partner_phone", "ilike", body.partner_phone])

    domain: list[Any] = _or_domain(conditions)
    if body.job_id is not None:
        domain.append(["job_id", "=", body.job_id])

    payload: dict[str, Any] = {
        "domain": domain,
        "fields": body.fields or DEFAULT_LOOKUP_FIELDS,
        "limit": body.limit,
    }
    if body.order:
        payload["order"] = body.order
    if body.include_archived:
        payload["context"] = {"active_test": False}

    result = await _call_odoo("hr.applicant", "search_read", payload)
    if not isinstance(result, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unexpected Odoo response type for lookup: {type(result).__name__}",
        )

    return {"count": len(result), "items": result}


@app.post("/api/applicants/create", dependencies=[Depends(_require_proxy_token)])
async def create_applicant(body: CreateRequest) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field_name in (
        "partner_name",
        "email_from",
        "partner_phone",
        "linkedin_profile",
        "job_id",
        "stage_id",
        "user_id",
        "company_id",
        "source_id",
        "medium_id",
        "campaign_id",
        "type_id",
        "availability",
        "applicant_notes",
    ):
        value = getattr(body, field_name)
        if value not in (None, ""):
            values[field_name] = value

    if body.categ_ids:
        # many2many set command
        values["categ_ids"] = [[6, 0, body.categ_ids]]

    create_result = await _call_odoo("hr.applicant", "create", {"vals_list": [values]})
    applicant_id: int | None = None
    if isinstance(create_result, list) and create_result:
        applicant_id = int(create_result[0])
    elif isinstance(create_result, int):
        applicant_id = create_result

    if not applicant_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unexpected Odoo response for create: {create_result}",
        )

    read_result = await _call_odoo(
        "hr.applicant",
        "search_read",
        {
            "domain": [["id", "=", applicant_id]],
            "fields": body.return_fields or DEFAULT_CREATE_RETURN_FIELDS,
            "limit": 1,
        },
    )

    record = read_result[0] if isinstance(read_result, list) and read_result else {"id": applicant_id}
    return {"id": applicant_id, "record": record}
