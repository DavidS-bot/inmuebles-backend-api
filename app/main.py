# app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
import os

from .db import init_db
from .routers import (
    properties, rules, movements, cashflow, auth,
    financial_movements, rental_contracts, mortgage_details, classification_rules, uploads, euribor_rates, analytics, mortgage_calculator, document_manager, notifications, tax_assistant, integrations, file_storage
)

app = FastAPI(title="Inmuebles API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir todos los orígenes para desarrollo local
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
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
app.include_router(file_storage.router)

# Global OPTIONS handler for CORS preflight
@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true"
        }
    )

@app.on_event("startup")
def on_startup():
    init_db()
    # Usar /uploads si existe (Render), sino usar local
    upload_dir = "/uploads" if os.path.exists("/uploads") else "uploads"
    os.makedirs(f"{upload_dir}/photo", exist_ok=True)
    os.makedirs(f"{upload_dir}/document", exist_ok=True)
    os.makedirs(f"{upload_dir}/tenant-document", exist_ok=True)

# Montar archivos estáticos desde la ruta correcta
upload_path = "/uploads" if os.path.exists("/uploads") else "uploads"
app.mount("/uploads", StaticFiles(directory=upload_path), name="uploads")

@app.get("/health")
def health():
    return {"status": "ok"}

# Force deploy 20250826_170951 - classification_rules and rental_contracts ready



