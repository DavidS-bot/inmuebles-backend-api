# app/routers/classification_rules.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel

from ..db import get_session
from ..deps import get_current_user
from ..models import User, Property, ClassificationRule, RentalContract

router = APIRouter(prefix="/classification-rules", tags=["classification-rules"])

# Pydantic models
class ClassificationRuleCreate(BaseModel):
    property_id: int
    keyword: str
    category: str  # "Renta", "Hipoteca", "Gasto"
    subcategory: Optional[str] = None
    tenant_name: Optional[str] = None

class ClassificationRuleUpdate(BaseModel):
    keyword: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    tenant_name: Optional[str] = None
    is_active: Optional[bool] = None

class ClassificationRuleResponse(BaseModel):
    id: int
    property_id: int
    keyword: str
    category: str
    subcategory: Optional[str] = None
    tenant_name: Optional[str] = None
    is_active: bool

class BulkClassificationRulesCreate(BaseModel):
    property_id: int
    rules: List[dict]

@router.get("/", response_model=List[ClassificationRuleResponse])
def get_classification_rules(
    property_id: Optional[int] = None,
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get classification rules with optional filters"""
    query = select(ClassificationRule).join(Property).where(Property.owner_id == current_user.id)
    
    if property_id:
        query = query.where(ClassificationRule.property_id == property_id)
    if category:
        query = query.where(ClassificationRule.category == category)
    if is_active is not None:
        query = query.where(ClassificationRule.is_active == is_active)
    
    rules = session.exec(query).all()
    return rules

@router.post("/", response_model=ClassificationRuleResponse)
def create_classification_rule(
    rule_data: ClassificationRuleCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create a new classification rule"""
    # Verify property ownership
    property_obj = session.get(Property, rule_data.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Validate category
    valid_categories = ["Renta", "Hipoteca", "Gasto"]
    if rule_data.category not in valid_categories:
        raise HTTPException(status_code=400, detail=f"Category must be one of: {', '.join(valid_categories)}")
    
    rule = ClassificationRule(**rule_data.dict())
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule

@router.get("/{rule_id}", response_model=ClassificationRuleResponse)
def get_classification_rule(
    rule_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get a specific classification rule"""
    rule = session.get(ClassificationRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Verify ownership through property
    property_obj = session.get(Property, rule.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return rule

@router.put("/{rule_id}", response_model=ClassificationRuleResponse)
def update_classification_rule(
    rule_id: int,
    rule_data: ClassificationRuleUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update a classification rule"""
    rule = session.get(ClassificationRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Verify ownership
    property_obj = session.get(Property, rule.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Validate category if provided
    if rule_data.category:
        valid_categories = ["Renta", "Hipoteca", "Gasto"]
        if rule_data.category not in valid_categories:
            raise HTTPException(status_code=400, detail=f"Category must be one of: {', '.join(valid_categories)}")
    
    # Update fields
    for field, value in rule_data.dict(exclude_unset=True).items():
        setattr(rule, field, value)
    
    session.commit()
    session.refresh(rule)
    return rule

@router.delete("/{rule_id}")
def delete_classification_rule(
    rule_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Delete a classification rule"""
    rule = session.get(ClassificationRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Verify ownership
    property_obj = session.get(Property, rule.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    session.delete(rule)
    session.commit()
    return {"message": "Classification rule deleted successfully"}

@router.post("/bulk", response_model=List[ClassificationRuleResponse])
def create_bulk_classification_rules(
    bulk_data: BulkClassificationRulesCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Create multiple classification rules at once"""
    # Verify property ownership
    property_obj = session.get(Property, bulk_data.property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Property not found")
    
    created_rules = []
    valid_categories = ["Renta", "Hipoteca", "Gasto"]
    
    for rule_data in bulk_data.rules:
        try:
            # Validate category
            category = rule_data.get("category", "")
            if category not in valid_categories:
                continue  # Skip invalid rules
            
            rule = ClassificationRule(
                property_id=bulk_data.property_id,
                keyword=rule_data.get("keyword", ""),
                category=category,
                subcategory=rule_data.get("subcategory"),
                tenant_name=rule_data.get("tenant_name"),
                is_active=rule_data.get("is_active", True)
            )
            session.add(rule)
            created_rules.append(rule)
        except Exception:
            # Skip invalid rules but continue processing
            continue
    
    session.commit()
    for rule in created_rules:
        session.refresh(rule)
    
    return created_rules

@router.get("/property/{property_id}/by-category")
def get_rules_by_category_for_property(
    property_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get classification rules grouped by category for a property"""
    # Verify property ownership
    property_obj = session.get(Property, property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Property not found")
    
    query = select(ClassificationRule).where(
        ClassificationRule.property_id == property_id,
        ClassificationRule.is_active == True
    )
    
    rules = session.exec(query).all()
    
    # Group by category
    grouped = {
        "Renta": [],
        "Hipoteca": [],
        "Gasto": []
    }
    
    for rule in rules:
        if rule.category in grouped:
            grouped[rule.category].append({
                "id": rule.id,
                "keyword": rule.keyword,
                "subcategory": rule.subcategory,
                "tenant_name": rule.tenant_name
            })
    
    return grouped

@router.post("/test-classification")
def test_classification_rules(
    property_id: int,
    test_concepts: List[str],
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Test how concepts would be classified with current rules"""
    # Verify property ownership
    property_obj = session.get(Property, property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Get active rules for the property
    query = select(ClassificationRule).where(
        ClassificationRule.property_id == property_id,
        ClassificationRule.is_active == True
    )
    rules = session.exec(query).all()
    
    results = []
    
    for concept in test_concepts:
        matched_rule = None
        concept_lower = concept.lower()
        
        # Find first matching rule
        for rule in rules:
            if rule.keyword.lower() in concept_lower:
                matched_rule = rule
                break
        
        result = {
            "concept": concept,
            "matched": matched_rule is not None,
            "category": matched_rule.category if matched_rule else "Sin clasificar",
            "subcategory": matched_rule.subcategory if matched_rule else None,
            "tenant_name": matched_rule.tenant_name if matched_rule else None,
            "keyword": matched_rule.keyword if matched_rule else None
        }
        
        results.append(result)
    
    return {"test_results": results}

@router.get("/property/{property_id}/suggestions")
def get_rule_suggestions_for_property(
    property_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get suggested classification rules based on rental contracts and common patterns"""
    # Verify property ownership
    property_obj = session.get(Property, property_id)
    if not property_obj or property_obj.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Property not found")
    
    suggestions = []
    
    # Get rental contracts for this property
    contracts_query = select(RentalContract).where(RentalContract.property_id == property_id)
    contracts = session.exec(contracts_query).all()
    
    # Generate rent-related suggestions based on contracts
    for contract in contracts:
        if contract.tenant_name:
            # Suggest rule based on tenant name
            suggestions.append({
                "keyword": contract.tenant_name,
                "category": "Renta",
                "subcategory": "Alquiler",
                "tenant_name": contract.tenant_name,
                "confidence": 90,
                "source": f"Contrato de alquiler activo",
                "suggested_keywords": [
                    contract.tenant_name,
                    contract.tenant_name.split()[0] if ' ' in contract.tenant_name else contract.tenant_name,
                    f"transferencia {contract.tenant_name.lower()}",
                    f"bizum {contract.tenant_name.lower()}"
                ]
            })
    
    # Common mortgage patterns
    mortgage_suggestions = [
        {
            "keyword": "hipoteca",
            "category": "Hipoteca",
            "subcategory": "Cuota hipoteca",
            "tenant_name": None,
            "confidence": 85,
            "source": "Patrón común de hipoteca",
            "suggested_keywords": [
                "hipoteca", "hipotecario", "prestamo hipotecario", 
                "cuota hipoteca", "adeudo hipoteca"
            ]
        },
        {
            "keyword": "banco santander",
            "category": "Hipoteca",
            "subcategory": "Cuota hipoteca",
            "tenant_name": None,
            "confidence": 75,
            "source": "Banco común para hipotecas",
            "suggested_keywords": ["santander", "banco santander"]
        },
        {
            "keyword": "bbva",
            "category": "Hipoteca",
            "subcategory": "Cuota hipoteca", 
            "tenant_name": None,
            "confidence": 75,
            "source": "Banco común para hipotecas",
            "suggested_keywords": ["bbva", "banco bbva"]
        }
    ]
    
    # Common expense patterns
    expense_suggestions = [
        {
            "keyword": "comunidad",
            "category": "Gasto",
            "subcategory": "Comunidad",
            "tenant_name": None,
            "confidence": 90,
            "source": "Gasto común de comunidad",
            "suggested_keywords": ["comunidad", "gastos comunidad", "cuota comunidad"]
        },
        {
            "keyword": "ibi",
            "category": "Gasto",
            "subcategory": "IBI",
            "tenant_name": None,
            "confidence": 95,
            "source": "Impuesto predial",
            "suggested_keywords": ["ibi", "impuesto bienes inmuebles", "tributos"]
        },
        {
            "keyword": "seguro hogar",
            "category": "Gasto",
            "subcategory": "Seguros",
            "tenant_name": None,
            "confidence": 85,
            "source": "Seguro común del hogar",
            "suggested_keywords": ["seguro hogar", "seguro vivienda", "poliza"]
        },
        {
            "keyword": "reparacion",
            "category": "Gasto",
            "subcategory": "Mantenimiento",
            "tenant_name": None,
            "confidence": 80,
            "source": "Gastos de reparación",
            "suggested_keywords": ["reparacion", "mantenimiento", "arreglo", "fontaneria", "electricidad"]
        }
    ]
    
    suggestions.extend(mortgage_suggestions)
    suggestions.extend(expense_suggestions)
    
    # Sort by confidence
    suggestions.sort(key=lambda x: x['confidence'], reverse=True)
    
    return {
        "property_id": property_id,
        "property_address": property_obj.address,
        "total_suggestions": len(suggestions),
        "rental_contracts_found": len(contracts),
        "suggestions": suggestions
    }