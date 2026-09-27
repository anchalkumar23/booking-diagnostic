"""FastAPI application entrypoint."""
import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.database import Base, engine
from app.logging_config import configure_logging
from app.routers import auth, bookings, centres, payments

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="EVE Healthcare Diagnostic Booking API", version="1.0.0")

# No Alembic for this assignment's scope -- create_all is idempotent and
# sufficient for a project this size. See README "What I'd improve".
Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(bookings.router)
app.include_router(payments.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("validation error on %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})


@app.get("/health")
def health():
    return {"status": "ok"}
