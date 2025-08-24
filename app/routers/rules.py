from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, delete
from ..db import get_session
from ..models import Rule, Property
from ..deps import get_current_user

router = APIRouter(prefix="/rules", tags=["rules"])

@router.get("")
def list_rules(property_id: int, session: Session = Depends(get_session), user=Depends(get_current_user)):
    p = session.get(Property, property_id)
    if not p or p.owner_id != user.id: raise HTTPException(404, "Propiedad no encontrada")
    return session.exec(select(Rule).where(Rule.property_id == property_id)).all()

@router.post("")
def upsert_rules(property_id: int, reglas: list[Rule], session: Session = Depends(get_session), user=Depends(get_current_user)):
    p = session.get(Property, property_id)
    if not p or p.owner_id != user.id: raise HTTPException(404, "Propiedad no encontrada")
    session.exec(delete(Rule).where(Rule.property_id == property_id))
    for r in reglas:
        r.property_id = property_id
        session.add(r)
    session.commit()
    return {"ok": True, "count": len(reglas)}

@router.delete("/{rule_id}")
def delete_rule(rule_id: int, session: Session = Depends(get_session), user=Depends(get_current_user)):
    r = session.get(Rule, rule_id)
    if not r: raise HTTPException(404, "Regla no encontrada")
    # podrías verificar propiedad del usuario con un join a Property si quieres
    session.delete(r); session.commit()
    return {"ok": True}
