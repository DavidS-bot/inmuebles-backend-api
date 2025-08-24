# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import (
    properties, rules, movements, cashflow, auth,
    financial_movements, rental_contracts, mortgage_details, classification_rules, uploads, euribor_rates, analytics, mortgage_calculator, document_manager, notifications, tax_assistant, integrations
)

app = FastAPI(title="Inmuebles API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir todos los orígenes para desarrollo local
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(properties.router)
app.include_router(rules.router)
app.include_router(movements.router)
app.include_router(cashflow.router)

# Financial Agent Routers
app.include_router(financial_movements.router)
app.include_router(rental_contracts.router)
app.include_router(mortgage_details.router)
app.include_router(classification_rules.router)
app.include_router(euribor_rates.router)
app.include_router(uploads.router)
app.include_router(analytics.router)
app.include_router(mortgage_calculator.router)
app.include_router(document_manager.router)
app.include_router(notifications.router)
app.include_router(tax_assistant.router)
app.include_router(integrations.router)

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}

# Endpoint temporal removido para evitar errores



