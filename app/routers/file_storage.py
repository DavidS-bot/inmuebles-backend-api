# app/routers/file_storage.py
"""File storage using database instead of filesystem"""

import base64
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlmodel import Session, select
from typing import List, Optional
from pathlib import Path

from ..db import get_session
from ..deps import get_current_user
from ..models_files import FileStorage, PropertyPhoto

router = APIRouter(prefix="/files", tags=["file-storage"])

# File size limits
MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5MB
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10MB

# Allowed extensions
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}

@router.post("/upload/photo")
async def upload_photo_to_db(
    file: UploadFile = File(...),
    property_id: Optional[int] = None,
    session: Session = Depends(get_session),
    user=Depends(get_current_user)
):
    """Upload photo and store in database as Base64"""
    
    # Validate file extension
    file_extension = Path(file.filename or "").suffix.lower()
    if file_extension not in PHOTO_EXTENSIONS:
        raise HTTPException(400, f"Invalid file type. Allowed: {', '.join(PHOTO_EXTENSIONS)}")
    
    # Read and validate file size
    contents = await file.read()
    if len(contents) > MAX_PHOTO_SIZE:
        raise HTTPException(400, "File too large. Maximum 5MB")
    
    # Convert to Base64
    file_data_base64 = base64.b64encode(contents).decode('utf-8')
    
    # Create database record
    file_record = FileStorage(
        filename=file.filename or f"photo_{uuid.uuid4()}{file_extension}",
        content_type=file.content_type or "image/jpeg",
        file_data=file_data_base64,
        file_size=len(contents),
        property_id=property_id,
        file_type="photo",
        user_id=user.id
    )
    
    session.add(file_record)
    session.commit()
    session.refresh(file_record)
    
    # If property_id provided, also create PropertyPhoto record
    if property_id:
        property_photo = PropertyPhoto(
            property_id=property_id,
            photo_url=f"/files/photo/{file_record.id}",
            photo_data=file_data_base64,
            is_primary=False
        )
        session.add(property_photo)
        session.commit()
    
    return {
        "id": file_record.id,
        "filename": file_record.filename,
        "url": f"/files/photo/{file_record.id}",
        "size": file_record.file_size
    }

@router.post("/upload/document")
async def upload_document_to_db(
    file: UploadFile = File(...),
    document_type: str = "document",
    session: Session = Depends(get_session),
    user=Depends(get_current_user)
):
    """Upload document and store in database as Base64"""
    
    # Validate file extension
    file_extension = Path(file.filename or "").suffix.lower()
    if file_extension not in DOCUMENT_EXTENSIONS:
        raise HTTPException(400, f"Invalid file type. Allowed: {', '.join(DOCUMENT_EXTENSIONS)}")
    
    # Read and validate file size
    contents = await file.read()
    if len(contents) > MAX_DOCUMENT_SIZE:
        raise HTTPException(400, "File too large. Maximum 10MB")
    
    # Convert to Base64
    file_data_base64 = base64.b64encode(contents).decode('utf-8')
    
    # Create database record
    file_record = FileStorage(
        filename=file.filename or f"document_{uuid.uuid4()}{file_extension}",
        content_type=file.content_type or "application/pdf",
        file_data=file_data_base64,
        file_size=len(contents),
        file_type=document_type,
        user_id=user.id
    )
    
    session.add(file_record)
    session.commit()
    session.refresh(file_record)
    
    return {
        "id": file_record.id,
        "filename": file_record.filename,
        "url": f"/files/document/{file_record.id}",
        "size": file_record.file_size
    }

@router.get("/photo/{file_id}")
async def get_photo_from_db(
    file_id: int,
    session: Session = Depends(get_session)
):
    """Retrieve and serve photo from database"""
    
    # Get file from database
    file_record = session.get(FileStorage, file_id)
    if not file_record or file_record.file_type != "photo":
        raise HTTPException(404, "Photo not found")
    
    # Decode Base64
    file_data = base64.b64decode(file_record.file_data)
    
    # Return as image response
    return Response(
        content=file_data,
        media_type=file_record.content_type,
        headers={
            "Content-Disposition": f"inline; filename={file_record.filename}",
            "Cache-Control": "public, max-age=86400"  # Cache for 1 day
        }
    )

@router.get("/document/{file_id}")
async def get_document_from_db(
    file_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user)
):
    """Retrieve and serve document from database"""
    
    # Get file from database
    file_record = session.get(FileStorage, file_id)
    if not file_record or file_record.file_type not in ["document", "tenant-document"]:
        raise HTTPException(404, "Document not found")
    
    # Decode Base64
    file_data = base64.b64decode(file_record.file_data)
    
    # Return as file response
    return Response(
        content=file_data,
        media_type=file_record.content_type,
        headers={
            "Content-Disposition": f"attachment; filename={file_record.filename}"
        }
    )

@router.get("/property/{property_id}/photos")
async def get_property_photos(
    property_id: int,
    session: Session = Depends(get_session)
):
    """Get all photos for a property"""
    
    statement = select(PropertyPhoto).where(PropertyPhoto.property_id == property_id)
    photos = session.exec(statement).all()
    
    return [
        {
            "id": photo.id,
            "url": photo.photo_url,
            "is_primary": photo.is_primary
        }
        for photo in photos
    ]

@router.delete("/photo/{file_id}")
async def delete_photo(
    file_id: int,
    session: Session = Depends(get_session),
    user=Depends(get_current_user)
):
    """Delete photo from database"""
    
    file_record = session.get(FileStorage, file_id)
    if not file_record:
        raise HTTPException(404, "Photo not found")
    
    # Check permission
    if file_record.user_id != user.id:
        raise HTTPException(403, "Not authorized to delete this photo")
    
    session.delete(file_record)
    session.commit()
    
    return {"message": "Photo deleted successfully"}

@router.get("/list/{file_type}")
async def list_files(
    file_type: str,
    session: Session = Depends(get_session),
    user=Depends(get_current_user)
):
    """List all files of a specific type"""
    
    if file_type not in ["photo", "document", "tenant-document"]:
        raise HTTPException(400, "Invalid file type")
    
    statement = select(FileStorage).where(
        FileStorage.file_type == file_type,
        FileStorage.user_id == user.id
    )
    files = session.exec(statement).all()
    
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "url": f"/files/{file_type.replace('-', '/')}/{f.id}",
            "size": f.file_size,
            "created_at": f.created_at
        }
        for f in files
    ]