"""GET /api/v1/daily — resumen diario para series de tiempo y heatmap."""

from datetime import date
from fastapi import APIRouter, Depends
from api.deps import DataStore, get_store
from api.filters import apply_filters

router = APIRouter(prefix="/daily", tags=["daily"])


@router.get("")
def get_daily(
    tienda: int | None = None,
    fecha_ini: date | None = None,
    fecha_fin: date | None = None,
    store: DataStore = Depends(get_store),
):
    """Resumen diario (n_transacciones, n_items, n_clientes) por fecha y tienda."""
    df = apply_filters(store.daily, tienda, fecha_ini, fecha_fin)
    # Serializar fechas como string ISO
    df = df.copy()
    df["fecha"] = df["fecha"].dt.strftime("%Y-%m-%d")
    return df.to_dict(orient="records")
