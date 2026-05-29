"""
Helpers de filtrado reutilizables entre routers.
Aplican los parámetros tienda / fecha_ini / fecha_fin a cualquier DataFrame
que tenga columnas 'id_tienda' y 'fecha'.
"""

from datetime import date
import pandas as pd


def apply_filters(df: pd.DataFrame,
                  tienda: int | None,
                  fecha_ini: date | None,
                  fecha_fin: date | None) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    if tienda is not None:
        mask &= df["id_tienda"] == tienda
    if fecha_ini is not None:
        mask &= df["fecha"] >= pd.Timestamp(fecha_ini)
    if fecha_fin is not None:
        mask &= df["fecha"] <= pd.Timestamp(fecha_fin)
    return df[mask]
