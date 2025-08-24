# app/routers/mortgage_details.py
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel

from ..db import get_session
from ..deps import get_current_user
from ..models import User, Property, MortgageDetails, MortgageRevision, MortgagePrepayment
from ..services.mortgage_calculator import MortgageCalculator

router = APIRouter(prefix="/mortgage-details", tags=["mortgage-details"])

# Pydantic models
class MortgageDetailsCreate(BaseModel):
    property_id: int
    loan_id: Optional[str] = None
    bank_entity: Optional[str] = None
    mortgage_type: str = "Variable"
    initial_amount: float
    outstanding_balance: float
    margin_percentage: float
    start_date: date
    end_date: date
    review_period_months: int = 12

class MortgageDetailsUpdate(BaseModel):
    loan_id: Optional[str] = None
    bank_entity: Optional[str] = None
    mortgage_type: Optional[str] = None
    outstanding_balance: Optional[float] = None
    margin_percentage: Optional[float] = None
    end_date: Optional[date] = None
    review_period_months: Optional[int] = None

class MortgageRevisionCreate(BaseModel):
    effective_date: date
    euribor_rate: Optional[float] = None
    margin_rate: float
    period_months: int

class MortgageRevisionUpdate(BaseModel):
    euribor_rate: Optional[float] = None
    margin_rate: Optional[float] = None
    period_months: Optional[int] = None

class MortgagePrepaymentCreate(BaseModel):
    payment_date: date
    amount: float

class MortgageDetailsResponse(BaseModel):
    id: int
    property_id: int
    loan_id: Optional[str] = None
    bank_entity: Optional[str] = None
    mortgage_type: str
    initial_amount: float
    outstanding_balance: float
    margin_percentage: float
    start_date: date
    end_date: date
    review_period_months: int

class MortgageRevisionResponse(BaseModel):
    id: int
    mortgage_id: int
    effective_date: date
    euribor_rate: Optional[float] = None
    margin_rate: float
    period_months: int

class MortgagePrepaymentResponse(BaseModel):
    id: int
    mortgage_id: int
    payment_date: date
    amount: float

