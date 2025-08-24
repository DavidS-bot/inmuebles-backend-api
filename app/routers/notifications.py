# app/routers/notifications.py
from fastapi import APIRouter, Depends
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
from sqlmodel import Session, select
from pydantic import BaseModel
from ..db import get_session
from ..deps import get_current_user
from ..models import Property, RentalContract, FinancialMovement, MortgageDetails, EuriborRate
import statistics

router = APIRouter(prefix="/notifications", tags=["notifications"])

class NotificationRule(BaseModel):
    type: str  # "payment_due", "unusual_expense", "contract_expiring", "savings_opportunity"
    threshold: Optional[float] = None
    enabled: bool = True
    email_enabled: bool = False
    sms_enabled: bool = False

class Notification(BaseModel):
    id: str
    type: str
    title: str
    message: str
    priority: str  # "high", "medium", "low"
    property_id: Optional[int] = None
    amount: Optional[float] = None
    due_date: Optional[date] = None
    action_url: Optional[str] = None
    created_at: datetime
    read: bool = False

@router.get("/alerts")
def get_active_notifications(
    session: Session = Depends(get_session)
):
    """Obtener todas las notificaciones activas del usuario"""
    
    # Simulación de notificaciones (sin autenticación para demo)
    notifications = [
        {
            "id": "notif_001",
            "type": "warning",
            "title": "Pago de alquiler pendiente",
            "description": "El inquilino del Piso en Calle Mayor, 45 no ha pagado el alquiler de agosto",
            "created_at": "2025-08-20T10:30:00",
            "property_id": 1,
            "amount": 850.0,
            "due_date": "2025-08-01",
            "actions": ["Contactar inquilino", "Enviar requerimiento"]
        },
        {
            "id": "notif_002",
            "type": "info", 
            "title": "Renovación de seguro próxima",
            "description": "El seguro de hogar de la propiedad en Av. Andalucía vence en 30 días",
            "created_at": "2025-08-19T15:45:00",
            "property_id": 2,
            "due_date": "2025-09-20",
            "actions": ["Renovar seguro", "Comparar ofertas"]
        },
        {
            "id": "notif_003",
            "type": "success",
            "title": "Oportunidad de ahorro detectada", 
            "description": "Puedes ahorrar €120/año cambiando de compañía eléctrica en la propiedad de C/ Larga",
            "created_at": "2025-08-18T09:15:00",
            "property_id": 3,
            "amount": 120.0,
            "actions": ["Ver ofertas", "Cambiar compañía"]
        },
        {
            "id": "notif_004",
            "type": "critical",
            "title": "IBI vencido - Recargo por demora",
            "description": "El IBI del segundo trimestre está vencido y generará recargos",
            "created_at": "2025-08-17T12:00:00",
            "property_id": 1,
            "amount": 290.0,
            "due_date": "2025-07-31", 
            "actions": ["Pagar urgente", "Gestionar recargo"]
        }
    ]
    
    return {
        "notifications": notifications,
        "total": len(notifications),
        "by_type": {
            "critical": len([n for n in notifications if n["type"] == "critical"]),
            "warning": len([n for n in notifications if n["type"] == "warning"]),
            "info": len([n for n in notifications if n["type"] == "info"]),
            "success": len([n for n in notifications if n["type"] == "success"])
        }
    }

@router.get("/stats")
def get_notification_stats(
    session: Session = Depends(get_session)
):
    """Estadísticas de notificaciones"""
    
    return {
        "total_alerts": 4,
        "critical_alerts": 1,
        "potential_savings": 120,
        "overdue_payments": 2
    }

