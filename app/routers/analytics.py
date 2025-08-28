# app/routers/analytics.py
from fastapi import APIRouter, Depends
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
from sqlmodel import Session, select, func
import logging
from ..db import get_session
from ..deps import get_current_user
from ..models import Property, FinancialMovement, RentalContract, MortgageDetails

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/debug-dashboard/{property_id}")
def debug_dashboard_data(
    property_id: int,
    year: Optional[int] = None,
    session: Session = Depends(get_session)
):
    """Debug endpoint temporal sin autenticación"""
    if year is None:
        year = datetime.now().year
    
    # Obtener la propiedad
    property_data = session.get(Property, property_id)
    if not property_data:
        return {"error": "Propiedad no encontrada"}
    
    # Obtener hipoteca de la propiedad
    mortgage = session.exec(
        select(MortgageDetails)
        .where(MortgageDetails.property_id == property_id)
    ).first()
    
    # Cálculo de inversión total: precio de compra + 10% proxy para impuestos y gastos
    purchase_price = property_data.purchase_price or 0
    total_investment = purchase_price * 1.10  # Precio compra + 10% proxy
    
    # Cash aportado: precio de compra - importe inicial hipoteca (de gestión hipotecaria)
    initial_debt = 0
    if mortgage:
        initial_debt = mortgage.initial_amount
    
    cash_contributed = purchase_price - initial_debt
    # Asegurar que cash_contributed sea al menos 20% del precio de compra
    if cash_contributed <= 0:
        cash_contributed = purchase_price * 0.2
    
    return {
        "property_id": property_id,
        "year": year,
        "purchase_price": purchase_price,
        "total_investment": total_investment,
        "initial_debt": initial_debt,
        "cash_contributed": cash_contributed,
        "mortgage_exists": bool(mortgage),
        "property": {
            "cash_contributed": cash_contributed,
            "total_investment": total_investment,
        }
    }

@router.get("/debug/{property_id}")
def debug_property_data(
    property_id: int,
    session: Session = Depends(get_session)
):
    """Debug endpoint para verificar datos de propiedad"""
    property_data = session.get(Property, property_id)
    if not property_data:
        return {"error": "Propiedad no encontrada"}
    
    mortgage = session.exec(
        select(MortgageDetails)
        .where(MortgageDetails.property_id == property_id)
    ).first()
    
    return {
        "property": {
            "id": property_data.id,
            "address": property_data.address,
            "purchase_price": property_data.purchase_price,
            "acquisition_costs": property_data.acquisition_costs,
            "renovation_costs": property_data.renovation_costs,
        },
        "mortgage": {
            "exists": bool(mortgage),
            "initial_amount": mortgage.initial_amount if mortgage else None,
            "outstanding_balance": mortgage.outstanding_balance if mortgage else None,
        } if mortgage else None
    }

