"""Página 2 — Visualizaciones Analíticas (consume FastAPI)."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from src.utils import api_client
from src.analytics.visualizations import (
    fig_serie_tiempo, fig_boxplot,
    fig_heatmap_correlacion, fig_evolucion_categorias,
)

st.set_page_config(page_title="Visualizaciones Analíticas", page_icon="📈", layout="wide")

tienda    = st.session_state.get("tienda_sel", "Todas")
fecha_ini = st.session_state.get("fecha_ini")
fecha_fin = st.session_state.get("fecha_fin")

st.title("📈 Visualizaciones Analíticas")
st.caption(f"Tienda: **{tienda}**")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📅 Serie de Tiempo", "📦 Boxplot", "🔥 Heatmap Correlación"])

# ── Tab 1: Serie de tiempo ────────────────────────────────────────────────────
with tab1:
    st.subheader("Evolución de Transacciones en el Tiempo")
    c1, c2 = st.columns(2)
    gran     = c1.radio("Granularidad", ["Diaria", "Semanal"], horizontal=True)
    desglose = c2.toggle("Desglose por tienda", False)
    try:
        df_daily = api_client.get_daily(tienda, fecha_ini, fecha_fin)
        st.plotly_chart(
            fig_serie_tiempo(df_daily, "D" if gran == "Diaria" else "W", desglose),
            use_container_width=True,
        )
        st.markdown("---")
        st.subheader("Evolución Semanal — Top 5 Categorías")
        df_evol = api_client.get_category_evolution(tienda, fecha_ini, fecha_fin)
        if not df_evol.empty:
            st.plotly_chart(fig_evolucion_categorias(df_evol), use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")

# ── Tab 2: Boxplot ────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Distribución del Comportamiento de Clientes")
    variable_sel = st.selectbox(
        "Variable",
        options=["volumen_total", "frecuencia", "n_productos_distintos", "n_categorias_distintas"],
        format_func=lambda x: {
            "volumen_total": "Volumen Total (ítems comprados)",
            "frecuencia": "Frecuencia (días con compra)",
            "n_productos_distintos": "Productos Distintos",
            "n_categorias_distintas": "Categorías Distintas",
        }[x],
    )
    try:
        df_cust = api_client.get_customer_features(tienda)
        st.plotly_chart(fig_boxplot(df_cust, variable_sel), use_container_width=True)
        with st.expander("📋 Estadísticas descriptivas"):
            desc = df_cust[variable_sel].describe().round(2)
            desc.index = ["Conteo","Media","Desv. Est.","Mín.","Q1","Mediana","Q3","Máx."]
            st.dataframe(desc.rename("Valor").to_frame(), use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")

# ── Tab 3: Heatmap correlación ────────────────────────────────────────────────
with tab3:
    st.subheader("Correlación entre Variables de Comportamiento")
    try:
        df_cust = api_client.get_customer_features(tienda)
        st.plotly_chart(fig_heatmap_correlacion(df_cust), use_container_width=True)
        st.markdown("**Interpretación:**")
        st.markdown(
            "- **Volumen ↔ Frecuencia**: clientes frecuentes acumulan más ítems.\n"
            "- **Productos Distintos ↔ Categorías Distintas**: correlación esperada.\n"
            "- Variables poco correlacionadas son las mejores para K-Means."
        )
    except Exception as e:
        st.error(f"Error: {e}")
