# app/routers/rental_contracts.py
import os
import uuid
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session, select
from pydantic import BaseModel

from ..db import get_session
from ..deps import get_current_user
from ..models import User, Property, RentalContract, TenantDocument

router = APIRouter(prefix="/rental-contracts", tags=["rental-contracts"])

# Pydantic models
class RentalContractCreate(BaseModel):
    property_id: int
    tenant_name: str
    start_date: date
    end_date: Optional[date] = None
    monthly_rent: float
    deposit: Optional[float] = None
    tenant_email: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_dni: Optional[str] = None
    tenant_address: Optional[str] = None
    monthly_income: Optional[float] = None
    job_position: Optional[str] = None
    employer_name: Optional[str] = None

class RentalContractUpdate(BaseModel):
    tenant_name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    monthly_rent: Optional[float] = None
    deposit: Optional[float] = None
    is_active: Optional[bool] = None
    tenant_email: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_dni: Optional[str] = None
    tenant_address: Optional[str] = None
    monthly_income: Optional[float] = None
    job_position: Optional[str] = None
    employer_name: Optional[str] = None

class RentalContractResponse(BaseModel):
    id: int
    property_id: int
    tenant_name: str
    start_date: date
    end_date: Optional[date] = None
    monthly_rent: float
    deposit: Optional[float] = None
    contract_pdf_path: Optional[str] = None
    contract_file_name: Optional[str] = None
    is_active: bool
    tenant_email: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_dni: Optional[str] = None
    tenant_address: Optional[str] = None
    monthly_income: Optional[float] = None
    job_position: Optional[str] = None
    employer_name: Optional[str] = None

class TenantDocumentResponse(BaseModel):
    id: int
    rental_contract_id: int
    document_type: str
    document_name: str
    file_path: str
    file_size: Optional[int] = None
    upload_date: date
    description: Optional[str] = None

