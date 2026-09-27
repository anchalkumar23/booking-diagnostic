"""Simulated payment processing + idempotent payment webhook."""
import hmac
import logging
import random

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Booking, BookingStatus, Payment, PaymentStatus, User, WebhookEvent
from app.schemas import PaymentCreate, PaymentOut, WebhookPayload

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)


def _apply_result(booking: Booking, payment: Payment, result: str) -> None:
    payment.status = PaymentStatus.SUCCESS if result == "SUCCESS" else PaymentStatus.FAILED
    # A user-cancelled booking stays cancelled; a late/failed payment doesn't resurrect it.
    if booking.status != BookingStatus.CANCELLED:
        booking.status = BookingStatus.CONFIRMED if result == "SUCCESS" else BookingStatus.FAILED


@router.post("/", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(
    body: PaymentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    booking = db.get(Booking, body.booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your booking")
    if booking.payment is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Payment already exists for this booking")
    if booking.status != BookingStatus.PENDING:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Booking is not payable (status={booking.status.value})"
        )

    result = body.force_result or random.choice(["SUCCESS", "FAILED"])
    payment = Payment(booking_id=booking.id, status=PaymentStatus.PENDING)
    _apply_result(booking, payment, result)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    logger.info("payment processed booking_id=%s result=%s", booking.id, result)
    return payment


@router.post("/webhook/", status_code=status.HTTP_200_OK)
def payment_webhook(
    body: WebhookPayload,
    db: Session = Depends(get_db),
    x_webhook_secret: str = Header(default=""),
):
    """Provider callback. Must tolerate exact-duplicate deliveries without
    double-applying state changes -- the unique constraint on event_id is the
    source of truth for "have we seen this before", checked both up front and
    again at commit time to close the race between two concurrent duplicates.

    Requires a shared-secret header so an unauthenticated caller can't force
    an arbitrary booking's status by guessing/obtaining its id -- checked
    with a constant-time comparison so the check itself isn't a timing oracle.
    """
    if not hmac.compare_digest(x_webhook_secret, settings.webhook_secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook secret")

    existing = db.query(WebhookEvent).filter(WebhookEvent.event_id == body.event_id).first()
    if existing is not None:
        logger.info("webhook event_id=%s already processed, skipping", body.event_id)
        return {"status": "already_processed", "event_id": body.event_id}

    booking = db.get(Booking, body.booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")

    payment = booking.payment
    if payment is None:
        payment = Payment(booking_id=booking.id, status=PaymentStatus.PENDING)
        db.add(payment)

    _apply_result(booking, payment, body.status)
    db.add(WebhookEvent(event_id=body.event_id, payload=body.model_dump()))

    try:
        db.commit()
    except IntegrityError:
        # Lost the race to a concurrent identical webhook delivery; treat as a no-op.
        db.rollback()
        logger.info("webhook event_id=%s hit duplicate-key race, skipping", body.event_id)
        return {"status": "already_processed", "event_id": body.event_id}

    logger.info("webhook processed event_id=%s booking_id=%s status=%s", body.event_id, booking.id, body.status)
    return {"status": "processed", "event_id": body.event_id, "booking_status": booking.status.value}
