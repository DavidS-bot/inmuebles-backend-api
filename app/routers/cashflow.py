# app/routers/cashflow.py
from datetime import date, datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..db import get_session
from ..models import Movement, Rule, Property
from ..deps import get_current_user

router = APIRouter(prefix="/cashflow", tags=["cashflow"])

def _normalize(s: str) -> str:
    return (s or "").casefold()

def _apply_rules(concept: str, rules: List[Rule]) -> Optional[str]:
    """
    Devuelve la categoría (str) si alguna regla matchea por substring.
    Si no hay match, devuelve None -> el movimiento se ignora en cashflow.
    """
    c = _normalize(concept)
    for r in rules:
        if _normalize(r.match_text) in c:
            return r.category  # p.ej. "mortgage", "rent", "tax", "insurance", "hoa", "other"
    return None

@router.get("/{property_id}")
def cashflow_property(
    property_id: int,
    from_: date = Query(..., alias="from"),
    to_: date = Query(..., alias="to"),
    session: Session = Depends(get_session),
    user = Depends(get_current_user),
):
    """
    Calcula cashflow neto de una propiedad en el rango [from, to].
    - Usa movimientos ya categorizados (movement.category) o aplica reglas substring.
    - Movimientos sin categoría tras reglas -> se IGNORAN (como pediste).
    """
    prop = session.get(Property, property_id)
    if not prop or prop.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")

    # Reglas de la propiedad
    rules = session.exec(
        select(Rule).where(Rule.property_id == property_id)
    ).all()

    # Movimientos del rango
    movs: List[Movement] = session.exec(
        select(Movement)
        .where(Movement.property_id == property_id)
        .where(Movement.date >= from_)
        .where(Movement.date <= to_)
    ).all()

    # Acumuladores por categoría
    expenses: Dict[str, float] = {
        "mortgage": 0.0,
        "tax": 0.0,
        "insurance": 0.0,
        "hoa": 0.0,
        "maintenance": 0.0,
        "management": 0.0,
        "utilities": 0.0,
        "other": 0.0,
    }
    income_total = 0.0

    used: List[dict] = []  # listado de movimientos usados en el cálculo

    for m in movs:
        # Si ya trae categoría, la usamos. Si no, aplicamos reglas.
        category = m.category or _apply_rules(m.concept, rules)
        if not category:
            # no mapeado -> ignorar
            continue

        amt = float(m.amount)  # positivo ingresos, negativo gastos (asumido)
        if amt >= 0:
            income_total += amt
        else:
            # Gasto: acumulamos en la categoría (si no existe, cae en "other")
            if category not in expenses:
                expenses["other"] += -amt
            else:
                expenses[category] += -amt

        used.append({
            "id": m.id,
            "date": m.date,
            "concept": m.concept,
            "amount": amt,
            "category": category,
        })

    expenses_total = sum(expenses.values())
    net = income_total - expenses_total

    return {
        "property_id": property_id,
        "period": {"from": from_.isoformat(), "to": to_.isoformat()},
        "income": round(income_total, 2),
        "expenses": {k: round(v, 2) for k, v in expenses.items()},
        "expenses_total": round(expenses_total, 2),
        "net_cashflow": round(net, 2),
        "movements_used": used,
    }

