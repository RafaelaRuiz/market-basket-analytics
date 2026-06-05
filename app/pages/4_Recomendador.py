"""Página 4 — Recomendador (Por Producto y Por Cliente)."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd

from src.utils import api_client

st.set_page_config(
    page_title="Recomendador",
    page_icon="🎯",
    layout="wide",
)

st.title("🎯 Recomendador")
st.caption("Reglas de asociación por producto · Filtrado colaborativo por cliente")
st.markdown("---")

tab_producto, tab_cliente = st.tabs(["🛒 Por Producto", "👤 Por Cliente"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Por Producto (Reglas de Asociación)
# ═══════════════════════════════════════════════════════════════════════════════
with tab_producto:
    st.subheader("🛒 Recomendaciones basadas en reglas de asociación")
    st.markdown(
        "Selecciona un producto y el sistema mostrará qué otros productos "
        "tienden a comprarse juntos, ordenados por **lift**."
    )

    # Cargar lista de productos con reglas disponibles
    @st.cache_data(ttl=600, show_spinner="Cargando productos con reglas...")
    def _fetch_products_with_rules() -> list[int]:
        try:
            return api_client.get_products_with_rules()
        except Exception:
            return []

    products_list = _fetch_products_with_rules()

    if not products_list:
        st.warning(
            "⚠️ No hay reglas de asociación disponibles. "
            "Ejecuta el pipeline ETL con `python -m src.etl.precompute --force` "
            "para generarlas."
        )
    else:
        col_sel, col_top = st.columns([3, 1])
        with col_sel:
            selected_product = st.selectbox(
                "Producto",
                options=products_list,
                format_func=lambda p: f"Producto {p}",
            )
        with col_top:
            top_n_prod = st.number_input(
                "Top N reglas", min_value=1, max_value=50, value=10, step=1
            )

        if st.button("🔍 Ver reglas", key="btn_rules"):
            with st.spinner("Consultando reglas..."):
                try:
                    df_rules = api_client.get_rules_for_product(
                        selected_product, top_n=top_n_prod
                    )
                except Exception as e:
                    st.error(f"Error: {e}")
                    df_rules = pd.DataFrame()

            if df_rules.empty:
                st.info(f"No se encontraron reglas para el Producto {selected_product}.")
            else:
                st.success(f"{len(df_rules)} reglas encontradas para el Producto {selected_product}.")

                # Formatear para presentación
                df_show = df_rules.copy()
                df_show["antecedents"] = df_show["antecedents"].apply(
                    lambda lst: ", ".join(f"P{p}" for p in lst)
                )
                df_show["consequents"] = df_show["consequents"].apply(
                    lambda lst: ", ".join(f"P{p}" for p in lst)
                )
                df_show = df_show.rename(columns={
                    "antecedents": "Si compra",
                    "consequents": "También compra",
                    "support":     "Soporte",
                    "confidence":  "Confianza",
                    "lift":        "Lift",
                })
                df_show[["Soporte", "Confianza"]] = df_show[["Soporte", "Confianza"]].map(
                    lambda v: f"{v:.3f}"
                )
                df_show["Lift"] = df_show["Lift"].apply(lambda v: f"{v:.2f}")

                st.dataframe(df_show, use_container_width=True, hide_index=True)

                # KPIs de la mejor regla
                best = df_rules.iloc[0]
                m1, m2, m3 = st.columns(3)
                m1.metric("Mejor Lift", f"{best['lift']:.2f}")
                m2.metric("Confianza", f"{best['confidence']:.1%}")
                m3.metric("Soporte", f"{best['support']:.3f}")

    st.markdown("---")
    with st.expander("ℹ️ ¿Cómo se calculan las reglas?"):
        st.markdown(
            """
            Las reglas de asociación se calculan con **FPGrowth** (mlxtend) sobre
            una muestra aleatoria del 30% de las transacciones:

            - **Soporte**: fracción de transacciones que contienen el itemset.
            - **Confianza**: P(consecuente | antecedente).
            - **Lift**: confianza / soporte esperado del consecuente. Lift > 1 indica
              que los productos se compran juntos más de lo esperado.

            Umbrales usados: soporte mínimo = 1%, confianza mínima = 30%.
            """
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Por Cliente (Similitud Coseno)
# ═══════════════════════════════════════════════════════════════════════════════
with tab_cliente:
    st.subheader("👤 Recomendaciones personalizadas por cliente")
    st.markdown(
        "Selecciona un cliente y el sistema identificará clientes "
        "con hábitos similares para sugerir **categorías** aún no exploradas."
    )

    # Cargar lista de clientes disponibles
    @st.cache_data(ttl=600, show_spinner="Cargando clientes...")
    def _fetch_customers() -> list[int]:
        try:
            return api_client.get_available_customers()
        except Exception:
            return []

    customers_list = _fetch_customers()

    if not customers_list:
        st.error("❌ No hay clientes disponibles en los datos.")
    else:
        col_id, col_n = st.columns([3, 1])
        with col_id:
            customer_id = st.selectbox(
                "Cliente",
                options=customers_list,
                format_func=lambda c: f"Cliente {c}",
            )
        with col_n:
            top_n_cli = st.number_input(
                "Top N categorías", min_value=1, max_value=20, value=5, step=1
            )

        if st.button("🔍 Recomendar categorías", key="btn_customer"):
            if customer_id is not None:
                with st.spinner(f"Calculando recomendaciones para cliente {customer_id}..."):
                    try:
                        df_recs = api_client.get_recommendations_for_customer(
                            customer_id, top_n=top_n_cli
                        )
                        error_msg = None
                    except Exception as e:
                        df_recs = pd.DataFrame()
                        error_msg = str(e)

                if error_msg:
                    if "404" in error_msg:
                        st.error(f"❌ Cliente {customer_id} no encontrado en los datos.")
                    else:
                        st.error(f"Error: {error_msg}")
                elif df_recs.empty:
                    st.info(
                        f"No se encontraron recomendaciones para el cliente {customer_id}. "
                        "Es posible que ya haya comprado en todas las categorías disponibles."
                    )
                else:
                    st.success(
                        f"✅ {len(df_recs)} categorías recomendadas para el cliente {customer_id}."
                    )

                    # Tabla de recomendaciones
                    df_show = df_recs.copy()
                    df_show.index = range(1, len(df_show) + 1)
                    df_show = df_show.rename(columns={
                        "categoria": "Categoría Recomendada",
                        "score":     "Puntaje de Similitud",
                    })
                    df_show["Puntaje de Similitud"] = df_show["Puntaje de Similitud"].apply(
                        lambda v: f"{v:.4f}"
                    )

                    st.dataframe(df_show, use_container_width=True)

                    # Gráfico de barras horizontales
                    import plotly.express as px
                    fig_recs = px.bar(
                        df_recs,
                        x="score",
                        y="categoria",
                        orientation="h",
                        labels={"score": "Puntaje", "categoria": "Categoría"},
                        color="score",
                        color_continuous_scale="Blues",
                    )
                    fig_recs.update_layout(
                        yaxis=dict(categoryorder="total ascending"),
                        coloraxis_showscale=False,
                        margin=dict(t=20, b=40),
                        plot_bgcolor="white",
                    )
                    st.plotly_chart(fig_recs, use_container_width=True)

    st.markdown("---")
    with st.expander("ℹ️ ¿Cómo funciona el recomendador por cliente?"):
        st.markdown(
            """
            El recomendador usa **filtrado colaborativo basado en ítems**:

            1. Se construye una matriz **cliente × categoría** con la frecuencia de compra.
            2. Se aplica **TruncatedSVD** (50 componentes) para reducir dimensionalidad.
            3. Se calcula la **similitud coseno** entre el cliente seleccionado y todos los demás.
            4. Se seleccionan los 10 vecinos más similares.
            5. Se recomiendan las categorías que estos vecinos compraron pero el cliente objetivo aún no.
            6. Las categorías se ordenan por **puntaje acumulado de similitud**.
            """
        )
