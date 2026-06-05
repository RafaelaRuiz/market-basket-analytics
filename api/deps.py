"""
Estado compartido de la aplicación FastAPI.

Los DataFrames procesados se cargan UNA SOLA VEZ al arrancar el servidor
y se reutilizan en todas las peticiones. Esto evita re-leer GCS en cada request.

Al terminar el ETL, el endpoint /api/v1/etl/reload fuerza una recarga
desde GCS para que los nuevos parquets sean visibles sin reiniciar el servidor.
"""

import os
import pandas as pd

_PROCESSED = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "processed")
)


class DataStore:
    """Contenedor singleton de los DataFrames en memoria."""

    flat:        pd.DataFrame | None = None
    customers:   pd.DataFrame | None = None
    daily:       pd.DataFrame | None = None
    products:    pd.DataFrame | None = None
    rules:       pd.DataFrame | None = None  # association_rules.parquet
    loaded:      bool = False


store = DataStore()


def _resolve(filename: str) -> str:
    bucket = os.environ.get("GCS_BUCKET", "").strip()
    if bucket:
        return f"gs://{bucket}/processed/{filename}"
    return os.path.join(_PROCESSED, filename)


def load_store():
    """
    Carga (o recarga) todos los DataFrames en el DataStore.
    Llamar al startup y cada vez que el ETL actualice los parquets.
    """
    store.flat      = pd.read_parquet(_resolve("transactions_flat.parquet"))
    store.customers = pd.read_parquet(_resolve("customer_features.parquet"))
    store.daily     = pd.read_parquet(_resolve("daily_summary.parquet"))
    store.products  = pd.read_parquet(_resolve("product_freq.parquet"))

    # Garantizar tipos de fecha
    store.flat["fecha"]  = pd.to_datetime(store.flat["fecha"])
    store.daily["fecha"] = pd.to_datetime(store.daily["fecha"])

    # Reglas de asociación (opcionales — se generan con precompute)
    rules_path = _resolve("association_rules.parquet")
    try:
        store.rules = pd.read_parquet(rules_path)
    except Exception:
        store.rules = None

    store.loaded = True


def get_store() -> DataStore:
    """Dependencia FastAPI: retorna el store con datos en memoria."""
    return store