@router.get("/original-alerts")
def get_original_notifications(
    session: Session = Depends(get_session)
):
    """Obtener propiedades del usuario (implementación original)"""
    notifications = []
    today = date.today()
    
    # Obtener propiedades del usuario
    properties = session.exec(select(Property)).all()
    
    for prop in properties:
        # 1. Contratos próximos a vencer
        contracts = session.exec(
            select(RentalContract)
            .where(RentalContract.property_id == prop.id)
            .where(RentalContract.is_active == True)
        ).all()
        
        for contract in contracts:
            if contract.end_date:
                days_until_expiry = (contract.end_date - today).days
                
                if 0 <= days_until_expiry <= 30:
                    notifications.append(Notification(
                        id=f"contract_expiry_{contract.id}",
                        type="contract_expiring",
                        title="Contrato próximo a vencer",
                        message=f"El contrato de {contract.tenant_name} en {prop.address} vence en {days_until_expiry} días",
                        priority="high" if days_until_expiry <= 7 else "medium",
                        property_id=prop.id,
                        due_date=contract.end_date,
                        action_url=f"/financial-agent/contracts",
                        created_at=datetime.now(),
                        read=False
                    ))
        
        # 2. Pagos de renta pendientes (detectar si no hay ingresos en los últimos 35 días)
        last_month = today - timedelta(days=35)
        recent_rent_payments = session.exec(
            select(FinancialMovement)
            .where(FinancialMovement.property_id == prop.id)
            .where(FinancialMovement.category == "Renta")
            .where(FinancialMovement.amount > 0)
            .where(FinancialMovement.date >= last_month)
        ).all()
        
        active_contract = session.exec(
            select(RentalContract)
            .where(RentalContract.property_id == prop.id)
            .where(RentalContract.is_active == True)
        ).first()
        
        if active_contract and not recent_rent_payments:
            notifications.append(Notification(
                id=f"missing_rent_{prop.id}",
                type="payment_due",
                title="Posible pago de renta pendiente",
                message=f"No se ha registrado pago de renta en {prop.address} en los últimos 35 días",
                priority="high",
                property_id=prop.id,
                amount=active_contract.monthly_rent,
                action_url=f"/financial-agent/property/{prop.id}",
                created_at=datetime.now(),
                read=False
            ))
        
        # 3. Gastos inusuales (gastos 3x superiores al promedio mensual)
        six_months_ago = today - timedelta(days=180)
        expenses = session.exec(
            select(FinancialMovement)
            .where(FinancialMovement.property_id == prop.id)
            .where(FinancialMovement.amount < 0)
            .where(FinancialMovement.date >= six_months_ago)
        ).all()
        
        if expenses:
            monthly_expenses = {}
            for expense in expenses:
                month_key = f"{expense.date.year}-{expense.date.month:02d}"
                if month_key not in monthly_expenses:
                    monthly_expenses[month_key] = 0
                monthly_expenses[month_key] += abs(expense.amount)
            
            if len(monthly_expenses) >= 3:
                avg_monthly_expense = statistics.mean(monthly_expenses.values())
                current_month = f"{today.year}-{today.month:02d}"
                current_month_expense = monthly_expenses.get(current_month, 0)
                
                if current_month_expense > avg_monthly_expense * 2.5:
                    notifications.append(Notification(
                        id=f"unusual_expense_{prop.id}",
                        type="unusual_expense",
                        title="Gastos inusuales detectados",
                        message=f"Los gastos de {prop.address} este mes (€{current_month_expense:.0f}) superan significativamente el promedio (€{avg_monthly_expense:.0f})",
                        priority="medium",
                        property_id=prop.id,
                        amount=current_month_expense - avg_monthly_expense,
                        action_url=f"/financial-agent/property/{prop.id}",
                        created_at=datetime.now(),
                        read=False
                    ))
        
        # 4. Oportunidades de ahorro en hipoteca
        mortgage = session.exec(
            select(MortgageDetails).where(MortgageDetails.property_id == prop.id)
        ).first()
        
        if mortgage:
            # Obtener tasa Euribor actual
            latest_euribor = session.exec(
                select(EuriborRate).order_by(EuriborRate.date.desc())
            ).first()
            
            if latest_euribor:
                current_rate = latest_euribor.rate_12m + mortgage.margin_percentage
                
                # Si la tasa actual es significativamente menor que hace 12 meses
                year_ago_euribor = session.exec(
                    select(EuriborRate)
                    .where(EuriborRate.date <= today - timedelta(days=365))
                    .order_by(EuriborRate.date.desc())
                ).first()
                
                if year_ago_euribor:
                    old_rate = year_ago_euribor.rate_12m + mortgage.margin_percentage
                    rate_diff = old_rate - current_rate
                    
                    if rate_diff > 0.5:  # Si la diferencia es mayor a 0.5%
                        monthly_savings = mortgage.outstanding_balance * (rate_diff / 100) / 12
                        notifications.append(Notification(
                            id=f"refinance_opportunity_{prop.id}",
                            type="savings_opportunity",
                            title="Oportunidad de refinanciación",
                            message=f"Los tipos han bajado {rate_diff:.2f}%. Podrías ahorrar €{monthly_savings:.0f}/mes refinanciando la hipoteca de {prop.address}",
                            priority="low",
                            property_id=prop.id,
                            amount=monthly_savings * 12,
                            action_url=f"/financial-agent/mortgage-calculator",
                            created_at=datetime.now(),
                            read=False
                        ))
        
        # 5. Revisiones de hipoteca próximas
        if mortgage:
            # Calcular próxima revisión (cada 12 meses desde start_date)
            months_since_start = (today.year - mortgage.start_date.year) * 12 + (today.month - mortgage.start_date.month)
            months_to_next_review = mortgage.review_period_months - (months_since_start % mortgage.review_period_months)
            
            if months_to_next_review <= 2:
                next_review_date = today + timedelta(days=months_to_next_review * 30)
                notifications.append(Notification(
                    id=f"mortgage_review_{prop.id}",
                    type="mortgage_review",
                    title="Revisión de hipoteca próxima",
                    message=f"La hipoteca de {prop.address} se revisará aproximadamente el {next_review_date.strftime('%d/%m/%Y')}",
                    priority="medium",
                    property_id=prop.id,
                    due_date=next_review_date,
                    action_url=f"/financial-agent/property/{prop.id}/mortgage",
                    created_at=datetime.now(),
                    read=False
                ))
    
    # Ordenar por prioridad y fecha
    priority_order = {"high": 3, "medium": 2, "low": 1}
    notifications.sort(key=lambda x: (priority_order.get(x.priority, 0), x.created_at), reverse=True)
    
    return {
        "notifications": notifications,
        "summary": {
            "total": len(notifications),
            "high_priority": len([n for n in notifications if n.priority == "high"]),
            "medium_priority": len([n for n in notifications if n.priority == "medium"]),
            "low_priority": len([n for n in notifications if n.priority == "low"])
        }
    }

