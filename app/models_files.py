# app/models_files.py
from sqlmodel import Field, SQLModel
from typing import Optional
from datetime import datetime

class FileStorage(SQLModel, table=True):
    """Store files in database as Base64"""
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    content_type: str
    file_data: str  # Base64 encoded file content
    file_size: int
    property_id: Optional[int] = None
    file_type: str  # 'photo', 'document', 'tenant-document'
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[int] = None
    
class PropertyPhoto(SQLModel, table=True):
    """Property photos with Base64 data"""
    id: Optional[int] = Field(default=None, primary_key=True)
    property_id: int
    photo_url: str  # Will be an API endpoint
    photo_data: str  # Base64 encoded image
    is_primary: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)