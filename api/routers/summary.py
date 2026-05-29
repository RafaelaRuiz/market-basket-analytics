"""GET /api/v1/summary — KPIs principales."""

from datetime import date
from fastapi import APIRouter, Depends
from api.deps import DataStore, get_store
from api.filters import apply_filters

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("")
def get_summary(
    tienda: int | None = None,
    fecha_ini: date | None = None,
    fecha_fin: date | None = None,
    store: DataStore = Depends(get_store),
):
    flat  = apply_filters(store.flat,  tienda, fecha_ini, fecha_fin)
    daily = apply_filters(store.daily, tienda, fecha_ini, fecha_fin)

    total_items  = int(len(flat))
    total_trans  = int(daily["n_transacciones"].sum())
    clientes     = int(flat["id_cliente"].nunique())
    categorias   = int(flat["nombre_categoria"].nunique())

    # Delta: primera mitad del período vs segunda mitad
    fechas = flat["fecha"].sort_values()
    delta_items_pct = delta_trans_pct = None
    if len(fechas) > 1:
        mid = fechas.iloc[len(fechas) // 2]
        h1_items = int((flat["fecha"] <= mid).sum())
        h2_items = int((flat["fecha"] > mid).sum())
        delta_items_pct = round((h2_items - h1_items) / max(h1_items, 1) * 100, 1)

        h1_trans = int(daily[daily["fecha"] <= mid]["n_transacciones"].sum())
        h2_trans = int(daily[daily["fecha"] > mid]["n_transacciones"].sum())
        delta_trans_pct = round((h2_trans - h1_trans) / max(h1_trans, 1) * 100, 1)

    return {
        "total_items":       total_items,
        "total_transacciones": total_trans,
        "clientes_unicos":   clientes,
        "categorias_activas": categorias,
        "delta_items_pct":   delta_items_pct,
        "delta_trans_pct":   delta_trans_pct,
    }
