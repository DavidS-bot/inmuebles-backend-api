# app/services/mortgage_calculator.py
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Optional
import pandas as pd
import numpy as np

from ..models import MortgageDetails, MortgageRevision, MortgagePrepayment

class MortgageCalculator:
    """Service for mortgage calculations based on the original Streamlit agent logic"""
    
    @staticmethod
    def calculate_monthly_payment(principal: float, monthly_rate: float, num_payments: int) -> float:
        """Calculate monthly mortgage payment using standard formula"""
        if num_payments <= 0:
            return principal
        if monthly_rate <= 0:
            return principal / num_payments
        
        return principal * (monthly_rate) / (1 - (1 + monthly_rate) ** (-num_payments))
    
    @staticmethod
    def generate_amortization_schedule(
        mortgage: MortgageDetails,
        revisions: List[MortgageRevision],
        prepayments: List[MortgagePrepayment]
    ) -> List[Dict]:
        """
        Generate complete amortization schedule with revisions and prepayments
        Based on the original schedule_con_revisiones_y_prepagos function
        """
        if mortgage.initial_amount <= 0:
            return []
        
        # Sort revisions by effective date
        revisions_sorted = sorted(revisions, key=lambda x: x.effective_date)
        
        # Group prepayments by month
        prepayments_by_month = {}
        for prep in prepayments:
            month_period = pd.Period(prep.payment_date, freq="M")
            if month_period not in prepayments_by_month:
                prepayments_by_month[month_period] = 0
            prepayments_by_month[month_period] += prep.amount
        
        schedule = []
        balance = float(mortgage.initial_amount)
        current_month = pd.Period(mortgage.start_date, freq="M")
        end_month = pd.Period(mortgage.end_date, freq="M")
        revision_index = 0
        
        while current_month <= end_month and balance > 0.01:
            months_remaining = (end_month - current_month).n + 1
            month_date = current_month.to_timestamp().date()
            
            # Determine current interest rate
            annual_rate = 0.0
            if mortgage.mortgage_type == "Fija":
                # For fixed mortgages, use margin as the fixed rate
                annual_rate = mortgage.margin_percentage
            else:
                # For variable mortgages, find applicable revision
                while (revision_index + 1 < len(revisions_sorted) and 
                       revisions_sorted[revision_index + 1].effective_date <= month_date):
                    revision_index += 1
                
                if revisions_sorted:
                    current_revision = revisions_sorted[revision_index]
                    euribor = current_revision.euribor_rate or 0.0
                    margin = current_revision.margin_rate or 0.0
                    annual_rate = euribor + margin
                else:
                    annual_rate = mortgage.margin_percentage
            
            monthly_rate = annual_rate / 100.0 / 12.0
            
            # Calculate monthly payment
            monthly_payment = MortgageCalculator.calculate_monthly_payment(
                balance, monthly_rate, months_remaining
            )
            
            # Calculate interest and principal
            interest_payment = balance * monthly_rate
            principal_payment = max(0.0, monthly_payment - interest_payment)
            
            # Ensure we don't pay more principal than remaining balance
            if principal_payment > balance:
                principal_payment = balance
                monthly_payment = interest_payment + principal_payment
            
            # Apply payment
            balance = max(0.0, balance - principal_payment)
            
            # Apply prepayments if any for this month
            prepayment_amount = prepayments_by_month.get(current_month, 0.0)
            if prepayment_amount > 0:
                if prepayment_amount > balance:
                    prepayment_amount = balance
                balance -= prepayment_amount
                principal_payment += prepayment_amount
                monthly_payment += prepayment_amount
            
            # Add to schedule
            schedule.append({
                "month": current_month.to_timestamp(),
                "payment": float(monthly_payment),
                "interest": float(interest_payment),
                "principal": float(principal_payment),
                "balance": float(balance),
                "annual_rate": float(annual_rate),
                "prepayment": float(prepayment_amount)
            })
            
            current_month += 1
        
        return schedule
    
    @staticmethod
    def calculate_current_payment_and_balance(
        mortgage: MortgageDetails,
        revisions: List[MortgageRevision],
        prepayments: List[MortgagePrepayment],
        as_of_date: Optional[date] = None
    ) -> Dict:
        """Calculate current monthly payment and outstanding balance"""
        if not as_of_date:
            as_of_date = date.today()
        
        schedule = MortgageCalculator.generate_amortization_schedule(
            mortgage, revisions, prepayments
        )
        
        if not schedule:
            return {
                "current_payment": 0.0,
                "current_balance": mortgage.outstanding_balance,
                "as_of_date": as_of_date
            }
        
        # Find the schedule entry for the current date or closest past date
        target_period = pd.Period(as_of_date, freq="M").to_timestamp()
        
        current_entry = None
        for entry in schedule:
            if entry["month"] <= target_period:
                current_entry = entry
            else:
                break
        
        if not current_entry:
            # If no past entry found, use the first one
            current_entry = schedule[0]
        
        return {
            "current_payment": current_entry["payment"],
            "current_balance": current_entry["balance"],
            "annual_rate": current_entry["annual_rate"],
            "as_of_date": as_of_date
        }
    
    @staticmethod
    def calculate_mortgage_summary(
        mortgage: MortgageDetails,
        revisions: List[MortgageRevision],
        prepayments: List[MortgagePrepayment]
    ) -> Dict:
        """Calculate comprehensive mortgage summary"""
        schedule = MortgageCalculator.generate_amortization_schedule(
            mortgage, revisions, prepayments
        )
        
        if not schedule:
            return {
                "total_payments": 0.0,
                "total_interest": 0.0,
                "total_principal": mortgage.initial_amount,
                "total_prepayments": 0.0,
                "loan_term_months": 0,
                "current_payment": 0.0,
                "current_balance": mortgage.outstanding_balance
            }
        
        total_payments = sum(entry["payment"] for entry in schedule)
        total_interest = sum(entry["interest"] for entry in schedule)
        total_principal = sum(entry["principal"] for entry in schedule)
        total_prepayments = sum(entry["prepayment"] for entry in schedule)
        
        # Get current status
        current_status = MortgageCalculator.calculate_current_payment_and_balance(
            mortgage, revisions, prepayments
        )
        
        return {
            "total_payments": total_payments,
            "total_interest": total_interest,
            "total_principal": total_principal,
            "total_prepayments": total_prepayments,
            "loan_term_months": len(schedule),
            "current_payment": current_status["current_payment"],
            "current_balance": current_status["current_balance"],
            "annual_rate": current_status.get("annual_rate", 0.0)
        }
    
    @staticmethod
    def generate_revision_calendar(
        start_date: date,
        end_date: date,
        period_months: int,
        margin_percentage: float
    ) -> List[str]:
        """Generate calendar of mortgage revision dates"""
        if period_months <= 0:
            return []
        
        revision_dates = []
        current_date = start_date
        
        while current_date <= end_date:
            revision_dates.append(current_date.isoformat())  # Return date in ISO format (YYYY-MM-DD)
            current_date = current_date + relativedelta(months=+period_months)
        
        return revision_dates
    
    @staticmethod
    def calculate_prepayment_impact(
        mortgage: MortgageDetails,
        revisions: List[MortgageRevision],
        existing_prepayments: List[MortgagePrepayment],
        new_prepayment_amount: float,
        new_prepayment_date: date
    ) -> Dict:
        """Calculate the impact of a new prepayment on the mortgage"""
        # Calculate original scenario
        original_schedule = MortgageCalculator.generate_amortization_schedule(
            mortgage, revisions, existing_prepayments
        )
        
        # Calculate scenario with new prepayment
        new_prepayment = MortgagePrepayment(
            mortgage_id=mortgage.id,
            payment_date=new_prepayment_date,
            amount=new_prepayment_amount
        )
        all_prepayments = existing_prepayments + [new_prepayment]
        
        new_schedule = MortgageCalculator.generate_amortization_schedule(
            mortgage, revisions, all_prepayments
        )
        
        if not original_schedule or not new_schedule:
            return {"error": "Could not calculate prepayment impact"}
        
        # Calculate savings
        original_total_interest = sum(entry["interest"] for entry in original_schedule)
        new_total_interest = sum(entry["interest"] for entry in new_schedule)
        interest_savings = original_total_interest - new_total_interest
        
        # Calculate time savings (months)
        time_savings_months = len(original_schedule) - len(new_schedule)
        
        return {
            "prepayment_amount": new_prepayment_amount,
            "interest_savings": interest_savings,
            "time_savings_months": time_savings_months,
            "original_term_months": len(original_schedule),
            "new_term_months": len(new_schedule),
            "original_total_interest": original_total_interest,
            "new_total_interest": new_total_interest
        }