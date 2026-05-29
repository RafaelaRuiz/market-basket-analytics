"""
Transformaciones sobre los datos crudos de transacciones:
- Explosión de baskets (una fila por item)
- Mapeo a categorías
- Construcción de features analíticos
"""

import pandas as pd
import numpy as np


def explode_baskets(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Transforma cada fila (una transacción con N productos) en N filas
    (una por producto). Agrega columnas de tiempo auxiliares.

    Entrada:  fecha | id_tienda | id_cliente | basket_raw ('p1 p2 p3')
    Salida:   fecha | id_tienda | id_cliente | id_producto | dia_semana | semana | mes
    """
    df = df_raw[df_raw["basket_raw"] != ""].copy()
    df["productos"] = df["basket_raw"].str.split()
    df = df.explode("productos")
    df = df.dropna(subset=["productos"])
    df["id_producto"] = df["productos"].astype(int).astype("int16")
    df = df.drop(columns=["basket_raw", "productos"])

    df["dia_semana"] = df["fecha"].dt.dayofweek.astype("int8")   # 0=Lun .. 6=Dom
    df["semana"] = df["fecha"].dt.isocalendar().week.astype("int8")
    df["mes"] = df["fecha"].dt.month.astype("int8")

    return df.reset_index(drop=True)


def map_categories(df_flat: pd.DataFrame,
                   cat_dict: dict,
                   pc_dict: dict) -> pd.DataFrame:
    """
    Agrega columna 'nombre_categoria' al DataFrame explosionado.
    Estrategia:
      - Si id_producto está en pc_dict → busca cat_dict[pc_dict[id_producto]]
      - Sino si id_producto <= max(cat_dict) → busca cat_dict[id_producto] directamente
      - Sino → 'SIN CATEGORIA'
    """
    max_cat = max(cat_dict.keys()) if cat_dict else 0

    def _get_cat(pid: int) -> str:
        if pid in pc_dict:
            return cat_dict.get(pc_dict[pid], "SIN CATEGORIA")
        if pid <= max_cat and pid in cat_dict:
            return cat_dict[pid]
        return "SIN CATEGORIA"

    df_flat = df_flat.copy()
    df_flat["nombre_categoria"] = df_flat["id_producto"].map(_get_cat)
    return df_flat


def build_customer_features(df_flat: pd.DataFrame) -> pd.DataFrame:
    """
    Genera una fila por cliente con sus métricas de comportamiento:
    - frecuencia: número de días distintos con al menos una compra
    - n_productos_distintos: variedad de productos comprados
    - volumen_total: total de ítems comprados
    - n_categorias_distintas: diversidad de categorías
    - id_tienda: tienda donde compró con mayor frecuencia
    """
    # Frecuencia = días únicos de compra por cliente
    freq = (
        df_flat.groupby("id_cliente")["fecha"]
        .nunique()
        .rename("frecuencia")
    )
    # Productos distintos
    n_prods = (
        df_flat.groupby("id_cliente")["id_producto"]
        .nunique()
        .rename("n_productos_distintos")
    )
    # Volumen total
    vol = (
        df_flat.groupby("id_cliente")["id_producto"]
        .count()
        .rename("volumen_total")
    )
    # Categorías distintas
    n_cats = (
        df_flat.groupby("id_cliente")["nombre_categoria"]
        .nunique()
        .rename("n_categorias_distintas")
    )
    # Tienda principal
    tienda_principal = (
        df_flat.groupby(["id_cliente", "id_tienda"])
        .size()
        .reset_index(name="cnt")
        .sort_values("cnt", ascending=False)
        .drop_duplicates("id_cliente")
        .set_index("id_cliente")["id_tienda"]
        .rename("id_tienda")
    )

    df_customers = pd.concat(
        [freq, n_prods, vol, n_cats, tienda_principal], axis=1
    ).reset_index()
    df_customers.columns = [
        "id_cliente",
        "frecuencia",
        "n_productos_distintos",
        "volumen_total",
        "n_categorias_distintas",
        "id_tienda",
    ]
    return df_customers


def build_daily_summary(df_flat: pd.DataFrame) -> pd.DataFrame:
    """
    Resumen diario por tienda:
    - n_transacciones: pares únicos (fecha, id_cliente) por tienda
    - n_items: total de ítems vendidos
    - n_clientes: clientes únicos
    """
    # n_transacciones = combinaciones únicas cliente-día por tienda
    trans = (
        df_flat.groupby(["fecha", "id_tienda"])
        .apply(lambda g: g.drop_duplicates(subset=["id_cliente"]).shape[0],
               include_groups=False)
        .rename("n_transacciones")
        .reset_index()
    )
    items = (
        df_flat.groupby(["fecha", "id_tienda"])["id_producto"]
        .count()
        .rename("n_items")
        .reset_index()
    )
    clientes = (
        df_flat.groupby(["fecha", "id_tienda"])["id_cliente"]
        .nunique()
        .rename("n_clientes")
        .reset_index()
    )

    df_daily = trans.merge(items, on=["fecha", "id_tienda"]).merge(
        clientes, on=["fecha", "id_tienda"]
    )
    df_daily["dia_semana"] = df_daily["fecha"].dt.dayofweek.astype("int8")
    df_daily["semana"] = df_daily["fecha"].dt.isocalendar().week.astype("int8")
    df_daily["mes"] = df_daily["fecha"].dt.month.astype("int8")
    return df_daily.sort_values(["fecha", "id_tienda"]).reset_index(drop=True)


def build_product_freq(df_flat: pd.DataFrame) -> pd.DataFrame:
    """
    Frecuencia de cada producto:
    - frecuencia_absoluta: total de apariciones
    - n_clientes: clientes únicos que lo compraron
    - pct_transacciones: porcentaje de transacciones que incluyen este producto
    """
    total_clientes = df_flat["id_cliente"].nunique()

    freq = (
        df_flat.groupby(["id_producto", "nombre_categoria"])
        .agg(
            frecuencia_absoluta=("id_producto", "count"),
            n_clientes=("id_cliente", "nunique"),
        )
        .reset_index()
    )
    freq["pct_clientes"] = (freq["n_clientes"] / total_clientes * 100).round(2)
    return freq.sort_values("frecuencia_absoluta", ascending=False).reset_index(drop=True)


def build_baskets_for_apriori(df_raw: pd.DataFrame,
                              sample_frac: float = 0.30) -> list:
    """
    Genera lista de frozensets para FPGrowth/Apriori.
    Usa una muestra aleatoria para manejar el volumen.
    """
    sample = df_raw.sample(frac=sample_frac, random_state=42)
    baskets = [
        frozenset(int(p) for p in row.split())
        for row in sample["basket_raw"]
        if isinstance(row, str) and row.strip()
    ]
    return baskets