@router.get("/", response_model=List[RentalContractResponse])
def get_rental_contracts(
    property_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get rental contracts with optional filters"""
    query = select(RentalContract).join(Property).where(Property.owner_id == current_user.id)
    
    if property_id:
        query = query.where(RentalContract.property_id == property_id)
    if is_active is not None:
        query = query.where(RentalContract.is_active == is_active)
    
    contracts = session.exec(query).all()
    return contracts

@router.post("/", response_model=RentalContractResponse)
def create_rental_contract(
    contract_data: RentalContractCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new rental contract"""
    # Verify property ownership
    property_obj = session.get(Property, contract_data.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Property not found")
    
    contract = RentalContract(**contract_data.dict())
    session.add(contract)
    session.commit()
    session.refresh(contract)
    return contract

@router.get("/{contract_id}", response_model=RentalContractResponse)
def get_rental_contract(
    contract_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get a specific rental contract"""
    contract = session.get(RentalContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Verify ownership through property
    property_obj = session.get(Property, contract.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    return contract

@router.put("/{contract_id}", response_model=RentalContractResponse)
def update_rental_contract(
    contract_id: int,
    contract_data: RentalContractUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update a rental contract"""
    contract = session.get(RentalContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Verify ownership
    property_obj = session.get(Property, contract.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Update fields
    for field, value in contract_data.dict(exclude_unset=True).items():
        setattr(contract, field, value)
    
    session.commit()
    session.refresh(contract)
    return contract

@router.delete("/{contract_id}")
def delete_rental_contract(
    contract_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a rental contract"""
    contract = session.get(RentalContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Verify ownership
    property_obj = session.get(Property, contract.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    session.delete(contract)
    session.commit()
    return {"message": "Contract deleted successfully"}

@router.post("/{contract_id}/upload-pdf")
def upload_contract_pdf(
    contract_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Upload PDF contract file"""
    contract = session.get(RentalContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Verify ownership
    property_obj = session.get(Property, contract.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Save file (implement your file storage logic here)
    import os
    from pathlib import Path
    
    upload_dir = Path("data/assets/contracts")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_dir / f"contract_{contract_id}_{file.filename}"
    
    with open(file_path, "wb") as buffer:
        content = file.file.read()
        buffer.write(content)
    
    # Update contract with file info
    contract.contract_pdf_path = str(file_path)
    contract.contract_file_name = file.filename
    session.commit()
    
    return {"message": "PDF uploaded successfully", "file_path": str(file_path)}

@router.get("/{contract_id}/download-pdf")
def download_contract_pdf(
    contract_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Download contract PDF"""
    from fastapi.responses import FileResponse
    import os
    
    contract = session.get(RentalContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Verify ownership
    property_obj = session.get(Property, contract.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    if not contract.contract_pdf_path or not os.path.exists(contract.contract_pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found")
    
    return FileResponse(
        path=contract.contract_pdf_path,
        filename=contract.contract_file_name or "contract.pdf",
        media_type="application/pdf"
    )

@router.get("/property/{property_id}/active", response_model=Optional[RentalContractResponse])
def get_active_contract_for_property(
    property_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get the active rental contract for a property"""
    # Verify property ownership
    property_obj = session.get(Property, property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Property not found")
    
    query = select(RentalContract).where(
        RentalContract.property_id == property_id,
        RentalContract.is_active == True
    )
    
    contract = session.exec(query).first()
    return contract

@router.get("/property/{property_id}/history", response_model=List[RentalContractResponse])
def get_rental_history_for_property(
    property_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get all rental contracts (history) for a property"""
    # Verify property ownership
    property_obj = session.get(Property, property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Property not found")
    
    query = select(RentalContract).where(
        RentalContract.property_id == property_id
    ).order_by(RentalContract.start_date.desc())
    
    contracts = session.exec(query).all()
    return contracts

# Configuración de uploads para documentos de inquilinos
TENANT_UPLOAD_DIR = "uploads/tenant_documents"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx"}

def ensure_upload_dir():
    """Asegura que el directorio de uploads exista"""
    os.makedirs(TENANT_UPLOAD_DIR, exist_ok=True)

def get_file_extension(filename: str) -> str:
    """Obtiene la extensión del archivo"""
    return os.path.splitext(filename)[1].lower()

def is_allowed_file(filename: str) -> bool:
    """Verifica si el archivo tiene una extensión permitida"""
    return get_file_extension(filename) in ALLOWED_EXTENSIONS

# Tenant Documents Endpoints
@router.get("/{contract_id}/documents", response_model=List[TenantDocumentResponse])
def get_tenant_documents(
    contract_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get all documents for a rental contract"""
    contract = session.get(RentalContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Verify ownership
    property_obj = session.get(Property, contract.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    documents = session.exec(
        select(TenantDocument)
        .where(TenantDocument.rental_contract_id == contract_id)
        .order_by(TenantDocument.upload_date.desc())
    ).all()
    
    return documents

@router.post("/{contract_id}/documents", response_model=TenantDocumentResponse)
async def upload_tenant_document(
    contract_id: int,
    document_type: str = Form(...),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Upload a document for a tenant"""
    # Verify contract ownership
    contract = session.get(RentalContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    property_obj = session.get(Property, contract.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")
    
    if not is_allowed_file(file.filename):
        raise HTTPException(
            status_code=400, 
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content to check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    
    # Reset file pointer
    await file.seek(0)
    
    # Generate unique filename
    file_extension = get_file_extension(file.filename)
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(TENANT_UPLOAD_DIR, unique_filename)
    
    # Ensure upload directory exists
    ensure_upload_dir()
    
    # Save file
    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Create database record
    document = TenantDocument(
        rental_contract_id=contract_id,
        document_type=document_type,
        document_name=file.filename,
        file_path=file_path,
        file_size=len(content),
        description=description
    )
    
    session.add(document)
    session.commit()
    session.refresh(document)
    
    return document

@router.delete("/{contract_id}/documents/{document_id}")
def delete_tenant_document(
    contract_id: int,
    document_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a tenant document"""
    # Verify contract ownership
    contract = session.get(RentalContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    property_obj = session.get(Property, contract.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Get and delete document
    document = session.get(TenantDocument, document_id)
    if not document or document.rental_contract_id != contract_id:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete physical file
    try:
        if os.path.exists(document.file_path):
            os.remove(document.file_path)
    except Exception as e:
        print(f"Warning: Failed to delete file {document.file_path}: {e}")
    
    # Delete database record
    session.delete(document)
    session.commit()
    
    return {"message": "Document deleted successfully"}

@router.get("/{contract_id}/documents/{document_id}/download")
async def download_tenant_document(
    contract_id: int,
    document_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Download a tenant document"""
    from fastapi.responses import FileResponse
    
    # Verify contract ownership
    contract = session.get(RentalContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    property_obj = session.get(Property, contract.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Get document
    document = session.get(TenantDocument, document_id)
    if not document or document.rental_contract_id != contract_id:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if file exists
    if not os.path.exists(document.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=document.file_path,
        filename=document.document_name,
        media_type='application/octet-stream'
    )