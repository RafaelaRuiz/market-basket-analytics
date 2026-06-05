"""
GET /api/v1/recommender/...  — endpoints de recomendación.

  /products          lista de productos con reglas disponibles
  /rules/{product_id} reglas de asociación para un producto
  /customer/{customer_id} categorías recomendadas por similitud coseno
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from api.deps import DataStore, get_store
from src.analytics.recommender import recommend_for_product, recommend_for_customer

router = APIRouter(prefix="/recommender", tags=["recommender"])


@router.get("/products")
def get_products_with_rules(
    store: DataStore = Depends(get_store),
):
    """
    Lista de IDs de productos que aparecen como antecedentes en las reglas.
    Si no hay reglas calculadas, retorna lista vacía.
    """
    if store.rules is None or store.rules.empty:
        return []

    product_ids = sorted({
        int(pid)
        for ant_list in store.rules["antecedents"]
        for pid in ant_list
    })
    return product_ids


@router.get("/customers")
def get_available_customers(
    store: DataStore = Depends(get_store),
):
    """
    Lista de IDs de clientes disponibles en los datos.
    Útil para selectbox en la UI de recomendaciones por cliente.
    """
    if store.customers is None or store.customers.empty:
        return []

    customer_ids = sorted(store.customers["id_cliente"].unique().tolist())
    return [int(c) for c in customer_ids]


@router.get("/rules/{product_id}")
def get_rules_for_product(
    product_id: int,
    top_n: int = Query(default=10, ge=1, le=50),
    store: DataStore = Depends(get_store),
):
    """
    Reglas de asociación donde el antecedente contiene product_id.
    Ordenadas por lift descendente.
    """
    if store.rules is None or store.rules.empty:
        raise HTTPException(
            status_code=503,
            detail="Reglas de asociación no disponibles. Ejecuta precompute con --force.",
        )

    result = recommend_for_product(product_id, store.rules, top_n=top_n)
    if result.empty:
        return []

    records = result.to_dict(orient="records")
    for rec in records:
        rec["antecedents"] = [int(x) for x in rec["antecedents"]]
        rec["consequents"] = [int(x) for x in rec["consequents"]]
    return records


@router.get("/customer/{customer_id}")
def get_recommendations_for_customer(
    customer_id: int,
    top_n: int = Query(default=5, ge=1, le=20),
    store: DataStore = Depends(get_store),
):
    """
    Categorías recomendadas para un cliente usando similitud coseno
    sobre una matriz cliente × categoría (TruncatedSVD).
    """
    recs = recommend_for_customer(customer_id, store.flat, top_n=top_n)

    if not recs:
        # Verificar si el cliente existe
        if customer_id not in store.customers["id_cliente"].values:
            raise HTTPException(
                status_code=404,
                detail=f"Cliente {customer_id} no encontrado en los datos.",
            )
        return []

    return recs
