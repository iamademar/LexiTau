from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, schemas
from ..dependencies import get_db, get_current_user

router = APIRouter(
    prefix="/clients",
    tags=["Clients"],
    responses={404: {"description": "Not found"}},
)


@router.post("", response_model=schemas.Client)
def create_client(
    client: schemas.ClientCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Create a new client for the current user's business"""
    # Check if client with the same name already exists for this business
    existing_client = db.query(models.Client).filter(
        models.Client.business_id == current_user.business_id,
        models.Client.name == client.name
    ).first()

    if existing_client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client with this name already exists for your business"
        )

    # Create new client
    db_client = models.Client(
        name=client.name,
        business_id=current_user.business_id
    )

    db.add(db_client)
    db.commit()
    db.refresh(db_client)

    return db_client


@router.get("", response_model=List[schemas.Client])
def list_clients(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """List all clients for the current user's business"""
    # Query clients scoped to the user's business
    clients = db.query(models.Client).filter(
        models.Client.business_id == current_user.business_id
    ).order_by(models.Client.name).all()

    return clients