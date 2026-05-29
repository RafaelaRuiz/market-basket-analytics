"""GET /api/v1/categories — distribución y evolución de categorías."""

from datetime import date
from fastapi import APIRouter, Depends
from api.deps import DataStore, get_store
from api.filters import apply_filters

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
def get_categories(
    tienda: int | None = None,
    fecha_ini: date | None = None,
    fecha_fin: date | None = None,
    store: DataStore = Depends(get_store),
):
    """Frecuencia total por categoría (para pie chart)."""
    flat_f = apply_filters(store.flat, tienda, fecha_ini, fecha_fin)
    df = (
        flat_f.groupby("nombre_categoria")["id_producto"]
        .count()
        .reset_index()
        .rename(columns={"id_producto": "frecuencia"})
        .sort_values("frecuencia", ascending=False)
    )
    return df.to_dict(orient="records")


@router.get("/evolution")
def get_category_evolution(
    tienda: int | None = None,
    fecha_ini: date | None = None,
    fecha_fin: date | None = None,
    top_n: int = 5,
    store: DataStore = Depends(get_store),
):
    """Evolución semanal de las top N categorías."""
    flat_f = apply_filters(store.flat, tienda, fecha_ini, fecha_fin)

    top_cats = (
        flat_f.groupby("nombre_categoria")["id_producto"]
        .count()
        .nlargest(top_n)
        .index.tolist()
    )
    df_top = flat_f[flat_f["nombre_categoria"].isin(top_cats)].copy()
    df_top["semana"] = df_top["fecha"].dt.to_period("W").dt.start_time

    evol = (
        df_top.groupby(["semana", "nombre_categoria"])["id_producto"]
        .count()
        .reset_index()
        .rename(columns={"id_producto": "frecuencia"})
    )
    evol["semana"] = evol["semana"].dt.strftime("%Y-%m-%d")
    return evol.to_dict(orient="records")
