# app/routers/document_manager.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
from sqlmodel import Session, select
from pydantic import BaseModel
import os
import uuid
import shutil
from pathlib import Path
from ..db import get_session
from ..deps import get_current_user
from ..models import Property, RentalContract, TenantDocument

router = APIRouter(prefix="/documents", tags=["document-manager"])

class DocumentAlert(BaseModel):
    type: str  # "contract_expiring", "document_missing", "renewal_due"
    message: str
    priority: str  # "high", "medium", "low"
    due_date: Optional[date] = None
    property_id: Optional[int] = None
    contract_id: Optional[int] = None

class DocumentTemplate(BaseModel):
    name: str
    type: str
    description: str
    required_fields: List[str]

@router.get("/alerts")
def get_document_alerts(
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Obtener alertas de documentos pendientes"""
    alerts = []
    today = date.today()
    
    # Obtener propiedades del usuario
    properties = session.exec(
        select(Property).where(Property.owner_id == current_user.id)
    ).all()
    
    for prop in properties:
        # Contratos próximos a vencer
        contracts = session.exec(
            select(RentalContract)
            .where(RentalContract.property_id == prop.id)
            .where(RentalContract.is_active == True)
        ).all()
        
        for contract in contracts:
            if contract.end_date:
                days_until_expiry = (contract.end_date - today).days
                
                if days_until_expiry <= 30 and days_until_expiry > 0:
                    alerts.append(DocumentAlert(
                        type="contract_expiring",
                        message=f"Contrato de {contract.tenant_name} vence en {days_until_expiry} días",
                        priority="high" if days_until_expiry <= 7 else "medium",
                        due_date=contract.end_date,
                        property_id=prop.id,
                        contract_id=contract.id
                    ))
                elif days_until_expiry <= 0:
                    alerts.append(DocumentAlert(
                        type="contract_expired",
                        message=f"Contrato de {contract.tenant_name} ha vencido",
                        priority="high",
                        due_date=contract.end_date,
                        property_id=prop.id,
                        contract_id=contract.id
                    ))
        
        # Documentos faltantes por contrato
        for contract in contracts:
            tenant_docs = session.exec(
                select(TenantDocument)
                .where(TenantDocument.rental_contract_id == contract.id)
            ).all()
            
            required_docs = ["dni", "payslip", "employment_contract", "bank_statement"]
            existing_doc_types = {doc.document_type for doc in tenant_docs}
            missing_docs = set(required_docs) - existing_doc_types
            
            for missing_doc in missing_docs:
                alerts.append(DocumentAlert(
                    type="document_missing",
                    message=f"Falta documento '{missing_doc}' de {contract.tenant_name}",
                    priority="medium",
                    property_id=prop.id,
                    contract_id=contract.id
                ))
    
    return {
        "alerts": alerts,
        "summary": {
            "total": len(alerts),
            "high_priority": len([a for a in alerts if a.priority == "high"]),
            "medium_priority": len([a for a in alerts if a.priority == "medium"]),
            "low_priority": len([a for a in alerts if a.priority == "low"])
        }
    }

@router.get("/property/{property_id}")
def get_property_documents(
    property_id: int,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Obtener todos los documentos de una propiedad"""
    # Verificar propiedad
    property_data = session.get(Property, property_id)
    if not property_data or property_data.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Propiedad no encontrada")
    
    # Obtener contratos y documentos
    contracts = session.exec(
        select(RentalContract)
        .where(RentalContract.property_id == property_id)
    ).all()
    
    documents_by_contract = {}
    
    for contract in contracts:
        tenant_docs = session.exec(
            select(TenantDocument)
            .where(TenantDocument.rental_contract_id == contract.id)
        ).all()
        
        documents_by_contract[contract.id] = {
            "contract_info": {
                "id": contract.id,
                "tenant_name": contract.tenant_name,
                "start_date": contract.start_date.isoformat(),
                "end_date": contract.end_date.isoformat() if contract.end_date else None,
                "is_active": contract.is_active,
                "contract_pdf": contract.contract_pdf_path
            },
            "documents": [
                {
                    "id": doc.id,
                    "type": doc.document_type,
                    "name": doc.document_name,
                    "upload_date": doc.upload_date.isoformat(),
                    "file_size": doc.file_size,
                    "description": doc.description
                }
                for doc in tenant_docs
            ]
        }
    
    return {
        "property_id": property_id,
        "property_address": property_data.address,
        "contracts": documents_by_contract
    }

@router.post("/upload/{contract_id}")
async def upload_document(
    contract_id: int,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    description: Optional[str] = Form(None),
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Subir documento para un contrato"""
    # Verificar contrato
    contract = session.get(RentalContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    
    # Verificar propiedad
    property_data = session.get(Property, contract.property_id)
    if not property_data or property_data.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    # Validar tipo de archivo
    allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx'}
    file_extension = Path(file.filename).suffix.lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Tipo de archivo no permitido. Permitidos: {allowed_extensions}"
        )
    
    # Crear directorio si no existe
    upload_dir = Path("uploads/documents")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generar nombre único
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}_{file.filename}"
    file_path = upload_dir / safe_filename
    
    try:
        # Guardar archivo
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Crear registro en base de datos
        tenant_doc = TenantDocument(
            rental_contract_id=contract_id,
            document_type=document_type,
            document_name=file.filename,
            file_path=str(file_path),
            file_size=file.size,
            description=description
        )
        
        session.add(tenant_doc)
        session.commit()
        session.refresh(tenant_doc)
        
        return {
            "id": tenant_doc.id,
            "message": "Documento subido exitosamente",
            "document": {
                "name": tenant_doc.document_name,
                "type": tenant_doc.document_type,
                "size": tenant_doc.file_size,
                "upload_date": tenant_doc.upload_date.isoformat()
            }
        }
        
    except Exception as e:
        # Limpiar archivo si algo sale mal
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Error al subir archivo: {str(e)}")

@router.delete("/document/{document_id}")
def delete_document(
    document_id: int,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Eliminar documento"""
    # Obtener documento
    document = session.get(TenantDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    
    # Verificar permisos
    contract = session.get(RentalContract, document.rental_contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    
    property_data = session.get(Property, contract.property_id)
    if not property_data or property_data.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    # Eliminar archivo físico
    file_path = Path(document.file_path)
    if file_path.exists():
        file_path.unlink()
    
    # Eliminar registro
    session.delete(document)
    session.commit()
    
    return {"message": "Documento eliminado exitosamente"}

@router.get("/templates")
def get_document_templates():
    """Obtener plantillas de documentos disponibles"""
    templates = [
        DocumentTemplate(
            name="Contrato de Arrendamiento",
            type="rental_contract",
            description="Plantilla estándar de contrato de alquiler",
            required_fields=["tenant_name", "property_address", "monthly_rent", "start_date", "end_date", "deposit"]
        ),
        DocumentTemplate(
            name="Inventario de Mobiliario",
            type="inventory",
            description="Lista detallada del mobiliario incluido",
            required_fields=["property_address", "tenant_name", "inventory_items", "condition"]
        ),
        DocumentTemplate(
            name="Recibo de Depósito",
            type="deposit_receipt",
            description="Comprobante de pago de fianza",
            required_fields=["tenant_name", "deposit_amount", "payment_date", "property_address"]
        ),
        DocumentTemplate(
            name="Comunicación de Finalización",
            type="termination_notice",
            description="Aviso de terminación de contrato",
            required_fields=["tenant_name", "property_address", "termination_date", "reason"]
        )
    ]
    
    return {
        "templates": templates,
        "categories": {
            "contracts": ["rental_contract"],
            "receipts": ["deposit_receipt"],
            "notices": ["termination_notice"],
            "inventories": ["inventory"]
        }
    }

@router.post("/generate-template")
def generate_document_from_template(
    template_type: str,
    contract_id: int,
    custom_fields: Dict = {},
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """Generar documento desde plantilla"""
    # Verificar contrato
    contract = session.get(RentalContract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    
    # Verificar propiedad
    property_data = session.get(Property, contract.property_id)
    if not property_data or property_data.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    # Plantillas básicas (en producción usar un motor de plantillas como Jinja2)
    templates = {
        "rental_contract": generate_rental_contract_content(contract, property_data, custom_fields),
        "inventory": generate_inventory_content(contract, property_data, custom_fields),
        "deposit_receipt": generate_deposit_receipt_content(contract, property_data, custom_fields),
        "termination_notice": generate_termination_notice_content(contract, property_data, custom_fields)
    }
    
    if template_type not in templates:
        raise HTTPException(status_code=400, detail="Tipo de plantilla no válido")
    
    content = templates[template_type]
    
    return {
        "template_type": template_type,
        "content": content,
        "generated_date": datetime.now().isoformat(),
        "contract_info": {
            "tenant_name": contract.tenant_name,
            "property_address": property_data.address
        }
    }

def generate_rental_contract_content(contract: RentalContract, property_data: Property, custom_fields: Dict) -> str:
    """Generar contenido de contrato de alquiler"""
    return f"""
CONTRATO DE ARRENDAMIENTO

Entre el arrendador y {contract.tenant_name}, como arrendatario, se acuerda:

1. OBJETO: El arrendamiento de la vivienda ubicada en {property_data.address}

2. DURACIÓN: Desde {contract.start_date} hasta {contract.end_date or 'indefinido'}

3. RENTA: €{contract.monthly_rent} mensuales

4. FIANZA: €{contract.deposit or 'A convenir'}

5. CONDICIONES ADICIONALES:
{custom_fields.get('additional_conditions', '')}

Fecha de generación: {datetime.now().strftime('%d/%m/%Y')}
"""

def generate_inventory_content(contract: RentalContract, property_data: Property, custom_fields: Dict) -> str:
    """Generar inventario de mobiliario"""
    return f"""
INVENTARIO DE MOBILIARIO

Propiedad: {property_data.address}
Inquilino: {contract.tenant_name}
Fecha: {datetime.now().strftime('%d/%m/%Y')}

MOBILIARIO INCLUIDO:
{custom_fields.get('inventory_items', '- A completar')}

ESTADO: {custom_fields.get('condition', 'Bueno')}
"""

def generate_deposit_receipt_content(contract: RentalContract, property_data: Property, custom_fields: Dict) -> str:
    """Generar recibo de fianza"""
    return f"""
RECIBO DE FIANZA

He recibido de {contract.tenant_name} la cantidad de €{contract.deposit or custom_fields.get('deposit_amount', '0')}
como fianza correspondiente al alquiler de {property_data.address}

Fecha: {custom_fields.get('payment_date', datetime.now().strftime('%d/%m/%Y'))}

Firmado: ________________
"""

def generate_termination_notice_content(contract: RentalContract, property_data: Property, custom_fields: Dict) -> str:
    """Generar aviso de terminación"""
    return f"""
COMUNICACIÓN DE FINALIZACIÓN DE CONTRATO

Estimado/a {contract.tenant_name},

Le comunicamos que el contrato de arrendamiento de {property_data.address}
finalizará el {custom_fields.get('termination_date', 'fecha a especificar')}.

Motivo: {custom_fields.get('reason', 'Finalización natural del contrato')}

Fecha de comunicación: {datetime.now().strftime('%d/%m/%Y')}
"""