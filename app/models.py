# app/models.py
from typing import Optional, List
from datetime import date
from sqlmodel import SQLModel, Field, Relationship

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str
    hashed_password: str
    is_active: bool = True

    properties: List["Property"] = Relationship(back_populates="owner")

class Property(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id")
    address: str
    rooms: Optional[int] = None
    m2: Optional[int] = None
    photo: Optional[str] = None
    
    # Campos financieros adicionales
    property_type: Optional[str] = None  # "Piso", "Unifamiliar", etc.
    purchase_date: Optional[date] = None
    purchase_price: Optional[float] = None
    appraisal_value: Optional[float] = None
    down_payment: Optional[float] = None  # Entrada/enganche pagado
    acquisition_costs: Optional[float] = None  # Gastos de compra (notaría, impuestos, etc.)
    renovation_costs: Optional[float] = None  # Costos de renovación

    owner: Optional[User] = Relationship(back_populates="properties")
    rules: List["Rule"] = Relationship(back_populates="property")
    movements: List["Movement"] = Relationship(back_populates="property")
    
    # Nuevas relaciones financieras
    mortgage_details: Optional["MortgageDetails"] = Relationship(back_populates="property")
    rental_contracts: List["RentalContract"] = Relationship(back_populates="property")
    financial_movements: List["FinancialMovement"] = Relationship(back_populates="property")
    classification_rules: List["ClassificationRule"] = Relationship(back_populates="property")

class Rule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    property_id: int = Field(foreign_key="property.id")
    name: str
    match_text: str
    category: str  # "mortgage", "rent", "tax", "insurance", "hoa", "maintenance", "management", "utilities", "other"

    property: Optional[Property] = Relationship(back_populates="rules")

class Movement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    property_id: int = Field(foreign_key="property.id")
    date: date
    concept: str
    amount: float            # + ingreso, - gasto
    category: Optional[str] = None  # si ya viene categorizado

    property: Optional[Property] = Relationship(back_populates="movements")

class FinancialMovement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")  # Owner of the movement
    property_id: Optional[int] = Field(default=None, foreign_key="property.id")  # Can be null initially
    date: date
    concept: str
    amount: float
    category: str  # "Renta", "Hipoteca", "Gasto"
    subcategory: Optional[str] = None  # Para gastos: "Comunidad", "IBI", etc.
    tenant_name: Optional[str] = None  # Para rentas
    is_classified: bool = True  # Si fue clasificado automáticamente
    bank_balance: Optional[float] = None  # Saldo después del movimiento
    
    user: Optional[User] = Relationship()
    property: Optional[Property] = Relationship(back_populates="financial_movements")

class RentalContract(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    property_id: int = Field(foreign_key="property.id")
    tenant_name: str
    start_date: date
    end_date: Optional[date] = None
    monthly_rent: float
    deposit: Optional[float] = None
    contract_pdf_path: Optional[str] = None
    contract_file_name: Optional[str] = None
    is_active: bool = True
    
    # Información adicional del inquilino
    tenant_email: Optional[str] = None
    tenant_phone: Optional[str] = None
    tenant_dni: Optional[str] = None
    tenant_address: Optional[str] = None
    monthly_income: Optional[float] = None
    job_position: Optional[str] = None
    employer_name: Optional[str] = None
    
    property: Optional[Property] = Relationship(back_populates="rental_contracts")
    tenant_documents: List["TenantDocument"] = Relationship(back_populates="rental_contract")

class TenantDocument(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    rental_contract_id: int = Field(foreign_key="rentalcontract.id")
    document_type: str  # "dni", "payslip", "employment_contract", "bank_statement", "other"
    document_name: str  # Nombre del archivo
    file_path: str  # Ruta donde se almacena el archivo
    file_size: Optional[int] = None  # Tamaño en bytes
    upload_date: date = Field(default_factory=lambda: date.today())
    description: Optional[str] = None  # Descripción opcional del documento
    
    rental_contract: Optional[RentalContract] = Relationship(back_populates="tenant_documents")

class MortgageDetails(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    property_id: int = Field(foreign_key="property.id", unique=True)
    loan_id: Optional[str] = None
    bank_entity: Optional[str] = None
    mortgage_type: str = "Variable"  # "Variable" o "Fija"
    initial_amount: float
    outstanding_balance: float
    margin_percentage: float
    start_date: date
    end_date: date
    review_period_months: int = 12
    
    property: Optional[Property] = Relationship(back_populates="mortgage_details")
    revisions: List["MortgageRevision"] = Relationship(back_populates="mortgage")
    prepayments: List["MortgagePrepayment"] = Relationship(back_populates="mortgage")

class MortgageRevision(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    mortgage_id: int = Field(foreign_key="mortgagedetails.id")
    effective_date: date
    euribor_rate: Optional[float] = None
    margin_rate: float
    period_months: int
    
    mortgage: Optional[MortgageDetails] = Relationship(back_populates="revisions")

class MortgagePrepayment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    mortgage_id: int = Field(foreign_key="mortgagedetails.id")
    payment_date: date
    amount: float
    
    mortgage: Optional[MortgageDetails] = Relationship(back_populates="prepayments")

class ClassificationRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    property_id: int = Field(foreign_key="property.id")
    keyword: str  # Palabra clave a buscar en el concepto
    category: str  # "Renta", "Hipoteca", "Gasto"
    subcategory: Optional[str] = None  # Para gastos específicos
    tenant_name: Optional[str] = None  # Para asociar rentas a inquilinos
    is_active: bool = True
    
    property: Optional[Property] = Relationship(back_populates="classification_rules")

class EuriborRate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: date  # Fecha de la tasa (normalmente primer día del mes)
    rate_12m: Optional[float] = None  # Tasa Euribor a 12 meses
    rate_6m: Optional[float] = None   # Tasa Euribor a 6 meses
    rate_3m: Optional[float] = None   # Tasa Euribor a 3 meses
    rate_1m: Optional[float] = None   # Tasa Euribor a 1 mes
    source: Optional[str] = None      # Fuente de los datos
    created_at: Optional[date] = None # Fecha de creación del registro

