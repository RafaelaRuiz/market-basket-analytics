"""GET /api/v1/customers — top clientes y features para segmentación."""

from datetime import date
from fastapi import APIRouter, Depends
from api.deps import DataStore, get_store
from api.filters import apply_filters

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/top")
def get_top_customers(
    n: int = 10,
    tienda: int | None = None,
    fecha_ini: date | None = None,
    fecha_fin: date | None = None,
    store: DataStore = Depends(get_store),
):
    """Top N clientes por total de ítems comprados."""
    flat_f = apply_filters(store.flat, tienda, fecha_ini, fecha_fin)
    top = (
        flat_f.groupby("id_cliente")["id_producto"]
        .count()
        .nlargest(n)
        .reset_index()
        .rename(columns={"id_producto": "total_items"})
    )
    return top.to_dict(orient="records")


@router.get("/features")
def get_customer_features(
    tienda: int | None = None,
    store: DataStore = Depends(get_store),
):
    """
    Features de comportamiento por cliente (para K-Means y boxplot).
    Filtro de tienda opcional (tienda principal del cliente).
    """
    df = store.customers
    if tienda is not None:
        df = df[df["id_tienda"] == tienda]
    return df.to_dict(orient="records")
