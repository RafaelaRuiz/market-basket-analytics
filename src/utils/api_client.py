"""
Cliente HTTP para consumir la FastAPI desde Streamlit.

Lee la variable de entorno API_URL (default: http://localhost:8000).
Todas las funciones retornan DataFrames de pandas listos para usar en
las funciones de visualización.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd
import requests

_API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
_PREFIX  = f"{_API_URL}/api/v1"
_TIMEOUT = 30  # segundos


def _get(endpoint: str, params: dict | None = None) -> list | dict:
    """Hace GET a {_PREFIX}/{endpoint} y retorna el JSON parseado."""
    url = f"{_PREFIX}/{endpoint}"
    resp = requests.get(url, params={k: v for k, v in (params or {}).items()
                                     if v is not None}, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _post(endpoint: str, json_body: dict | None = None) -> dict:
    url = f"{_PREFIX}/{endpoint}"
    resp = requests.post(url, json=json_body or {}, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _build_params(tienda=None, fecha_ini=None, fecha_fin=None) -> dict:
    return {
        "tienda":    tienda if tienda != "Todas" else None,
        "fecha_ini": fecha_ini.isoformat() if isinstance(fecha_ini, date) else fecha_ini,
        "fecha_fin": fecha_fin.isoformat() if isinstance(fecha_fin, date) else fecha_fin,
    }


# ─── Summary ─────────────────────────────────────────────────────────────────

def get_summary(tienda=None, fecha_ini=None, fecha_fin=None) -> dict:
    """KPIs principales: totales, clientes, deltas."""
    return _get("summary", _build_params(tienda, fecha_ini, fecha_fin))


def get_executive_summary_data(tienda=None, fecha_ini=None, fecha_fin=None) -> dict:
    """
    Carga en paralelo los datasets usados por Resumen Ejecutivo.

    Streamlit renderiza de arriba hacia abajo; si cada grafica dispara su propia
    consulta, el usuario ve la pagina aparecer por partes. Este helper reduce la
    espera total y entrega un bloque completo para pintar toda la vista.
    """
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            "summary": executor.submit(get_summary, tienda, fecha_ini, fecha_fin),
            "top_products": executor.submit(
                get_top_products, 10, tienda, fecha_ini, fecha_fin
            ),
            "top_customers": executor.submit(
                get_top_customers, 10, tienda, fecha_ini, fecha_fin
            ),
            "daily": executor.submit(get_daily, tienda, fecha_ini, fecha_fin),
            "categories": executor.submit(get_categories, tienda, fecha_ini, fecha_fin),
        }
        return {key: future.result() for key, future in futures.items()}


# ─── Products ────────────────────────────────────────────────────────────────

def get_top_products(n=10, tienda=None, fecha_ini=None,
                     fecha_fin=None) -> pd.DataFrame:
    data = _get("products/top",
                {"n": n, **_build_params(tienda, fecha_ini, fecha_fin)})
    return pd.DataFrame(data)


# ─── Customers ───────────────────────────────────────────────────────────────

def get_top_customers(n=10, tienda=None, fecha_ini=None,
                      fecha_fin=None) -> pd.DataFrame:
    data = _get("customers/top",
                {"n": n, **_build_params(tienda, fecha_ini, fecha_fin)})
    return pd.DataFrame(data)


def get_customer_features(tienda=None) -> pd.DataFrame:
    params = {"tienda": tienda if tienda != "Todas" else None}
    data = _get("customers/features", params)
    return pd.DataFrame(data)


# ─── Daily ───────────────────────────────────────────────────────────────────

def get_daily(tienda=None, fecha_ini=None, fecha_fin=None) -> pd.DataFrame:
    data = _get("daily", _build_params(tienda, fecha_ini, fecha_fin))
    df = pd.DataFrame(data)
    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"])
    return df


# ─── Categories ──────────────────────────────────────────────────────────────

def get_categories(tienda=None, fecha_ini=None, fecha_fin=None) -> pd.DataFrame:
    data = _get("categories", _build_params(tienda, fecha_ini, fecha_fin))
    return pd.DataFrame(data)


def get_category_evolution(tienda=None, fecha_ini=None, fecha_fin=None,
                            top_n=5) -> pd.DataFrame:
    data = _get("categories/evolution",
                {"top_n": top_n, **_build_params(tienda, fecha_ini, fecha_fin)})
    df = pd.DataFrame(data)
    if not df.empty:
        df["semana"] = pd.to_datetime(df["semana"])
    return df


def get_analytics_data(tienda=None, fecha_ini=None, fecha_fin=None) -> dict:
    """Carga en paralelo los datos compartidos por las visualizaciones."""
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            "daily": executor.submit(get_daily, tienda, fecha_ini, fecha_fin),
            "category_evolution": executor.submit(
                get_category_evolution, tienda, fecha_ini, fecha_fin
            ),
            "customer_features": executor.submit(get_customer_features, tienda),
        }
        return {key: future.result() for key, future in futures.items()}


# ─── Segmentación ────────────────────────────────────────────────────────────

def get_kmeans(
    k: int = 3,
    features: list[str] | None = None,
    tienda: int | None = None,
) -> dict:
    """
    Ejecuta K-Means con k clusters.
    Retorna dict con labels, coordenadas PCA, centroides, stats, inertia_curve.
    """
    from src.analytics.segmentation import AVAILABLE_FEATURES
    feat = features or AVAILABLE_FEATURES
    params = {"k": k, "features": feat}
    if tienda is not None:
        params["tienda"] = tienda
    return _get("segmentation/kmeans", params)


def get_segmentation_features() -> list[dict]:
    """Lista de features disponibles para segmentación."""
    return _get("segmentation/features")


# ─── Recomendador ─────────────────────────────────────────────────────────────

def get_products_with_rules() -> list[int]:
    """Productos que aparecen como antecedentes en las reglas de asociación."""
    return _get("recommender/products")


def get_available_customers() -> list[int]:
    """IDs de clientes disponibles para recomendaciones personalizadas."""
    return _get("recommender/customers")


def get_rules_for_product(product_id: int, top_n: int = 10) -> pd.DataFrame:
    """Reglas de asociación para un producto dado."""
    data = _get(f"recommender/rules/{product_id}", {"top_n": top_n})
    return pd.DataFrame(data)


def get_recommendations_for_customer(
    customer_id: int, top_n: int = 5
) -> pd.DataFrame:
    """Categorías recomendadas para un cliente por similitud coseno."""
    data = _get(f"recommender/customer/{customer_id}", {"top_n": top_n})
    return pd.DataFrame(data)


# ─── ETL control ─────────────────────────────────────────────────────────────

def upload_csv(file_bytes: bytes, filename: str) -> dict:
    url = f"{_PREFIX}/etl/upload"
    resp = requests.post(
        url,
        files={"file": (filename, file_bytes, "text/csv")},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def trigger_etl() -> dict:
    return _post("etl/trigger")


def reload_data() -> dict:
    return _post("etl/reload")


def get_etl_status() -> dict:
    return _get("etl/status")
