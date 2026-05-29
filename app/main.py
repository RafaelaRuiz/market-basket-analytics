"""
Punto de entrada del dashboard Streamlit.
Gestiona los filtros globales y los almacena en session_state
para que todas las páginas los consuman via api_client.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from src.utils import api_client

st.set_page_config(
    page_title="Market Basket Analytics",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Sidebar: filtros globales ────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/shopping-cart.png", width=60)
    st.title("Market Basket\nAnalytics")
    st.markdown("---")
    st.subheader("🔎 Filtros globales")

    tienda_sel = st.selectbox(
        "Tienda",
        options=["Todas", "102", "103", "107", "110"],
        index=0,
        key="filtro_tienda",
    )

    from datetime import date
    fecha_rango = st.date_input(
        "Rango de fechas",
        value=(date(2013, 1, 1), date(2013, 6, 30)),
        min_value=date(2013, 1, 1),
        max_value=date(2013, 6, 30),
        key="filtro_fechas",
    )
    st.markdown("---")

    # Estado de la API
    try:
        status = api_client.get_etl_status()
        st.caption(f"✅ API conectada")
        st.caption(f"📁 {status['total_files']} archivos procesados")
    except Exception:
        st.warning("⚠️ API no disponible")

# ─── Guardar filtros en session_state ─────────────────────────────────────────
tienda = int(tienda_sel) if tienda_sel != "Todas" else None
if isinstance(fecha_rango, (list, tuple)) and len(fecha_rango) == 2:
    fecha_ini, fecha_fin = fecha_rango
else:
    fecha_ini, fecha_fin = date(2013, 1, 1), date(2013, 6, 30)

st.session_state["tienda_sel"]  = tienda_sel
st.session_state["tienda_id"]   = tienda
st.session_state["fecha_ini"]   = fecha_ini
st.session_state["fecha_fin"]   = fecha_fin

# ─── Página de inicio ─────────────────────────────────────────────────────────
st.title("🛒 Market Basket Analytics")
st.markdown("Usa el menú lateral para navegar entre los módulos.")

c1, c2, c3 = st.columns(3)
c1.info("**📊 Resumen Ejecutivo**\nKPIs y top 10 de productos, clientes y categorías.")
c2.info("**📈 Visualizaciones Analíticas**\nSeries de tiempo, boxplots y correlaciones.")
c3.info("**🔬 Análisis Avanzado**\nSegmentación K-Means y recomendador de productos.")

# KPI rápido en la home
try:
    s = api_client.get_summary(tienda_sel, fecha_ini, fecha_fin)
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🛍️ Ítems",         f"{s['total_items']:,}")
    m2.metric("🧾 Transacciones", f"{s['total_transacciones']:,}")
    m3.metric("👥 Clientes",      f"{s['clientes_unicos']:,}")
    m4.metric("🏷️ Categorías",    f"{s['categorias_activas']}")
except Exception as e:
    st.error(f"No se pudo conectar con la API: {e}")
