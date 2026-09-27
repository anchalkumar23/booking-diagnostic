"""Diagnostic centres & tests: public reads, authenticated writes."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user
from app.models import DiagnosticCentre, DiagnosticTest
from app.schemas import CentreCreate, CentreOut, TestCreate, TestOut

router = APIRouter(prefix="/centres", tags=["centres"])


@router.get("/", response_model=list[CentreOut])
def list_centres(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    limit = min(limit, 100)
    return (
        db.query(DiagnosticCentre)
        .options(joinedload(DiagnosticCentre.tests))
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{centre_id}", response_model=CentreOut)
def get_centre(centre_id: str, db: Session = Depends(get_db)):
    centre = db.get(DiagnosticCentre, centre_id)
    if centre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Centre not found")
    return centre


@router.post("/", response_model=CentreOut, status_code=status.HTTP_201_CREATED)
def create_centre(body: CentreCreate, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    centre = DiagnosticCentre(name=body.name, location=body.location)
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return centre


@router.post("/{centre_id}/tests", response_model=TestOut, status_code=status.HTTP_201_CREATED)
def add_test(
    centre_id: str, body: TestCreate, db: Session = Depends(get_db), _user=Depends(get_current_user)
):
    centre = db.get(DiagnosticCentre, centre_id)
    if centre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Centre not found")
    test = DiagnosticTest(centre_id=centre_id, name=body.name, price=body.price)
    db.add(test)
    db.commit()
    db.refresh(test)
    return test
