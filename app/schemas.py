"""Pydantic request/response schemas."""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models import BookingStatus, PaymentStatus


# ---- Auth ----

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- Centres / Tests ----

class TestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    price: Decimal


class TestCreate(BaseModel):
    name: str
    price: Decimal = Field(gt=0)


class CentreCreate(BaseModel):
    name: str
    location: str


class CentreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    location: str
    tests: list[TestOut] = []


# ---- Bookings ----

class BookingCreate(BaseModel):
    test_id: str
    appointment_time: datetime


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    test_id: str
    centre_id: str
    appointment_time: datetime
    amount: Decimal
    status: BookingStatus
    created_at: datetime


# ---- Payments ----

class PaymentCreate(BaseModel):
    booking_id: str
    # Optional override so results are deterministic in tests/demos;
    # omitted in normal use, where the outcome is randomized.
    force_result: Optional[Literal["SUCCESS", "FAILED"]] = None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    booking_id: str
    status: PaymentStatus
    created_at: datetime


class WebhookPayload(BaseModel):
    event_id: str
    booking_id: str
    status: Literal["SUCCESS", "FAILED"]
