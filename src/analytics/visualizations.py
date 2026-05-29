"""
Funciones de visualización con Plotly.
Cada función recibe un DataFrame ya filtrado y devuelve una figura Plotly.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# Paleta de colores corporativa
PALETTE = px.colors.qualitative.Bold
PRIMARY = "#1F77B4"

DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
         7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}


# ─────────────────────────────────────────────────────────────────────────────
# RESUMEN EJECUTIVO
# ─────────────────────────────────────────────────────────────────────────────

def fig_top_productos(df_products: pd.DataFrame, n: int = 10) -> go.Figure:
    """Top N productos por frecuencia absoluta (barras horizontales)."""
    top = df_products.head(n).copy()
    top["label"] = top.apply(
        lambda r: f"Prod {r['id_producto']} ({r['nombre_categoria']})", axis=1
    )
    fig = px.bar(
        top.sort_values("frecuencia_absoluta"),
        x="frecuencia_absoluta",
        y="label",
        orientation="h",
        color="frecuencia_absoluta",
        color_continuous_scale="Blues",
        labels={"frecuencia_absoluta": "Ítems vendidos", "label": "Producto"},
        title=f"Top {n} Productos por Volumen",
    )
    fig.update_coloraxes(showscale=False)
    fig.update_layout(yaxis_title=None, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def fig_top_clientes(df_top: pd.DataFrame, n: int = 10) -> go.Figure:
    """
    Top N clientes por número total de ítems comprados.
    Acepta DataFrame pre-agregado con columnas [id_cliente, total_items].
    """
    top = df_top.head(n).sort_values("total_items")
    top["label"] = "Cliente " + top["id_cliente"].astype(str)
    fig = px.bar(
        top,
        x="total_items",
        y="label",
        orientation="h",
        color="total_items",
        color_continuous_scale="Greens",
        labels={"total_items": "Total ítems", "label": "Cliente"},
        title=f"Top {n} Clientes por Volumen de Compra",
    )
    fig.update_coloraxes(showscale=False)
    fig.update_layout(yaxis_title=None, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def fig_dias_pico(df_daily: pd.DataFrame) -> go.Figure:
    """Heatmap: día de la semana × semana del año, intensidad = n_transacciones."""
    pivot = (
        df_daily.groupby(["dia_semana", "semana"])["n_transacciones"]
        .sum()
        .reset_index()
        .pivot(index="dia_semana", columns="semana", values="n_transacciones")
        .fillna(0)
    )
    pivot.index = [DIAS_SEMANA[i] for i in pivot.index]

    fig = px.imshow(
        pivot,
        color_continuous_scale="YlOrRd",
        labels={"x": "Semana del año", "y": "Día", "color": "Transacciones"},
        title="Días Pico de Compra",
        aspect="auto",
    )
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
    return fig


def fig_categorias_pie(df_cats: pd.DataFrame) -> go.Figure:
    """
    Pie chart de frecuencia por categoría.
    Acepta DataFrame pre-agregado con columnas [nombre_categoria, frecuencia].
    """
    cat_counts = df_cats.sort_values("frecuencia", ascending=False)
    # Agrupar categorías pequeñas en "Otras"
    top_cats = cat_counts.head(10)
    otros = cat_counts.iloc[10:]["frecuencia"].sum()
    if otros > 0:
        top_cats = pd.concat([
            top_cats,
            pd.DataFrame([{"nombre_categoria": "Otras", "frecuencia": otros}])
        ], ignore_index=True)

    fig = px.pie(
        top_cats,
        values="frecuencia",
        names="nombre_categoria",
        title="Categorías Más Frecuentes",
        color_discrete_sequence=PALETTE,
        hole=0.35,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=40, b=10))
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# VISUALIZACIONES ANALÍTICAS
# ─────────────────────────────────────────────────────────────────────────────

def fig_serie_tiempo(df_daily: pd.DataFrame, granularity: str = "D",
                     por_tienda: bool = False) -> go.Figure:
    """
    Serie de tiempo de transacciones.

    Args:
        granularity: 'D' diario, 'W' semanal.
        por_tienda: si True, traza una línea por tienda; si False, suma todo.
    """
    df = df_daily.copy()
    if granularity == "W":
        df["periodo"] = df["fecha"].dt.to_period("W").dt.start_time
    else:
        df["periodo"] = df["fecha"]

    label_gran = "Semana" if granularity == "W" else "Día"

    if por_tienda:
        agg = (
            df.groupby(["periodo", "id_tienda"])["n_transacciones"]
            .sum()
            .reset_index()
        )
        agg["id_tienda"] = agg["id_tienda"].astype(str)
        fig = px.line(
            agg,
            x="periodo",
            y="n_transacciones",
            color="id_tienda",
            labels={"periodo": label_gran, "n_transacciones": "Transacciones",
                    "id_tienda": "Tienda"},
            title=f"Transacciones por {label_gran} y Tienda",
            markers=True,
        )
    else:
        agg = (
            df.groupby("periodo")["n_transacciones"]
            .sum()
            .reset_index()
        )
        fig = px.area(
            agg,
            x="periodo",
            y="n_transacciones",
            labels={"periodo": label_gran, "n_transacciones": "Transacciones"},
            title=f"Transacciones por {label_gran} (Todas las tiendas)",
            color_discrete_sequence=[PRIMARY],
        )

    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
    return fig


def fig_boxplot(df_customers: pd.DataFrame, variable: str) -> go.Figure:
    """
    Boxplot de la distribución de una variable de comportamiento de clientes.
    Agrupa por tienda principal.
    """
    label_map = {
        "volumen_total": "Total de ítems comprados",
        "frecuencia": "Número de visitas",
        "n_productos_distintos": "Productos distintos",
        "n_categorias_distintas": "Categorías distintas",
    }
    label = label_map.get(variable, variable)

    df = df_customers.copy()
    df["Tienda"] = "Tienda " + df["id_tienda"].astype(str)

    # Truncar outliers extremos para mejor visualización (percentil 99)
    p99 = df[variable].quantile(0.99)
    df_vis = df[df[variable] <= p99]

    fig = px.box(
        df_vis,
        x="Tienda",
        y=variable,
        color="Tienda",
        labels={variable: label},
        title=f"Distribución de {label} por Tienda",
        color_discrete_sequence=PALETTE,
        points="outliers",
    )
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def fig_heatmap_correlacion(df_customers: pd.DataFrame) -> go.Figure:
    """Heatmap de correlación entre las features numéricas de clientes."""
    features = ["frecuencia", "n_productos_distintos",
                "volumen_total", "n_categorias_distintas"]
    labels = ["Frecuencia", "Prod. Distintos", "Volumen Total", "Cat. Distintas"]

    corr = df_customers[features].corr()
    corr.index = labels
    corr.columns = labels

    fig = px.imshow(
        corr,
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        text_auto=".2f",
        title="Correlación entre Variables de Clientes",
        labels={"color": "Correlación"},
    )
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
    return fig


def fig_evolucion_categorias(df_evol: pd.DataFrame) -> go.Figure:
    """
    Serie de tiempo del top N categorías a lo largo del tiempo.
    Acepta DataFrame pre-agregado con columnas [semana, nombre_categoria, frecuencia].
    """
    fig = px.line(
        df_evol,
        x="semana",
        y="frecuencia",
        color="nombre_categoria",
        title="Evolución Semanal — Top Categorías",
        labels={"semana": "Semana", "frecuencia": "Ítems vendidos",
                "nombre_categoria": "Categoría"},
        markers=False,
    )
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
    return fig
