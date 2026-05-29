# Market Basket Analytics

Dashboard de analítica de transacciones de supermercado.
Construido con **Streamlit + Pandas + Plotly + Scikit-learn**, desplegado en **Google Cloud Run**.

## Módulos

| Página | Descripción |
|--------|-------------|
| 📊 Resumen Ejecutivo | KPIs, Top 10 productos y clientes, días pico, categorías |
| 📈 Visualizaciones Analíticas | Series de tiempo, boxplots, heatmap de correlación |
| 🔬 Segmentación de Clientes | Clustering K-Means con visualización PCA |
| 🤝 Recomendador | Reglas de asociación (FPGrowth) + filtrado colaborativo |
| 📥 Nuevos Datos | Incorporar nuevos CSV y regenerar análisis automáticamente |

## Desarrollo local

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Generar datasets procesados (una vez)
python -m src.etl.precompute

# 3. Ejecutar la app
streamlit run app/main.py
```

## Con Google Cloud Storage

```bash
# Precomputo y upload a GCS
python -m src.etl.precompute --bucket=<NOMBRE_BUCKET>

# Ejecutar apuntando al bucket
GCS_BUCKET=<NOMBRE_BUCKET> streamlit run app/main.py
```

## Despliegue en Cloud Run

```bash
# Build y push de la imagen
gcloud builds submit --tag gcr.io/<PROJECT_ID>/market-basket-app

# Deploy
gcloud run deploy market-basket-app \
  --image gcr.io/<PROJECT_ID>/market-basket-app \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars GCS_BUCKET=<NOMBRE_BUCKET> \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300
```

**IAM requerido:** La service account de Cloud Run necesita `roles/storage.objectViewer`
(y `roles/storage.objectAdmin` si se usa la página de Nuevos Datos).

## Estructura del proyecto

```
market-basket-analytics/
├── data/raw/              # Datos originales (no en Docker)
├── data/processed/        # Parquets generados por precompute.py
├── src/
│   ├── etl/               # loader.py, transformer.py, precompute.py
│   ├── analytics/         # visualizations.py, segmentation.py, recommender.py
│   └── utils/             # gcs.py (helper de datos)
├── app/
│   ├── main.py            # Punto de entrada
│   └── pages/             # Páginas del dashboard
├── Dockerfile
└── requirements.txt
```