@router.get("/dashboard/{property_id}")
def get_property_dashboard(
    property_id: int,
    year: Optional[int] = None,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Dashboard completo de métricas para una propiedad específica"""
    if year is None:
        year = datetime.now().year
    
    # Obtener la propiedad
    property_data = session.get(Property, property_id)
    if not property_data or property_data.owner_id != current_user.id:
        return {"error": "Propiedad no encontrada"}
    
    # Calcular métricas financieras
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    
    # Movimientos del año
    movements = session.exec(
        select(FinancialMovement)
        .where(FinancialMovement.property_id == property_id)
        .where(FinancialMovement.date >= start_date)
        .where(FinancialMovement.date <= end_date)
    ).all()
    
    # Cálculos básicos
    total_income = sum(m.amount for m in movements if m.amount > 0)
    total_expenses = sum(abs(m.amount) for m in movements if m.amount < 0)
    net_income = total_income - total_expenses
    
    # Ingresos por categoría
    rent_income = sum(m.amount for m in movements if m.category == "Renta" and m.amount > 0)
    
    # Gastos por categoría
    expenses_by_category = {}
    for movement in movements:
        if movement.amount < 0:
            category = movement.subcategory or movement.category
            expenses_by_category[category] = expenses_by_category.get(category, 0) + abs(movement.amount)
    
    # Obtener hipoteca de la propiedad
    mortgage = session.exec(
        select(MortgageDetails)
        .where(MortgageDetails.property_id == property_id)
    ).first()
    
    # Cálculo de inversión total: precio de compra + 10% proxy para impuestos y gastos
    purchase_price = property_data.purchase_price or 0
    total_investment = purchase_price * 1.10  # Precio compra + 10% proxy
    
    # Cash aportado: precio de compra - importe inicial hipoteca (de gestión hipotecaria)
    initial_debt = 0
    if mortgage:
        initial_debt = mortgage.initial_amount
    
    cash_contributed = purchase_price - initial_debt
    # Asegurar que cash_contributed sea al menos 20% del precio de compra
    if cash_contributed <= 0:
        cash_contributed = purchase_price * 0.2
    
# Comentado temporalmente: logger.info(f"Property {property_id}: purchase_price={purchase_price}, total_investment={total_investment}, initial_debt={initial_debt}, cash_contributed={cash_contributed}")
    
    # ROI sobre cash aportado (más realista)
    roi_on_cash = (net_income / cash_contributed * 100) if cash_contributed > 0 else 0
    
    # ROI sobre inversión total (tradicional)
    roi_on_investment = (net_income / total_investment * 100) if total_investment > 0 else 0
    
    # Rental Yield (Rentabilidad bruta sobre cash)
    gross_yield_cash = (rent_income / cash_contributed * 100) if cash_contributed > 0 else 0
    gross_yield_investment = (rent_income / total_investment * 100) if total_investment > 0 else 0
    
    # Cash flow mensual promedio
    monthly_cash_flow = net_income / 12
    
    # Contrato activo
    active_contract = session.exec(
        select(RentalContract)
        .where(RentalContract.property_id == property_id)
        .where(RentalContract.is_active == True)
    ).first()
    
    # Detalles hipoteca ya obtenidos arriba
    
    return {
        "property": {
            "id": property_data.id,
            "address": property_data.address,
            "total_investment": float(total_investment),
            "cash_contributed": float(cash_contributed),
            "initial_debt": float(initial_debt),
            "purchase_price": float(property_data.purchase_price) if property_data.purchase_price else 0.0,
            "current_value": float(property_data.appraisal_value) if property_data.appraisal_value else None
        },
        "financial_metrics": {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_income": net_income,
            "roi_on_cash": round(roi_on_cash, 2),
            "roi_on_investment": round(roi_on_investment, 2),
            "gross_yield_cash": round(gross_yield_cash, 2),
            "gross_yield_investment": round(gross_yield_investment, 2),
            "monthly_cash_flow": round(monthly_cash_flow, 2)
        },
        "income_breakdown": {
            "rent": rent_income,
            "other": total_income - rent_income
        },
        "expenses_by_category": expenses_by_category,
        "rental_info": {
            "active_contract": bool(active_contract),
            "monthly_rent": active_contract.monthly_rent if active_contract else 0,
            "tenant_name": active_contract.tenant_name if active_contract else None,
            "contract_end": active_contract.end_date.isoformat() if active_contract and active_contract.end_date else None
        },
        "mortgage_info": {
            "has_mortgage": bool(mortgage),
            "outstanding_balance": mortgage.outstanding_balance if mortgage else 0,
            "monthly_payment": calculate_monthly_payment(mortgage) if mortgage else 0,
            "current_rate": (mortgage.margin_percentage + 3.5) if mortgage else 0,  # Euribor + diferencial
            "remaining_months": calculate_remaining_months_from_date(mortgage.end_date) if mortgage else 0,
            "start_date": mortgage.start_date.isoformat() if mortgage else None,
            "end_date": mortgage.end_date.isoformat() if mortgage else None
        },
        "year": year
    }

@router.get("/portfolio-summary")
def get_portfolio_summary(
    year: Optional[int] = None,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Resumen completo del portfolio de propiedades"""
    if year is None:
        year = datetime.now().year
    
    # Obtener todas las propiedades del usuario
    properties = session.exec(
        select(Property).where(Property.owner_id == current_user.id)
    ).all()
    
    # Get mortgage debt total
    from ..models import MortgageDetails
    mortgages = session.exec(
        select(MortgageDetails).join(Property).where(Property.owner_id == current_user.id)
    ).all()
    total_debt = sum(m.outstanding_balance for m in mortgages)
    
    # Calculate total property value
    total_property_value = 0
    for prop in properties:
        appraisal = prop.appraisal_value or 0
        purchase = prop.purchase_price or 0
        # Use appraisal if available, otherwise purchase price
        total_property_value += appraisal if appraisal > 0 else purchase
    
    portfolio_metrics = {
        "total_properties": len(properties),
        "total_investment": 0,
        "total_property_value": total_property_value,
        "total_debt": total_debt,
        "net_equity": total_property_value - total_debt,
        "total_income": 0,
        "total_expenses": 0,
        "total_net_income": 0,
        "average_roi": 0,
        "properties_performance": []
    }
    
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    
    valid_rois = []
    
    for prop in properties:
        # Movimientos de la propiedad
        movements = session.exec(
            select(FinancialMovement)
            .where(FinancialMovement.property_id == prop.id)
            .where(FinancialMovement.date >= start_date)
            .where(FinancialMovement.date <= end_date)
        ).all()
        
        income = sum(m.amount for m in movements if m.amount > 0)
        expenses = sum(abs(m.amount) for m in movements if m.amount < 0)
        net_income = income - expenses
        
        # Inversión total: precio de compra + 10% proxy para impuestos y gastos
        purchase_price = prop.purchase_price or 0
        investment = purchase_price * 1.10  # Precio compra + 10% proxy
        
# Comentado temporalmente: logger.info(f"Portfolio Property {prop.id}: purchase_price={purchase_price}, investment={investment}")
        roi = (net_income / investment * 100) if investment > 0 else 0
        
        if investment > 0:
            valid_rois.append(roi)
        
        portfolio_metrics["total_investment"] += investment
        portfolio_metrics["total_income"] += income
        portfolio_metrics["total_expenses"] += expenses
        portfolio_metrics["total_net_income"] += net_income
        
        portfolio_metrics["properties_performance"].append({
            "id": prop.id,
            "address": prop.address,
            "investment": float(investment),
            "total_investment": float(investment),  # Usando la nueva lógica
            "income": float(income),
            "expenses": float(expenses),
            "net_income": float(net_income),
            "roi": round(float(roi), 2)
        })
    
    # ROI promedio ponderado
    if portfolio_metrics["total_investment"] > 0:
        portfolio_metrics["average_roi"] = round(
            (portfolio_metrics["total_net_income"] / portfolio_metrics["total_investment"] * 100), 2
        )
    
    # Ordenar propiedades por ROI
    portfolio_metrics["properties_performance"].sort(key=lambda x: x["roi"], reverse=True)
    
    return portfolio_metrics

@router.get("/cash-flow-projection/{property_id}")
def get_cash_flow_projection(
    property_id: int,
    months_ahead: int = 12,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Proyección de cash flow para los próximos meses"""
    property_data = session.get(Property, property_id)
    if not property_data or property_data.owner_id != current_user.id:
        return {"error": "Propiedad no encontrada"}
    
    # Obtener histórico de movimientos (últimos 12 meses)
    one_year_ago = date.today() - timedelta(days=365)
    historical_movements = session.exec(
        select(FinancialMovement)
        .where(FinancialMovement.property_id == property_id)
        .where(FinancialMovement.date >= one_year_ago)
    ).all()
    
    # Calcular promedios mensuales por categoría
    monthly_averages = {}
    for movement in historical_movements:
        category = movement.category
        month_key = f"{movement.date.year}-{movement.date.month:02d}"
        
        if category not in monthly_averages:
            monthly_averages[category] = []
        
        # Agrupar por mes
        found = False
        for avg in monthly_averages[category]:
            if avg["month"] == month_key:
                avg["total"] += movement.amount
                found = True
                break
        
        if not found:
            monthly_averages[category].append({
                "month": month_key,
                "total": movement.amount
            })
    
    # Calcular promedios finales
    projected_monthly = {}
    for category, months_data in monthly_averages.items():
        if months_data:
            avg_amount = sum(m["total"] for m in months_data) / len(months_data)
            projected_monthly[category] = round(avg_amount, 2)
    
    # Generar proyección
    projection = []
    current_date = date.today()
    
    for i in range(months_ahead):
        month_date = current_date + timedelta(days=30*i)
        monthly_projection = {
            "month": month_date.strftime("%Y-%m"),
            "date": month_date.isoformat(),
            "projected_income": 0,
            "projected_expenses": 0,
            "projected_net": 0,
            "details": {}
        }
        
        for category, amount in projected_monthly.items():
            monthly_projection["details"][category] = amount
            if amount > 0:
                monthly_projection["projected_income"] += amount
            else:
                monthly_projection["projected_expenses"] += abs(amount)
        
        monthly_projection["projected_net"] = monthly_projection["projected_income"] - monthly_projection["projected_expenses"]
        projection.append(monthly_projection)
    
    return {
        "property_id": property_id,
        "projection_months": months_ahead,
        "historical_data": monthly_averages,
        "projection": projection
    }

def calculate_monthly_payment(mortgage: MortgageDetails) -> float:
    """Calcular pago mensual de hipoteca"""
    if not mortgage:
        return 0
    
    # Fórmula simplificada - en producción usar tasas reales
    principal = mortgage.outstanding_balance
    annual_rate = (mortgage.margin_percentage + 3.5) / 100  # Estimación Euribor + margen
    monthly_rate = annual_rate / 12
    
    # Calcular meses restantes
    today = date.today()
    months_remaining = (mortgage.end_date.year - today.year) * 12 + (mortgage.end_date.month - today.month)
    
    if months_remaining <= 0 or monthly_rate == 0:
        return 0
    
    # Fórmula de amortización
    monthly_payment = principal * (monthly_rate * (1 + monthly_rate)**months_remaining) / ((1 + monthly_rate)**months_remaining - 1)
    return round(monthly_payment, 2)

def calculate_remaining_months_from_date(end_date):
    """Calcular meses restantes hasta una fecha"""
    if not end_date:
        return 0
    
    today = date.today()
    remaining_months = (end_date.year - today.year) * 12 + (end_date.month - today.month)
    
    return max(0, remaining_months)