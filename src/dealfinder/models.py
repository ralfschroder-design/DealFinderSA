from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    CAR = "car"
    BIKE = "bike"
    BOAT = "boat"
    JETSKI = "jetski"


class SellerType(str, Enum):
    DEALER = "dealer"
    PRIVATE = "private"
    UNKNOWN = "unknown"


class ListingStatus(str, Enum):
    ACTIVE = "active"
    SOLD = "sold"
    REMOVED = "removed"


class Listing(BaseModel):
    source_key: str
    source_listing_id: str
    url: str
    category: Category
    title: str | None = None
    make: str | None = None
    model: str | None = None
    variant: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    price_zar: int | None = Field(default=None, ge=0)
    mileage_km: int | None = Field(default=None, ge=0)
    engine_hours: int | None = Field(default=None, ge=0)
    province: str | None = None
    town: str | None = None
    lat: float | None = None
    lng: float | None = None
    seller_type: SellerType = SellerType.UNKNOWN
    seller_name: str | None = None
    seller_phone: str | None = None
    description: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    posted_at: datetime | None = None
    status: ListingStatus = ListingStatus.ACTIVE
    is_valid: bool = True
    quality_flags: list[str] = Field(default_factory=list)
    fingerprint: str | None = None
    raw: dict | None = None


class ValidityResult(BaseModel):
    is_valid: bool
    flags: list[str] = Field(default_factory=list)


class RunStats(BaseModel):
    source_keys: list[str] = Field(default_factory=list)
    fetched: int = 0
    upserted: int = 0
    invalid: int = 0
    price_points: int = 0
    errors: list[str] = Field(default_factory=list)
