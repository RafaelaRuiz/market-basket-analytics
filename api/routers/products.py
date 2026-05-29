"""GET /api/v1/products — frecuencia de productos y top N."""

from datetime import date
from fastapi import APIRouter, Depends
from api.deps import DataStore, get_store
from api.filters import apply_filters
from src.etl.transformer import build_product_freq

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/top")
def get_top_products(
    n: int = 10,
    tienda: int | None = None,
    fecha_ini: date | None = None,
    fecha_fin: date | None = None,
    store: DataStore = Depends(get_store),
):
    """
    Top N productos por frecuencia absoluta.
    Si se aplican filtros de tienda/fecha, recalcula sobre el subconjunto.
    Si no hay filtros, usa el parquet pre-calculado directamente.
    """
    if tienda is None and fecha_ini is None and fecha_fin is None:
        df = store.products.head(n)
    else:
        flat_f = apply_filters(store.flat, tienda, fecha_ini, fecha_fin)
        df = build_product_freq(flat_f).head(n)

    return df.to_dict(orient="records")