@router.get("/", response_model=List[MortgageDetailsResponse])
def get_mortgage_details(
    property_id: Optional[int] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get mortgage details with optional property filter"""
    query = select(MortgageDetails).join(Property).where(Property.owner_id == current_user.id)
    
    if property_id:
        query = query.where(MortgageDetails.property_id == property_id)
    
    mortgages = session.exec(query).all()
    return mortgages

@router.post("/", response_model=MortgageDetailsResponse)
def create_mortgage_details(
    mortgage_data: MortgageDetailsCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create mortgage details for a property"""
    # Verify property ownership
    property_obj = session.get(Property, mortgage_data.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Check if mortgage already exists for this property
    existing = session.exec(
        select(MortgageDetails).where(MortgageDetails.property_id == mortgage_data.property_id)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Mortgage details already exist for this property")
    
    mortgage = MortgageDetails(**mortgage_data.dict())
    session.add(mortgage)
    session.commit()
    session.refresh(mortgage)
    return mortgage

@router.get("/{mortgage_id}", response_model=MortgageDetailsResponse)
def get_mortgage_detail(
    mortgage_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get specific mortgage details"""
    mortgage = session.get(MortgageDetails, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Verify ownership through property
    property_obj = session.get(Property, mortgage.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    return mortgage

@router.put("/{mortgage_id}", response_model=MortgageDetailsResponse)
def update_mortgage_details(
    mortgage_id: int,
    mortgage_data: MortgageDetailsUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update mortgage details"""
    mortgage = session.get(MortgageDetails, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Verify ownership
    property_obj = session.get(Property, mortgage.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Update fields
    for field, value in mortgage_data.dict(exclude_unset=True).items():
        setattr(mortgage, field, value)
    
    session.commit()
    session.refresh(mortgage)
    return mortgage

@router.delete("/{mortgage_id}")
def delete_mortgage_details(
    mortgage_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Delete mortgage details"""
    mortgage = session.get(MortgageDetails, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Verify ownership
    property_obj = session.get(Property, mortgage.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    session.delete(mortgage)
    session.commit()
    return {"message": "Mortgage details deleted successfully"}

# Mortgage Revisions endpoints
@router.get("/{mortgage_id}/revisions", response_model=List[MortgageRevisionResponse])
def get_mortgage_revisions(
    mortgage_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get all revisions for a mortgage"""
    mortgage = session.get(MortgageDetails, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Verify ownership
    property_obj = session.get(Property, mortgage.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    revisions = session.exec(
        select(MortgageRevision)
        .where(MortgageRevision.mortgage_id == mortgage_id)
        .order_by(MortgageRevision.effective_date)
    ).all()
    
    return revisions

@router.post("/{mortgage_id}/revisions", response_model=MortgageRevisionResponse)
def create_mortgage_revision(
    mortgage_id: int,
    revision_data: MortgageRevisionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Add a new mortgage revision"""
    mortgage = session.get(MortgageDetails, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Verify ownership
    property_obj = session.get(Property, mortgage.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    revision = MortgageRevision(mortgage_id=mortgage_id, **revision_data.dict())
    session.add(revision)
    session.commit()
    session.refresh(revision)
    return revision

@router.put("/{mortgage_id}/revisions/{revision_id}", response_model=MortgageRevisionResponse)
def update_mortgage_revision(
    mortgage_id: int,
    revision_id: int,
    revision_data: MortgageRevisionUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update an existing mortgage revision"""
    # Verify mortgage ownership
    mortgage = session.get(MortgageDetails, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    property_obj = session.get(Property, mortgage.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Get the revision
    revision = session.get(MortgageRevision, revision_id)
    if not revision or revision.mortgage_id != mortgage_id:
        raise HTTPException(status_code=404, detail="Revision not found")
    
    # Update revision fields
    for field, value in revision_data.dict(exclude_unset=True).items():
        setattr(revision, field, value)
    
    session.commit()
    session.refresh(revision)
    return revision

# Mortgage Prepayments endpoints
@router.get("/{mortgage_id}/prepayments", response_model=List[MortgagePrepaymentResponse])
def get_mortgage_prepayments(
    mortgage_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get all prepayments for a mortgage"""
    mortgage = session.get(MortgageDetails, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Verify ownership
    property_obj = session.get(Property, mortgage.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    prepayments = session.exec(
        select(MortgagePrepayment)
        .where(MortgagePrepayment.mortgage_id == mortgage_id)
        .order_by(MortgagePrepayment.payment_date)
    ).all()
    
    return prepayments

@router.post("/{mortgage_id}/prepayments", response_model=MortgagePrepaymentResponse)
def create_mortgage_prepayment(
    mortgage_id: int,
    prepayment_data: MortgagePrepaymentCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Add a new mortgage prepayment"""
    mortgage = session.get(MortgageDetails, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Verify ownership
    property_obj = session.get(Property, mortgage.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    prepayment = MortgagePrepayment(mortgage_id=mortgage_id, **prepayment_data.dict())
    session.add(prepayment)
    session.commit()
    session.refresh(prepayment)
    return prepayment

@router.get("/property/{property_id}/details", response_model=Optional[MortgageDetailsResponse])
def get_mortgage_by_property(
    property_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get mortgage details for a specific property"""
    # Verify property ownership
    property_obj = session.get(Property, property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Property not found")
    
    mortgage = session.exec(
        select(MortgageDetails).where(MortgageDetails.property_id == property_id)
    ).first()
    
    return mortgage

# Calculation endpoints
@router.get("/{mortgage_id}/calculate-schedule")
def calculate_amortization_schedule(
    mortgage_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Calculate full amortization schedule"""
    mortgage = session.get(MortgageDetails, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Verify ownership
    property_obj = session.get(Property, mortgage.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Get revisions and prepayments
    revisions = session.exec(
        select(MortgageRevision).where(MortgageRevision.mortgage_id == mortgage_id)
    ).all()
    
    prepayments = session.exec(
        select(MortgagePrepayment).where(MortgagePrepayment.mortgage_id == mortgage_id)
    ).all()
    
    # Calculate schedule
    schedule = MortgageCalculator.generate_amortization_schedule(
        mortgage, revisions, prepayments
    )
    
    return {"schedule": schedule}

@router.get("/{mortgage_id}/current-status")
def get_current_mortgage_status(
    mortgage_id: int,
    as_of_date: Optional[date] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get current payment and balance"""
    mortgage = session.get(MortgageDetails, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Verify ownership
    property_obj = session.get(Property, mortgage.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Get revisions and prepayments
    revisions = session.exec(
        select(MortgageRevision).where(MortgageRevision.mortgage_id == mortgage_id)
    ).all()
    
    prepayments = session.exec(
        select(MortgagePrepayment).where(MortgagePrepayment.mortgage_id == mortgage_id)
    ).all()
    
    # Calculate current status
    status = MortgageCalculator.calculate_current_payment_and_balance(
        mortgage, revisions, prepayments, as_of_date
    )
    
    return status

@router.get("/{mortgage_id}/summary")
def get_mortgage_summary(
    mortgage_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive mortgage summary"""
    mortgage = session.get(MortgageDetails, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Verify ownership
    property_obj = session.get(Property, mortgage.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Get revisions and prepayments
    revisions = session.exec(
        select(MortgageRevision).where(MortgageRevision.mortgage_id == mortgage_id)
    ).all()
    
    prepayments = session.exec(
        select(MortgagePrepayment).where(MortgagePrepayment.mortgage_id == mortgage_id)
    ).all()
    
    # Calculate summary
    summary = MortgageCalculator.calculate_mortgage_summary(
        mortgage, revisions, prepayments
    )
    
    return summary

@router.post("/{mortgage_id}/generate-revision-calendar")
def generate_revision_calendar(
    mortgage_id: int,
    create_missing: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Generate revision calendar for the mortgage and optionally create missing revision entries"""
    mortgage = session.get(MortgageDetails, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Verify ownership
    property_obj = session.get(Property, mortgage.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Generate calendar
    calendar = MortgageCalculator.generate_revision_calendar(
        mortgage.start_date,
        mortgage.end_date,
        mortgage.review_period_months,
        mortgage.margin_percentage
    )
    
    created_revisions = []
    
    if create_missing:
        # Get existing revisions
        existing_revisions = session.exec(
            select(MortgageRevision).where(MortgageRevision.mortgage_id == mortgage_id)
        ).all()
        existing_dates = {rev.effective_date for rev in existing_revisions}
        
        # Create missing revisions
        for revision_date in calendar:
            if revision_date not in existing_dates:
                new_revision = MortgageRevision(
                    mortgage_id=mortgage_id,
                    effective_date=revision_date,
                    margin_rate=mortgage.margin_percentage,
                    period_months=mortgage.review_period_months,
                    # euribor_rate will be null - user needs to fill it
                )
                session.add(new_revision)
                created_revisions.append(new_revision)
        
        if created_revisions:
            session.commit()
            for rev in created_revisions:
                session.refresh(rev)
    
    return {
        "revision_calendar": calendar,
        "created_revisions": len(created_revisions),
        "created_revision_dates": [rev.effective_date.isoformat() for rev in created_revisions]
    }

class PrepaymentImpactRequest(BaseModel):
    amount: float
    payment_date: date

@router.post("/{mortgage_id}/calculate-prepayment-impact")
def calculate_prepayment_impact(
    mortgage_id: int,
    prepayment_data: PrepaymentImpactRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Calculate the impact of a potential prepayment"""
    mortgage = session.get(MortgageDetails, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Verify ownership
    property_obj = session.get(Property, mortgage.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Get revisions and prepayments
    revisions = session.exec(
        select(MortgageRevision).where(MortgageRevision.mortgage_id == mortgage_id)
    ).all()
    
    prepayments = session.exec(
        select(MortgagePrepayment).where(MortgagePrepayment.mortgage_id == mortgage_id)
    ).all()
    
    # Calculate impact
    impact = MortgageCalculator.calculate_prepayment_impact(
        mortgage, revisions, prepayments,
        prepayment_data.amount, prepayment_data.payment_date
    )
    
    return impact

@router.get("/property/{property_id}/roi-analysis")
def calculate_property_roi(
    property_id: int,
    year: Optional[int] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Calculate comprehensive ROI analysis for a property"""
    # Verify property ownership
    property_obj = session.get(Property, property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Get financial movements for the property
    from ..models import FinancialMovement
    from datetime import datetime
    
    if not year:
        year = datetime.now().year
    
    start_date = datetime(year, 1, 1).date()
    end_date = datetime(year, 12, 31).date()
    
    movements = session.exec(
        select(FinancialMovement).where(
            FinancialMovement.property_id == property_id,
            FinancialMovement.date >= start_date,
            FinancialMovement.date <= end_date
        )
    ).all()
    
    # Calculate total income and expenses
    total_income = sum(mov.amount for mov in movements if mov.amount > 0)
    total_expenses = sum(abs(mov.amount) for mov in movements if mov.amount < 0)
    net_cash_flow = total_income - total_expenses
    
    # Calculate total equity invested
    total_equity = 0
    if property_obj.down_payment:
        total_equity += property_obj.down_payment
    if property_obj.acquisition_costs:
        total_equity += property_obj.acquisition_costs
    if property_obj.renovation_costs:
        total_equity += property_obj.renovation_costs
    
    # Calculate ROI metrics
    cash_on_cash_roi = 0
    purchase_price_roi = 0
    
    if total_equity > 0:
        cash_on_cash_roi = (net_cash_flow / total_equity) * 100
    
    if property_obj.purchase_price and property_obj.purchase_price > 0:
        purchase_price_roi = (net_cash_flow / property_obj.purchase_price) * 100
    
    # Calculate cap rate (if we have current value)
    cap_rate = 0
    current_value = property_obj.appraisal_value or property_obj.purchase_price
    if current_value and current_value > 0:
        cap_rate = (net_cash_flow / current_value) * 100
    
    # Monthly cash flow
    monthly_cash_flow = net_cash_flow / 12 if net_cash_flow else 0
    
    # Calculate mortgage info if exists
    mortgage = session.exec(
        select(MortgageDetails).where(MortgageDetails.property_id == property_id)
    ).first()
    
    mortgage_info = None
    if mortgage:
        mortgage_payments = sum(
            abs(mov.amount) for mov in movements 
            if mov.amount < 0 and mov.category == "Hipoteca"
        )
        
        mortgage_info = {
            "outstanding_balance": mortgage.outstanding_balance,
            "annual_payments": mortgage_payments,
            "monthly_payment": mortgage_payments / 12 if mortgage_payments else 0
        }
    
    return {
        "property_id": property_id,
        "year": year,
        "financial_summary": {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_cash_flow": net_cash_flow,
            "monthly_cash_flow": monthly_cash_flow
        },
        "investment_summary": {
            "purchase_price": property_obj.purchase_price,
            "down_payment": property_obj.down_payment,
            "acquisition_costs": property_obj.acquisition_costs,
            "renovation_costs": property_obj.renovation_costs,
            "total_equity_invested": total_equity,
            "current_value": current_value
        },
        "roi_metrics": {
            "cash_on_cash_roi": cash_on_cash_roi,
            "purchase_price_roi": purchase_price_roi,
            "cap_rate": cap_rate,
            "monthly_roi": (monthly_cash_flow / total_equity * 100) if total_equity > 0 else 0
        },
        "mortgage_info": mortgage_info
    }

@router.post("/{mortgage_id}/auto-assign-euribor")
def auto_assign_euribor_rates(
    mortgage_id: int,
    rate_period: str = "12m",  # "12m", "6m", "3m", "1m"
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Automatically assign Euribor rates to mortgage revisions based on their dates"""
    mortgage = session.get(MortgageDetails, mortgage_id)
    if not mortgage:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Verify ownership
    property_obj = session.get(Property, mortgage.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Mortgage not found")
    
    # Get all revisions without Euribor rates
    revisions = session.exec(
        select(MortgageRevision).where(
            MortgageRevision.mortgage_id == mortgage_id,
            MortgageRevision.euribor_rate.is_(None)
        )
    ).all()
    
    if not revisions:
        return {"message": "No revisions found without Euribor rates", "updated": 0}
    
    # Import EuriborRate here to avoid circular imports
    from ..models import EuriborRate
    
    updated_count = 0
    errors = []
    
    for revision in revisions:
        try:
            # Find closest Euribor rate for the revision date
            euribor_rate = session.exec(
                select(EuriborRate)
                .where(EuriborRate.date <= revision.effective_date)
                .order_by(EuriborRate.date.desc())
                .limit(1)
            ).first()
            
            if euribor_rate:
                # Get the appropriate rate based on period
                rate_value = None
                if rate_period == "12m":
                    rate_value = euribor_rate.rate_12m
                elif rate_period == "6m":
                    rate_value = euribor_rate.rate_6m
                elif rate_period == "3m":
                    rate_value = euribor_rate.rate_3m
                elif rate_period == "1m":
                    rate_value = euribor_rate.rate_1m
                
                if rate_value is not None:
                    revision.euribor_rate = rate_value
                    updated_count += 1
                else:
                    errors.append(f"No {rate_period} rate available for {revision.effective_date}")
            else:
                errors.append(f"No Euribor data found for {revision.effective_date}")
                
        except Exception as e:
            errors.append(f"Error processing revision {revision.effective_date}: {str(e)}")
    
    if updated_count > 0:
        session.commit()
    
    return {
        "message": f"Updated {updated_count} revisions with Euribor rates",
        "updated": updated_count,
        "errors": errors
    }