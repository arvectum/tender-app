from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ParsedPurchaseItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    position_external_id: str | None = None
    name: str
    description: str | None = None
    okpd2: str | None = None
    quantity: Decimal
    unit: str | None = None
    max_unit_price: Decimal | None = None
    max_total_price: Decimal | None = None
    delivery_region: str | None = None
    delivery_address: str | None = None
    delivery_terms: str | None = None
    raw_payload: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("quantity must be positive")
        return value


class ParsedPurchase(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str
    external_id: str
    title: str | None = None
    url: str | None = None
    status: str | None = None
    region: str | None = None
    customer_name: str | None = None
    submission_deadline: datetime | None = None
    commission_fee_amount: Decimal | None = None
    security_amount: Decimal | None = None
    max_total_price: Decimal | None = None
    created_at_source: datetime | None = None
    items: list[ParsedPurchaseItem] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] | None = None

    @field_validator("source", "external_id")
    @classmethod
    def validate_required_strings(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("field cannot be empty")
        return cleaned


class ConnectorResult(BaseModel):
    source: str
    purchases: list[ParsedPurchase] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BasePurchaseConnector:
    source: str

    def fetch_active_purchases(
        self,
        status: str = "Прием предложений",
        limit: int | None = None,
    ) -> list[ParsedPurchase]:
        raise NotImplementedError
