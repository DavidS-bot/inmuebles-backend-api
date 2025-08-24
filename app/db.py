# app/db.py
from sqlmodel import SQLModel, create_engine, Session
from .config import settings
import os

# Importar todos los modelos para que SQLModel los reconozca
from .models import (
    User, Property, Rule, Movement, 
    FinancialMovement, RentalContract, 
    MortgageDetails, MortgageRevision, MortgagePrepayment,
    ClassificationRule
)

os.makedirs(settings.app_data_dir, exist_ok=True)

engine = create_engine(settings.database_url, pool_pre_ping=True)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