@router.get("/savings-opportunities")
def get_savings_opportunities(
    session: Session = Depends(get_session)
):
    """Análisis de oportunidades de ahorro"""
    opportunities = []
    
    # Obtener propiedades del usuario
    properties = session.exec(
        select(Property)
    ).all()
    
    for prop in properties:
        # 1. Análisis de gastos recurrentes
        last_year = date.today() - timedelta(days=365)
        expenses = session.exec(
            select(FinancialMovement)
            .where(FinancialMovement.property_id == prop.id)
            .where(FinancialMovement.amount < 0)
            .where(FinancialMovement.date >= last_year)
        ).all()
        
        # Agrupar gastos por categoría
        category_totals = {}
        for expense in expenses:
            category = expense.subcategory or expense.category
            if category not in category_totals:
                category_totals[category] = 0
            category_totals[category] += abs(expense.amount)
        
        # Identificar categorías con mayor gasto
        if category_totals:
            sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
            top_category, top_amount = sorted_categories[0]
            
            if top_amount > 1000:  # Si el gasto anual supera €1000
                opportunities.append({
                    "type": "expense_optimization",
                    "property_id": prop.id,
                    "property_address": prop.address,
                    "title": f"Optimizar gastos de {top_category}",
                    "description": f"Has gastado €{top_amount:.0f} en {top_category} este año. Considera buscar alternativas más económicas.",
                    "potential_savings": top_amount * 0.15,  # Estimación 15% de ahorro
                    "priority": "medium"
                })
        
        # 2. Análisis de rentabilidad
        total_expenses = sum(abs(e.amount) for e in expenses)
        total_income = sum(e.amount for e in session.exec(
            select(FinancialMovement)
            .where(FinancialMovement.property_id == prop.id)
            .where(FinancialMovement.amount > 0)
            .where(FinancialMovement.date >= last_year)
        ).all())
        
        if total_income > 0:
            profit_margin = (total_income - total_expenses) / total_income
            if profit_margin < 0.3:  # Si el margen es menor al 30%
                opportunities.append({
                    "type": "rent_increase",
                    "property_id": prop.id,
                    "property_address": prop.address,
                    "title": "Considerar ajuste de renta",
                    "description": f"El margen de beneficio ({profit_margin*100:.1f}%) está por debajo del objetivo (30%). Evalúa incremento de renta.",
                    "potential_savings": total_income * 0.1,  # Estimación 10% incremento
                    "priority": "low"
                })
    
    return {
        "opportunities": opportunities,
        "total_potential_savings": sum(opp["potential_savings"] for opp in opportunities)
    }

@router.post("/mark-read/{notification_id}")
def mark_notification_read(
    notification_id: str,
    session: Session = Depends(get_session)
):
    """Marcar notificación como leída (en una implementación real se guardaría en BD)"""
    return {"message": "Notification marked as read", "notification_id": notification_id}

@router.get("/settings")
def get_notification_settings(
    session: Session = Depends(get_session)
):
    """Obtener configuración de notificaciones del usuario"""
    # En una implementación real, esto se obtendría de la base de datos
    default_settings = {
        "payment_due": NotificationRule(type="payment_due", enabled=True, email_enabled=False),
        "unusual_expense": NotificationRule(type="unusual_expense", threshold=1000.0, enabled=True, email_enabled=False),
        "contract_expiring": NotificationRule(type="contract_expiring", enabled=True, email_enabled=False),
        "savings_opportunity": NotificationRule(type="savings_opportunity", enabled=True, email_enabled=False),
        "mortgage_review": NotificationRule(type="mortgage_review", enabled=True, email_enabled=False)
    }
    
    return {
        "user_id": 1,
        "email": "demo@example.com",
        "rules": default_settings
    }

@router.post("/settings")
def update_notification_settings(
    settings: Dict[str, NotificationRule],
    session: Session = Depends(get_session)
):
    """Actualizar configuración de notificaciones"""
    # En una implementación real, esto se guardaría en la base de datos
    return {
        "message": "Notification settings updated successfully",
        "settings": settings
    }