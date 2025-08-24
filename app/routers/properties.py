from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel
from ..db import get_session
from ..models import Property
from ..deps import get_current_user

router = APIRouter(prefix="/properties", tags=["properties"])

class PropertyCreate(BaseModel):
    address: str
    rooms: Optional[int] = None
    m2: Optional[int] = None
    photo: Optional[str] = None
    property_type: Optional[str] = None
    purchase_date: Optional[str] = None  # Accept as string from frontend
    purchase_price: Optional[float] = None
    appraisal_value: Optional[float] = None
    down_payment: Optional[float] = None
    acquisition_costs: Optional[float] = None
    renovation_costs: Optional[float] = None

class PropertyUpdate(BaseModel):
    address: Optional[str] = None
    rooms: Optional[int] = None
    m2: Optional[int] = None
    photo: Optional[str] = None
    property_type: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_price: Optional[float] = None
    appraisal_value: Optional[float] = None
    down_payment: Optional[float] = None
    acquisition_costs: Optional[float] = None
    renovation_costs: Optional[float] = None

@router.get("")
def list_properties(session: Session = Depends(get_session), user=Depends(get_current_user)):
    q = select(Property).where(Property.owner_id == user.id)
    return session.exec(q).all()

@router.post("")
def create_property(data: PropertyCreate, session: Session = Depends(get_session), user=Depends(get_current_user)):
    # Convert purchase_date string to date object if provided
    purchase_date_obj = None
    if data.purchase_date:
        try:
            purchase_date_obj = datetime.strptime(data.purchase_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, "Formato de fecha inválido. Use YYYY-MM-DD")
    
    # Create Property object with proper types
    property_obj = Property(
        owner_id=user.id,
        address=data.address,
        rooms=data.rooms,
        m2=data.m2,
        photo=data.photo,
        property_type=data.property_type,
        purchase_date=purchase_date_obj,
        purchase_price=data.purchase_price,
        appraisal_value=data.appraisal_value,
        down_payment=data.down_payment,
        acquisition_costs=data.acquisition_costs,
        renovation_costs=data.renovation_costs
    )
    
    session.add(property_obj); session.commit(); session.refresh(property_obj)
    return property_obj

@router.get("/{pid}")
def get_property(pid: int, session: Session = Depends(get_session), user=Depends(get_current_user)):
    p = session.get(Property, pid)
    if not p or p.owner_id != user.id: raise HTTPException(404, "No encontrado")
    return p

@router.put("/{pid}")
def update_property(pid: int, p: PropertyUpdate, session: Session = Depends(get_session), user=Depends(get_current_user)):
    cur = session.get(Property, pid)
    if not cur or cur.owner_id != user.id: raise HTTPException(404, "No encontrado")
    
    # Convert purchase_date string to date object if provided
    if p.purchase_date and isinstance(p.purchase_date, str):
        try:
            purchase_date_obj = datetime.strptime(p.purchase_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, "Formato de fecha inválido. Use YYYY-MM-DD")
    else:
        purchase_date_obj = p.purchase_date
    
    # Update only provided fields
    update_data = p.dict(exclude_unset=True)
    if 'purchase_date' in update_data:
        update_data['purchase_date'] = purchase_date_obj
    
    for k, v in update_data.items():
        setattr(cur, k, v)
    
    session.add(cur); session.commit(); session.refresh(cur)
    return cur

@router.delete("/{pid}")
def delete_property(pid: int, session: Session = Depends(get_session), user=Depends(get_current_user)):
    property_to_delete = session.get(Property, pid)
    if not property_to_delete or property_to_delete.owner_id != user.id:
        raise HTTPException(404, "Propiedad no encontrada")
    
    session.delete(property_to_delete)
    session.commit()
    return {"message": "Propiedad eliminada correctamente"}
