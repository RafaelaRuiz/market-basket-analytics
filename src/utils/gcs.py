"""
Helper para cargar datos procesados, ya sea desde GCS o desde el sistema
de archivos local (fallback automático).

La variable de entorno GCS_BUCKET controla la fuente:
  - Si está definida: lee desde gs://<GCS_BUCKET>/processed/
  - Si no está definida: lee desde data/processed/ (desarrollo local)
"""

import os
import streamlit as st
import pandas as pd

_LOCAL_PROCESSED = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "processed"
)

PARQUET_FILES = [
    "transactions_flat.parquet",
    "customer_features.parquet",
    "daily_summary.parquet",
    "product_freq.parquet",
]


def _resolve_path(filename: str) -> str:
    """Devuelve la ruta completa (GCS o local) para un parquet."""
    bucket = os.environ.get("GCS_BUCKET", "").strip()
    if bucket:
        return f"gs://{bucket}/processed/{filename}"
    return os.path.normpath(os.path.join(_LOCAL_PROCESSED, filename))


@st.cache_data(show_spinner="Cargando datos... (esto solo ocurre una vez)")
def load_all_data() -> dict:
    """
    Carga todos los DataFrames procesados.
    Resultado en caché por sesión de Streamlit.

    Returns:
        dict con claves: 'flat', 'customers', 'daily', 'products'
    """
    data = {
        "flat":      pd.read_parquet(_resolve_path("transactions_flat.parquet")),
        "customers": pd.read_parquet(_resolve_path("customer_features.parquet")),
        "daily":     pd.read_parquet(_resolve_path("daily_summary.parquet")),
        "products":  pd.read_parquet(_resolve_path("product_freq.parquet")),
    }
    # Asegurar tipos de fecha
    data["flat"]["fecha"] = pd.to_datetime(data["flat"]["fecha"])
    data["daily"]["fecha"] = pd.to_datetime(data["daily"]["fecha"])
    return data


def reload_data():
    """Limpia el caché y fuerza la recarga desde la fuente."""
    load_all_data.clear()
