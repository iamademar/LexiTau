from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, schemas
from ..dependencies import get_db, get_current_user

router = APIRouter(
    tags=["Tags"],
    responses={404: {"description": "Not found"}},
)


@router.post("/clients", response_model=schemas.Client)
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


@router.get("/clients", response_model=List[schemas.Client])
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


@router.post("/projects", response_model=schemas.Project)
def create_project(
    project: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Create a new project for the current user's business"""
    # Check if project with the same name already exists for this business
    existing_project = db.query(models.Project).filter(
        models.Project.business_id == current_user.business_id,
        models.Project.name == project.name
    ).first()
    
    if existing_project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project with this name already exists for your business"
        )
    
    # Create new project
    db_project = models.Project(
        name=project.name,
        business_id=current_user.business_id
    )
    
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    return db_project


@router.get("/projects", response_model=List[schemas.Project])
def list_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """List all projects for the current user's business"""
    # Query projects scoped to the user's business
    projects = db.query(models.Project).filter(
        models.Project.business_id == current_user.business_id
    ).order_by(models.Project.name).all()
    
    return projects


@router.get("/categories", response_model=List[schemas.Category])
def list_categories(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """List all available categories"""
    # Categories are global, but still require authentication
    categories = db.query(models.Category).order_by(models.Category.name).all()
    return categories