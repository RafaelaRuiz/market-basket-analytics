"""Página 3 — Segmentación de Clientes (K-Means)."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.utils import api_client
from src.analytics.segmentation import AVAILABLE_FEATURES, FEATURE_LABELS

st.set_page_config(
    page_title="Segmentación de Clientes",
    page_icon="🔬",
    layout="wide",
)

# ─── Controles en sidebar ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Parámetros K-Means")
    k = st.slider("Número de clusters (K)", min_value=2, max_value=8, value=3, step=1)

    features = st.multiselect(
        "Features a usar",
        options=AVAILABLE_FEATURES,
        default=AVAILABLE_FEATURES,
        format_func=lambda f: FEATURE_LABELS.get(f, f),
    )

    tienda_sel = st.session_state.get("tienda_sel", "Todas")
    tienda_id  = st.session_state.get("tienda_id")

    st.markdown("---")
    st.caption(f"Tienda: **{tienda_sel}**")

st.title("🔬 Segmentación de Clientes")
st.caption("Agrupamiento K-Means sobre features de comportamiento de compra.")
st.markdown("---")

if len(features) < 2:
    st.warning("Selecciona al menos 2 features para la segmentación.")
    st.stop()

# ─── Llamada a la API (con caché Streamlit) ────────────────────────────────────
@st.cache_data(ttl=300, show_spinner="Calculando segmentación...")
def _fetch_kmeans(k: int, features_tuple: tuple, tienda: int | None) -> dict:
    return api_client.get_kmeans(k=k, features=list(features_tuple), tienda=tienda)


try:
    result = _fetch_kmeans(k, tuple(features), tienda_id)
except Exception as e:
    st.error(f"❌ Error al obtener segmentación: {e}")
    st.info("Asegúrate de que la FastAPI esté corriendo.")
    st.stop()

# ─── Construir DataFrames desde resultado ─────────────────────────────────────
df_scatter = pd.DataFrame({
    "id_cliente": result["customer_ids"],
    "pca_x":      result["pca_x"],
    "pca_y":      result["pca_y"],
    "cluster":    [str(l) for l in result["labels"]],
})

df_stats = pd.DataFrame(result["stats"])
df_centers = pd.DataFrame(result["centers"])
df_elbow = pd.DataFrame(result["inertia_curve"])
interpretations: list[str] = result.get("interpretation", [])
pca_var = result.get("pca_var", [0, 0])

# ─── Fila 1: curva de codo + scatter PCA ──────────────────────────────────────
col_elbow, col_scatter = st.columns(2)

with col_elbow:
    st.subheader("📉 Curva de codo (Elbow)")
    fig_elbow = go.Figure()
    fig_elbow.add_trace(go.Scatter(
        x=df_elbow["k"],
        y=df_elbow["inercia"],
        mode="lines+markers",
        marker=dict(size=8, color="#636EFA"),
        line=dict(width=2),
    ))
    fig_elbow.add_vline(
        x=k,
        line_dash="dash",
        line_color="red",
        annotation_text=f"K={k}",
        annotation_position="top right",
    )
    fig_elbow.update_layout(
        xaxis_title="K (número de clusters)",
        yaxis_title="Inercia",
        plot_bgcolor="white",
        margin=dict(t=30, b=40),
    )
    st.plotly_chart(fig_elbow, use_container_width=True)

with col_scatter:
    var1 = round(pca_var[0] * 100, 1) if len(pca_var) > 0 else 0
    var2 = round(pca_var[1] * 100, 1) if len(pca_var) > 1 else 0
    st.subheader("🎨 Scatter PCA — Clusters")
    fig_scatter = px.scatter(
        df_scatter,
        x="pca_x",
        y="pca_y",
        color="cluster",
        hover_data={"id_cliente": True, "pca_x": False, "pca_y": False},
        labels={"pca_x": f"PC1 ({var1}%)", "pca_y": f"PC2 ({var2}%)", "cluster": "Cluster"},
        color_discrete_sequence=px.colors.qualitative.Plotly,
        opacity=0.6,
    )
    fig_scatter.update_traces(marker=dict(size=4))
    fig_scatter.update_layout(
        plot_bgcolor="white",
        margin=dict(t=30, b=40),
        legend_title_text="Cluster",
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("---")

# ─── Fila 2: KPI por cluster + tabla de estadísticas ──────────────────────────
st.subheader("📊 Resumen por segmento")

cluster_colors = px.colors.qualitative.Plotly

kpi_cols = st.columns(k)
for i, row in df_stats.iterrows():
    c_idx = int(row["cluster"])
    with kpi_cols[c_idx]:
        st.markdown(
            f"<div style='border-left:4px solid {cluster_colors[c_idx % len(cluster_colors)]};"
            f"padding:8px 12px;border-radius:4px'>"
            f"<b>Cluster {c_idx}</b><br>"
            f"<span style='font-size:1.4em'>{int(row['n_clientes']):,}</span> clientes"
            f"</div>",
            unsafe_allow_html=True,
        )

st.markdown("")

# Tabla con medias por feature por cluster
rename_map = {f"{f}_mean": FEATURE_LABELS.get(f, f) for f in features}
rename_map["cluster"] = "Cluster"
rename_map["n_clientes"] = "N° Clientes"

cols_to_show = ["cluster", "n_clientes"] + [f"{f}_mean" for f in features]
df_display = df_stats[cols_to_show].rename(columns=rename_map)
df_display["Cluster"] = df_display["Cluster"].astype(int)

st.dataframe(
    df_display.style.format({v: "{:,.2f}" for v in df_display.columns if v not in ("Cluster", "N° Clientes")}),
    use_container_width=True,
    hide_index=True,
)

st.markdown("---")

# ─── Interpretación textual ────────────────────────────────────────────────────
st.subheader("💡 Interpretación de segmentos")

interp_cols = st.columns(min(k, 4))
for i, text in enumerate(interpretations):
    with interp_cols[i % len(interp_cols)]:
        st.info(f"**Cluster {i}**\n\n{text}")

# ─── Expander: tabla de centroides ────────────────────────────────────────────
with st.expander("🎯 Centroides en espacio original"):
    df_cent_display = df_centers.rename(
        columns={f: FEATURE_LABELS.get(f, f) for f in features}
    )
    df_cent_display["cluster"] = df_cent_display["cluster"].astype(int)
    df_cent_display = df_cent_display.rename(columns={"cluster": "Cluster"})
    st.dataframe(
        df_cent_display.style.format(
            {v: "{:,.2f}" for v in df_cent_display.columns if v != "Cluster"}
        ),
        use_container_width=True,
        hide_index=True,
    )
