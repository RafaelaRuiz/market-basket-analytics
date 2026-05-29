"""Página 5 — Incorporación de Nuevos Datos (consume FastAPI)."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import io
import streamlit as st
import pandas as pd
from src.utils import api_client

st.set_page_config(page_title="Nuevos Datos", page_icon="📥", layout="wide")

st.title("📥 Incorporación de Nuevos Datos")
st.markdown(
    "Sube un CSV de transacciones. La API lo almacena, lanza el **ETL incremental** "
    "(solo procesa el archivo nuevo) y recarga los resultados automáticamente."
)
st.markdown("---")

# ─── Estado del ETL ───────────────────────────────────────────────────────────
with st.expander("📋 Estado del procesamiento"):
    try:
        status = api_client.get_etl_status()
        st.write(f"**Archivos procesados:** {status['total_files']}")
        st.write(f"**Última actualización:** {status['last_updated'] or 'N/A'}")
        for f in status["processed_files"]:
            st.write(f"  ✅ {f}")
    except Exception as e:
        st.error(f"No se pudo obtener estado de la API: {e}")

st.markdown("---")

# ─── Formato esperado ─────────────────────────────────────────────────────────
with st.expander("ℹ️ Formato esperado del archivo"):
    st.code(
        "2013-07-01|102|530|20 3 1\n"
        "2013-07-01|102|587|6 29 43 21 34",
        language="text",
    )
    st.caption("Sin header · pipe-delimited · `Fecha|IDTienda|IDCliente|IDProductos`")

# ─── Upload ───────────────────────────────────────────────────────────────────
uploaded = st.file_uploader("Selecciona el CSV de transacciones", type=["csv"])

if uploaded:
    content = uploaded.read()
    # Preview local
    try:
        df_prev = pd.read_csv(io.BytesIO(content), sep="|", header=None,
                              names=["fecha","id_tienda","id_cliente","basket_raw"],
                              nrows=10, dtype=str)
        c1, c2 = st.columns(2)
        c1.metric("Filas en el archivo", f"{sum(1 for _ in content.decode().splitlines()):,}")
        c2.metric("Columnas detectadas", df_prev.shape[1])
        st.subheader("Vista previa (10 filas)")
        st.dataframe(df_prev, use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"No se pudo hacer preview: {e}")

    st.markdown("---")
    st.warning("⚠️ Al incorporar datos se ejecutará el ETL incremental. Solo se procesará el archivo nuevo.")

    if st.button("🔄 Incorporar datos", type="primary"):
        with st.status("Procesando...", expanded=True) as status_widget:

            # 1. Subir CSV a la API
            st.write("📤 Enviando archivo a la API...")
            try:
                r = api_client.upload_csv(content, uploaded.name)
                st.write(f"   ✅ {r['message']}")
            except Exception as e:
                status_widget.update(label="❌ Error al subir archivo", state="error")
                st.error(str(e)); st.stop()

            # 2. Lanzar ETL incremental
            st.write("⚙️ Lanzando ETL incremental...")
            try:
                r = api_client.trigger_etl()
                st.write(f"   ✅ {r.get('message', r.get('status', 'OK'))}")
                if r.get("output"):
                    with st.expander("Log ETL"):
                        st.code(r["output"])
            except Exception as e:
                status_widget.update(label="❌ Error en ETL", state="error")
                st.error(str(e)); st.stop()

            # 3. Recargar datos en memoria de la API
            st.write("🔄 Recargando datos en la API...")
            try:
                r = api_client.reload_data()
                rows = r.get("rows", {})
                st.write(f"   ✅ Datos recargados: {rows.get('flat', '?'):,} ítems en memoria")
            except Exception as e:
                st.warning(f"No se pudo recargar automáticamente: {e}")

            status_widget.update(label="✅ Datos incorporados exitosamente", state="complete")
            st.success("🎉 Los nuevos datos ya están disponibles en todos los módulos.")
            st.rerun()
