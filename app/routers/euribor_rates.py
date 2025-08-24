# app/routers/euribor_rates.py
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel

from ..db import get_session
from ..deps import get_current_user
from ..models import User, EuriborRate

router = APIRouter(prefix="/euribor-rates", tags=["euribor-rates"])

# Pydantic models
class EuriborRateCreate(BaseModel):
    date: date
    rate_12m: Optional[float] = None
    rate_6m: Optional[float] = None
    rate_3m: Optional[float] = None
    rate_1m: Optional[float] = None
    source: Optional[str] = None

class EuriborRateUpdate(BaseModel):
    rate_12m: Optional[float] = None
    rate_6m: Optional[float] = None
    rate_3m: Optional[float] = None
    rate_1m: Optional[float] = None
    source: Optional[str] = None

class EuriborRateResponse(BaseModel):
    id: int
    date: date
    rate_12m: Optional[float] = None
    rate_6m: Optional[float] = None
    rate_3m: Optional[float] = None
    rate_1m: Optional[float] = None
    source: Optional[str] = None
    created_at: Optional[date] = None

class BulkEuriborRatesCreate(BaseModel):
    rates: List[EuriborRateCreate]

@router.get("/", response_model=List[EuriborRateResponse])
def get_euribor_rates(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get Euribor rates with optional date filtering"""
    query = select(EuriborRate).order_by(EuriborRate.date.desc())
    
    if start_date:
        query = query.where(EuriborRate.date >= start_date)
    if end_date:
        query = query.where(EuriborRate.date <= end_date)
    
    rates = session.exec(query).all()
    return rates

@router.post("/", response_model=EuriborRateResponse)
def create_euribor_rate(
    rate_data: EuriborRateCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new Euribor rate entry"""
    # Check if rate already exists for this date
    existing = session.exec(
        select(EuriborRate).where(EuriborRate.date == rate_data.date)
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail=f"Rate already exists for date {rate_data.date}")
    
    rate = EuriborRate(**rate_data.dict(), created_at=date.today())
    session.add(rate)
    session.commit()
    session.refresh(rate)
    return rate

@router.post("/bulk", response_model=List[EuriborRateResponse])
def create_bulk_euribor_rates(
    bulk_data: BulkEuriborRatesCreate,
    overwrite: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create multiple Euribor rates at once (useful for copy/paste from Excel)"""
    created_rates = []
    updated_rates = []
    errors = []
    
    for rate_data in bulk_data.rates:
        try:
            # Check if rate already exists
            existing = session.exec(
                select(EuriborRate).where(EuriborRate.date == rate_data.date)
            ).first()
            
            if existing:
                if overwrite:
                    # Update existing rate
                    for field, value in rate_data.dict(exclude_unset=True).items():
                        if field != 'date':  # Don't update the date
                            setattr(existing, field, value)
                    updated_rates.append(existing)
                else:
                    errors.append(f"Rate already exists for date {rate_data.date}")
                    continue
            else:
                # Create new rate
                rate = EuriborRate(**rate_data.dict(), created_at=date.today())
                session.add(rate)
                created_rates.append(rate)
                
        except Exception as e:
            errors.append(f"Error processing date {rate_data.date}: {str(e)}")
            continue
    
    session.commit()
    
    # Refresh all created rates
    for rate in created_rates:
        session.refresh(rate)
    
    result = {
        "created": created_rates,
        "updated": updated_rates,
        "errors": errors,
        "total_processed": len(created_rates) + len(updated_rates),
        "total_errors": len(errors)
    }
    
    return result

@router.put("/{rate_id}", response_model=EuriborRateResponse)
def update_euribor_rate(
    rate_id: int,
    rate_data: EuriborRateUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update an existing Euribor rate"""
    rate = session.get(EuriborRate, rate_id)
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    
    # Update fields
    for field, value in rate_data.dict(exclude_unset=True).items():
        setattr(rate, field, value)
    
    session.commit()
    session.refresh(rate)
    return rate

@router.delete("/{rate_id}")
def delete_euribor_rate(
    rate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a Euribor rate"""
    rate = session.get(EuriborRate, rate_id)
    if not rate:
        raise HTTPException(status_code=404, detail="Rate not found")
    
    session.delete(rate)
    session.commit()
    return {"message": "Rate deleted successfully"}

@router.get("/latest", response_model=Optional[EuriborRateResponse])
def get_latest_euribor_rate(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get the most recent Euribor rate"""
    rate = session.exec(
        select(EuriborRate).order_by(EuriborRate.date.desc()).limit(1)
    ).first()
    
    return rate

@router.get("/by-date/{target_date}", response_model=Optional[EuriborRateResponse])
def get_euribor_rate_by_date(
    target_date: date,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get Euribor rate for a specific date (or closest previous date)"""
    # First try exact match
    rate = session.exec(
        select(EuriborRate).where(EuriborRate.date == target_date)
    ).first()
    
    if rate:
        return rate
    
    # If no exact match, get the closest previous date
    rate = session.exec(
        select(EuriborRate)
        .where(EuriborRate.date <= target_date)
        .order_by(EuriborRate.date.desc())
        .limit(1)
    ).first()
    
    return rate

# Utility endpoint for parsing CSV/Excel data
class ParsedEuriborData(BaseModel):
    parsed_data: List[EuriborRateCreate]
    errors: List[str]

@router.post("/parse-text", response_model=ParsedEuriborData)
def parse_euribor_text(
    text_data: str,
    date_format: str = "%Y-%m-%d",
    separator: str = "\t",
    current_user: User = Depends(get_current_user)
):
    """Parse text data (from copy/paste) into Euribor rate format"""
    lines = text_data.strip().split('\n')
    parsed_data = []
    errors = []
    
    for line_num, line in enumerate(lines, 1):
        try:
            parts = line.strip().split(separator)
            if len(parts) < 2:
                errors.append(f"Line {line_num}: Not enough columns")
                continue
            
            # Parse date (first column)
            from datetime import datetime
            try:
                parsed_date = datetime.strptime(parts[0].strip(), date_format).date()
            except ValueError:
                errors.append(f"Line {line_num}: Invalid date format '{parts[0]}'")
                continue
            
            # Parse rates (remaining columns)
            rate_data = {"date": parsed_date}
            
            # Map columns to rate types
            rate_fields = ["rate_12m", "rate_6m", "rate_3m", "rate_1m"]
            
            for i, field in enumerate(rate_fields):
                if i + 1 < len(parts) and parts[i + 1].strip():
                    try:
                        # Handle percentage format (remove % and convert)
                        rate_str = parts[i + 1].strip().replace('%', '').replace(',', '.')
                        rate_data[field] = float(rate_str)
                    except ValueError:
                        errors.append(f"Line {line_num}: Invalid rate value '{parts[i + 1]}'")
                        continue
            
            parsed_data.append(EuriborRateCreate(**rate_data))
            
        except Exception as e:
            errors.append(f"Line {line_num}: {str(e)}")
            continue
    
    return ParsedEuriborData(parsed_data=parsed_data, errors=errors)