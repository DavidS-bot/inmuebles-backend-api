# app/routers/uploads.py
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Optional
import shutil
from ..deps import get_current_user

router = APIRouter(prefix="/uploads", tags=["uploads"])

# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

@router.post("/photo")
async def upload_photo(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    """Upload a photo for properties"""
    
    # Check file extension
    file_extension = Path(file.filename or "").suffix.lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido. Usa: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Check file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="El archivo es demasiado grande. Máximo 5MB"
        )
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename
    
    try:
        # Save file
        with open(file_path, "wb") as buffer:
            buffer.write(contents)
        
        # Return the file URL
        return {
            "url": f"/uploads/photo/{unique_filename}",
            "filename": unique_filename,
            "size": len(contents)
        }
    
    except Exception as e:
        # Clean up file if there was an error
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail="Error al guardar el archivo")

@router.get("/photo/{filename}")
async def get_photo(filename: str):
    """Serve uploaded photos"""
    file_path = UPLOAD_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    return FileResponse(
        path=file_path,
        media_type="image/*",
        headers={"Cache-Control": "max-age=31536000"}  # Cache for 1 year
    )

@router.delete("/photo/{filename}")
async def delete_photo(filename: str, user=Depends(get_current_user)):
    """Delete an uploaded photo"""
    file_path = UPLOAD_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    try:
        file_path.unlink()
        return {"message": "Archivo eliminado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error al eliminar el archivo")