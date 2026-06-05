"""Página 1 — Resumen Ejecutivo (consume FastAPI)."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from src.utils import api_client
from src.analytics.visualizations import (
    fig_top_productos, fig_top_clientes,
    fig_dias_pico, fig_categorias_pie,
)

st.set_page_config(page_title="Resumen Ejecutivo", page_icon="📊", layout="wide")

# ─── Filtros desde session_state ─────────────────────────────────────────────
tienda    = st.session_state.get("tienda_sel", "Todas")
fecha_ini = st.session_state.get("fecha_ini")
fecha_fin = st.session_state.get("fecha_fin")


@st.cache_data(ttl=300, show_spinner=False)
def load_executive_summary_data(tienda, fecha_ini, fecha_fin):
    return api_client.get_executive_summary_data(tienda, fecha_ini, fecha_fin)

st.title("📊 Resumen Ejecutivo")
st.caption(f"Tienda: **{tienda}**")
st.markdown("---")

try:
    with st.spinner("Cargando resumen completo..."):
        data = load_executive_summary_data(tienda, fecha_ini, fecha_fin)

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    s = data["summary"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🛍️ Total Ítems",      f"{s['total_items']:,}",
              f"{s['delta_items_pct']:+.1f}%" if s["delta_items_pct"] is not None else None)
    c2.metric("🧾 Transacciones",    f"{s['total_transacciones']:,}",
              f"{s['delta_trans_pct']:+.1f}%" if s["delta_trans_pct"] is not None else None)
    c3.metric("👥 Clientes Únicos",  f"{s['clientes_unicos']:,}")
    c4.metric("🏷️ Categorías",       f"{s['categorias_activas']}")

    st.markdown("---")

    # ── Top 10 Productos / Top 10 Clientes ────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        df_prods = data["top_products"]
        st.plotly_chart(fig_top_productos(df_prods), use_container_width=True)

    with col2:
        df_top_cli = data["top_customers"]
        st.plotly_chart(fig_top_clientes(df_top_cli), use_container_width=True)

    st.markdown("---")

    # ── Días pico / Categorías ────────────────────────────────────────────────
    col3, col4 = st.columns(2)
    with col3:
        df_daily = data["daily"]
        st.plotly_chart(fig_dias_pico(df_daily), use_container_width=True)

    with col4:
        df_cats = data["categories"]
        st.plotly_chart(fig_categorias_pie(df_cats), use_container_width=True)

    # ── Tabla detalle ─────────────────────────────────────────────────────────
    with st.expander("📋 Tabla detalle — Top 10 Productos"):
        df_show = df_prods.rename(columns={
            "id_producto": "ID Producto",
            "nombre_categoria": "Categoría",
            "frecuencia_absoluta": "Ítems Vendidos",
            "n_clientes": "Clientes Únicos",
            "pct_clientes": "% Clientes",
        })
        st.dataframe(df_show, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"❌ Error al obtener datos de la API: {e}")
    st.info("Asegúrate de que la FastAPI esté corriendo: `uvicorn api.main:app --port 8000`")
