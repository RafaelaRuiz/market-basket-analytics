"""
FastAPI — Market Basket Analytics API

Carga los datos en memoria al arrancar y expone endpoints REST
para que el dashboard Streamlit consuma sin tocar GCS directamente.

Ejecución local:
    uvicorn api.main:app --reload --port 8000

Variables de entorno:
    GCS_BUCKET           nombre del bucket (sin gs://)
    GOOGLE_CLOUD_PROJECT ID del proyecto GCloud
    ETL_JOB_NAME         nombre del Cloud Run Job (default: market-basket-etl)
    CLOUD_RUN_REGION     región de Cloud Run (default: us-central1)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import load_store
from api.routers import summary, products, customers, daily, categories, etl


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carga los parquets en memoria una sola vez al arrancar."""
    print("[api] Cargando datasets en memoria...", flush=True)
    load_store()
    print("[api] ✅ Datos cargados. API lista.", flush=True)
    yield
    print("[api] Apagando servidor.", flush=True)


app = FastAPI(
    title="Market Basket Analytics API",
    description="API REST que expone datos procesados de transacciones de supermercado.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: permite peticiones desde el dashboard Streamlit (mismo VPC en Cloud Run)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers bajo /api/v1
PREFIX = "/api/v1"
app.include_router(summary.router,    prefix=PREFIX)
app.include_router(products.router,   prefix=PREFIX)
app.include_router(customers.router,  prefix=PREFIX)
app.include_router(daily.router,      prefix=PREFIX)
app.include_router(categories.router, prefix=PREFIX)
app.include_router(etl.router,        prefix=PREFIX)


@app.get("/health")
def health():
    """Health check para Cloud Run."""
    return {"status": "ok"}


@app.get("/")
def root():
    return {
        "service": "Market Basket Analytics API",
        "docs":    "/docs",
        "health":  "/health",
    }
