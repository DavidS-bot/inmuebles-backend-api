# app/routers/mortgage_calculator.py
from fastapi import APIRouter, Depends
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
from sqlmodel import Session, select
from pydantic import BaseModel
from ..db import get_session
from ..deps import get_current_user
from ..models import MortgageDetails, EuriborRate
import math

router = APIRouter(prefix="/mortgage-calculator", tags=["mortgage-calculator"])

class AmortizationRequest(BaseModel):
    property_id: int
    prepayment_amount: float
    prepayment_date: date
    reduce_term: bool = True  # True: reduce plazo, False: reduce cuota

class MortgageSimulation(BaseModel):
    loan_amount: float
    annual_rate: float
    term_years: int
    start_date: date

@router.get("/current-payment/{property_id}")
def get_current_mortgage_payment(
    property_id: int,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Obtener el pago actual de la hipoteca"""
    mortgage = session.exec(
        select(MortgageDetails).where(MortgageDetails.property_id == property_id)
    ).first()
    
    if not mortgage:
        return {"error": "No hay hipoteca registrada para esta propiedad"}
    
    # Obtener la tasa Euribor más reciente
    latest_euribor = session.exec(
        select(EuriborRate).order_by(EuriborRate.date.desc())
    ).first()
    
    current_euribor = latest_euribor.rate_12m if latest_euribor else 3.5
    current_rate = current_euribor + mortgage.margin_percentage
    
    # Calcular pago mensual actual
    monthly_payment = calculate_monthly_payment_detailed(
        mortgage.outstanding_balance,
        current_rate,
        mortgage.start_date,
        mortgage.end_date
    )
    
    return {
        "property_id": property_id,
        "outstanding_balance": mortgage.outstanding_balance,
        "current_euribor": current_euribor,
        "margin": mortgage.margin_percentage,
        "total_rate": current_rate,
        "monthly_payment": monthly_payment,
        "remaining_months": calculate_remaining_months(mortgage.end_date),
        "total_interest_remaining": calculate_total_interest_remaining(mortgage, current_rate)
    }

@router.post("/simulate-prepayment")
def simulate_prepayment(
    request: AmortizationRequest,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Simular amortización anticipada"""
    mortgage = session.exec(
        select(MortgageDetails).where(MortgageDetails.property_id == request.property_id)
    ).first()
    
    if not mortgage:
        return {"error": "No hay hipoteca registrada para esta propiedad"}
    
    # Obtener tasa actual
    latest_euribor = session.exec(
        select(EuriborRate).order_by(EuriborRate.date.desc())
    ).first()
    
    current_euribor = latest_euribor.rate_12m if latest_euribor else 3.5
    annual_rate = current_euribor + mortgage.margin_percentage
    
    # Escenario actual (sin amortización)
    current_scenario = calculate_amortization_schedule(
        mortgage.outstanding_balance,
        annual_rate,
        mortgage.start_date,
        mortgage.end_date
    )
    
    # Escenario con amortización anticipada
    new_principal = mortgage.outstanding_balance - request.prepayment_amount
    
    if request.reduce_term:
        # Mantener la cuota, reducir plazo
        current_monthly = current_scenario["monthly_payment"]
        new_end_date = calculate_new_end_date(new_principal, annual_rate, current_monthly, request.prepayment_date)
        new_scenario = calculate_amortization_schedule(
            new_principal,
            annual_rate,
            request.prepayment_date,
            new_end_date,
            fixed_payment=current_monthly
        )
    else:
        # Mantener el plazo, reducir cuota
        new_scenario = calculate_amortization_schedule(
            new_principal,
            annual_rate,
            request.prepayment_date,
            mortgage.end_date
        )
    
    # Calcular ahorros
    current_total_interest = sum(payment["interest"] for payment in current_scenario["schedule"])
    new_total_interest = sum(payment["interest"] for payment in new_scenario["schedule"])
    interest_savings = current_total_interest - new_total_interest
    
    months_saved = len(current_scenario["schedule"]) - len(new_scenario["schedule"]) if request.reduce_term else 0
    monthly_savings = current_scenario["monthly_payment"] - new_scenario["monthly_payment"] if not request.reduce_term else 0
    
    return {
        "prepayment_amount": request.prepayment_amount,
        "strategy": "reduce_term" if request.reduce_term else "reduce_payment",
        "current_scenario": {
            "monthly_payment": current_scenario["monthly_payment"],
            "total_interest": current_total_interest,
            "remaining_months": len(current_scenario["schedule"]),
            "end_date": mortgage.end_date.isoformat()
        },
        "new_scenario": {
            "monthly_payment": new_scenario["monthly_payment"],
            "total_interest": new_total_interest,
            "remaining_months": len(new_scenario["schedule"]),
            "end_date": new_scenario["end_date"]
        },
        "savings": {
            "interest_savings": round(interest_savings, 2),
            "months_saved": months_saved,
            "monthly_savings": round(monthly_savings, 2),
            "total_savings": round(interest_savings + (monthly_savings * len(new_scenario["schedule"])), 2)
        }
    }

@router.post("/simulate-mortgage")
def simulate_new_mortgage(
    simulation: MortgageSimulation,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Simular una nueva hipoteca"""
    end_date = simulation.start_date.replace(year=simulation.start_date.year + simulation.term_years)
    
    amortization = calculate_amortization_schedule(
        simulation.loan_amount,
        simulation.annual_rate,
        simulation.start_date,
        end_date
    )
    
    total_interest = sum(payment["interest"] for payment in amortization["schedule"])
    total_paid = simulation.loan_amount + total_interest
    
    return {
        "loan_amount": simulation.loan_amount,
        "annual_rate": simulation.annual_rate,
        "term_years": simulation.term_years,
        "monthly_payment": amortization["monthly_payment"],
        "total_interest": round(total_interest, 2),
        "total_paid": round(total_paid, 2),
        "schedule_summary": {
            "first_6_months": amortization["schedule"][:6],
            "total_payments": len(amortization["schedule"])
        }
    }

@router.get("/rate-evolution/{property_id}")
def get_rate_evolution_impact(
    property_id: int,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Analizar el impacto de la evolución de tipos en la hipoteca"""
    mortgage = session.exec(
        select(MortgageDetails).where(MortgageDetails.property_id == property_id)
    ).first()
    
    if not mortgage:
        return {"error": "No hay hipoteca registrada para esta propiedad"}
    
    # Obtener histórico de Euribor
    euribor_rates = session.exec(
        select(EuriborRate).order_by(EuriborRate.date.desc()).limit(24)
    ).all()
    
    if not euribor_rates:
        return {"error": "No hay datos históricos de Euribor"}
    
    # Simular pagos con diferentes escenarios
    scenarios = []
    current_rate = euribor_rates[0].rate_12m + mortgage.margin_percentage
    
    # Escenario actual
    current_payment = calculate_monthly_payment_detailed(
        mortgage.outstanding_balance,
        current_rate,
        mortgage.start_date,
        mortgage.end_date
    )
    
    # Escenarios de estrés
    stress_scenarios = [
        {"name": "Euribor +1%", "rate_change": 1.0},
        {"name": "Euribor +2%", "rate_change": 2.0},
        {"name": "Euribor -0.5%", "rate_change": -0.5},
        {"name": "Euribor 0%", "rate_change": -euribor_rates[0].rate_12m}
    ]
    
    for scenario in stress_scenarios:
        new_rate = current_rate + scenario["rate_change"]
        new_payment = calculate_monthly_payment_detailed(
            mortgage.outstanding_balance,
            new_rate,
            mortgage.start_date,
            mortgage.end_date
        )
        
        scenarios.append({
            "scenario": scenario["name"],
            "rate": round(new_rate, 3),
            "monthly_payment": round(new_payment, 2),
            "payment_difference": round(new_payment - current_payment, 2),
            "annual_impact": round((new_payment - current_payment) * 12, 2)
        })
    
    return {
        "property_id": property_id,
        "current_scenario": {
            "rate": round(current_rate, 3),
            "monthly_payment": round(current_payment, 2)
        },
        "stress_scenarios": scenarios,
        "euribor_history": [
            {
                "date": rate.date.isoformat(),
                "rate_12m": rate.rate_12m,
                "total_rate": rate.rate_12m + mortgage.margin_percentage
            }
            for rate in reversed(euribor_rates)
        ]
    }

def calculate_monthly_payment_detailed(principal: float, annual_rate: float, start_date: date, end_date: date) -> float:
    """Calcular pago mensual detallado"""
    monthly_rate = annual_rate / 100 / 12
    
    # Calcular meses restantes
    today = date.today()
    months_remaining = (end_date.year - today.year) * 12 + (end_date.month - today.month)
    
    if months_remaining <= 0 or monthly_rate == 0:
        return principal / 1 if months_remaining <= 0 else 0
    
    # Fórmula de amortización francesa
    monthly_payment = principal * (monthly_rate * (1 + monthly_rate)**months_remaining) / ((1 + monthly_rate)**months_remaining - 1)
    return monthly_payment

def calculate_remaining_months(end_date: date) -> int:
    """Calcular meses restantes"""
    today = date.today()
    return max(0, (end_date.year - today.year) * 12 + (end_date.month - today.month))

def calculate_total_interest_remaining(mortgage: MortgageDetails, annual_rate: float) -> float:
    """Calcular intereses totales restantes"""
    monthly_payment = calculate_monthly_payment_detailed(
        mortgage.outstanding_balance,
        annual_rate,
        mortgage.start_date,
        mortgage.end_date
    )
    
    remaining_months = calculate_remaining_months(mortgage.end_date)
    total_payments = monthly_payment * remaining_months
    return max(0, total_payments - mortgage.outstanding_balance)

def calculate_amortization_schedule(principal: float, annual_rate: float, start_date: date, end_date: date, fixed_payment: Optional[float] = None) -> Dict:
    """Generar tabla de amortización"""
    monthly_rate = annual_rate / 100 / 12
    total_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    
    if fixed_payment is None:
        monthly_payment = principal * (monthly_rate * (1 + monthly_rate)**total_months) / ((1 + monthly_rate)**total_months - 1)
    else:
        monthly_payment = fixed_payment
    
    schedule = []
    remaining_balance = principal
    current_date = start_date
    
    while remaining_balance > 1 and len(schedule) < total_months * 2:  # Safety limit
        interest_payment = remaining_balance * monthly_rate
        principal_payment = min(monthly_payment - interest_payment, remaining_balance)
        
        if principal_payment <= 0:
            break
            
        remaining_balance -= principal_payment
        
        schedule.append({
            "month": len(schedule) + 1,
            "date": current_date.isoformat(),
            "payment": round(monthly_payment, 2),
            "principal": round(principal_payment, 2),
            "interest": round(interest_payment, 2),
            "balance": round(remaining_balance, 2)
        })
        
        # Avanzar al siguiente mes
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)
    
    final_end_date = schedule[-1]["date"] if schedule else end_date.isoformat()
    
    return {
        "monthly_payment": round(monthly_payment, 2),
        "total_months": len(schedule),
        "end_date": final_end_date,
        "schedule": schedule
    }

def calculate_new_end_date(principal: float, annual_rate: float, monthly_payment: float, start_date: date) -> date:
    """Calcular nueva fecha de fin manteniendo la cuota"""
    monthly_rate = annual_rate / 100 / 12
    
    if monthly_rate == 0 or monthly_payment <= 0:
        months = 360  # Default 30 years
    else:
        try:
            months = math.log(1 + (principal * monthly_rate) / monthly_payment) / math.log(1 + monthly_rate)
            months = int(math.ceil(months))
        except (ValueError, ZeroDivisionError):
            months = 360  # Default fallback
    
    years_to_add = months // 12
    months_to_add = months % 12
    
    new_end_date = start_date.replace(year=start_date.year + years_to_add)
    
    if new_end_date.month + months_to_add > 12:
        new_end_date = new_end_date.replace(
            year=new_end_date.year + 1,
            month=new_end_date.month + months_to_add - 12
        )
    else:
        new_end_date = new_end_date.replace(month=new_end_date.month + months_to_add)
    
    return new_end_date