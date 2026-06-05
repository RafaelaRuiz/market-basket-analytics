"""
GET /api/v1/segmentation/kmeans  — pipeline K-Means sobre features de clientes.

El cálculo se realiza en cada llamada (scikit-learn es rápido sobre 158 K clientes).
El frontend añade su propio st.cache_data para evitar recómputos repetidos.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from api.deps import DataStore, get_store
from src.analytics.segmentation import AVAILABLE_FEATURES, get_kmeans_results

router = APIRouter(prefix="/segmentation", tags=["segmentation"])


@router.get("/kmeans")
def kmeans(
    k: int = Query(default=3, ge=2, le=8, description="Número de clusters"),
    features: list[str] = Query(
        default=AVAILABLE_FEATURES,
        description="Features a usar en la segmentación",
    ),
    tienda: int | None = Query(default=None, description="Filtrar clientes por tienda principal"),
    store: DataStore = Depends(get_store),
):
    """
    Ejecuta K-Means con k clusters sobre las features seleccionadas.

    Retorna: labels, coordenadas PCA, centroides, estadísticas por segmento,
    curva de inercia e interpretación textual.
    """
    invalid = [f for f in features if f not in AVAILABLE_FEATURES]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Features inválidas: {invalid}. Disponibles: {AVAILABLE_FEATURES}",
        )

    df = store.customers.copy()
    if tienda is not None:
        df = df[df["id_tienda"] == tienda]

    if len(df) < k:
        raise HTTPException(
            status_code=400,
            detail=f"No hay suficientes clientes ({len(df)}) para {k} clusters.",
        )

    result = get_kmeans_results(df, features, k)
    return result


@router.get("/features")
def available_features():
    """Lista de features disponibles para segmentación."""
    from src.analytics.segmentation import FEATURE_LABELS
    return [{"id": f, "label": FEATURE_LABELS[f]} for f in AVAILABLE_FEATURES]
