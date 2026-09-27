"""Booking endpoints. All require authentication; users only see their own bookings."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Booking, BookingStatus, DiagnosticTest, User
from app.schemas import BookingCreate, BookingOut

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("/", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    body: BookingCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    test = db.get(DiagnosticTest, body.test_id)
    if test is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diagnostic test not found")

    appointment_time = body.appointment_time
    if appointment_time.tzinfo is None:
        appointment_time = appointment_time.replace(tzinfo=timezone.utc)
    if appointment_time <= datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Appointment time must be in the future")

    # Amount is always the server's current price for the test, never client-supplied.
    booking = Booking(
        user_id=user.id,
        test_id=test.id,
        centre_id=test.centre_id,
        appointment_time=appointment_time,
        amount=test.price,
        status=BookingStatus.PENDING,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


@router.get("/", response_model=list[BookingOut])
def list_my_bookings(
    skip: int = 0, limit: int = 20, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    limit = min(limit, 100)
    return (
        db.query(Booking)
        .filter(Booking.user_id == user.id)
        .order_by(Booking.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def _get_owned_booking(booking_id: str, db: Session, user: User) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your booking")
    return booking


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_booking(booking_id, db, user)


@router.patch("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(booking_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    booking = _get_owned_booking(booking_id, db, user)
    if booking.status not in (BookingStatus.PENDING, BookingStatus.CONFIRMED):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Cannot cancel a booking with status {booking.status.value}"
        )
    booking.status = BookingStatus.CANCELLED
    db.commit()
    db.refresh(booking)
    return booking
