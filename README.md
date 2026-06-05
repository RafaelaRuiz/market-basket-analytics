# Market Basket Analytics

Construido con Streamlit, Pandas, Plotly y Scikit-learn. Desplegado en Google Cloud Run.

## Descripción General

Market Basket Analytics analiza más de 1.1 millones de transacciones de supermercado provenientes de 4 puntos de venta durante 6 meses (enero-junio 2013). La solución integra:

- Analítica descriptiva: KPIs, visualizaciones exploratorias
- Segmentación de clientes: K-Means clustering en 4 perfiles
- Recomendación de productos: Reglas de asociación y similitud coseno
- Incorporación de nuevos datos: Pipeline ETL automatizado
- Despliegue en la nube: Google Cloud Run + Cloud Storage

## Características Clave

- 1,108,951 transacciones procesadas (10.6 millones de ítems)
- 131,186 clientes únicos segmentados en 4 perfiles
- 3.8 millones de reglas de asociación para recomendaciones
- 5 páginas interactivas con filtros globales
- Despliegue automático con Docker y Cloud Run

## Módulos

| Página | Descripción |
|--------|-------------|
| Resumen Ejecutivo | KPIs, Top 10 productos y clientes, días pico, distribución de categorías |
| Visualizaciones Analíticas | Series de tiempo, boxplots, heatmap de correlación |
| Segmentación de Clientes | Clustering K-Means con visualización PCA y estadísticas por segmento |
| Recomendador | Reglas de asociación por producto, similitud coseno por cliente |
| Nuevos Datos | Upload de CSV, validación y regeneración automática de análisis |

## Instalación Local

### 1. Requisitos

- Python 3.12 o superior
- pip o conda

### 2. Clonar y configurar

```bash
git clone https://github.com/SilemNabib/market-basket-analytics
cd market-basket-analytics
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Generar datasets procesados (una sola vez)

```bash
python -m src.etl.precompute
```

Esto crea los archivos Parquet en `data/processed/`.

### 4. Ejecutar el proyecto

**Terminal 1 — Streamlit (Frontend):**
```bash
streamlit run app/main.py
```

**Terminal 2 — FastAPI (Backend/API):**
```bash
uvicorn api.main:app --reload --port 8000
```
La aplicación Streamlit puede usar el API para consultas avanzadas, o ejecutarse de forma independiente.

### Endpoints del API (FastAPI)

Principales rutas disponibles en http://localhost:8000:

- `GET /summary` - Resumen ejecutivo (KPIs generales)
- `GET /summary/by_store` - Resumen por tienda
- `GET /categories` - Top categorías
- `GET /products` - Top productos
- `GET /daily-summary` - Resumen diario
- `GET /customers` - Estadísticas de clientes
- `GET /segmentation` - Segmentación K-Means
- `GET /recommender/by-product/{product_id}` - Reglas para producto
- `GET /recommender/by-customer/{customer_id}` - Recomendaciones por cliente

Documentación interactiva: http://localhost:8000/docs (Swagger UI)

## Estructura del Proyecto

```
market-basket-analytics/
├── data/
│   ├── raw/                           # Datos originales (CSV)
│   │   ├── Transactions/
│   │   └── Products/
│   └── processed/                     # Parquets procesados
├── src/
│   ├── etl/
│   │   ├── loader.py                  # Carga de datos
│   │   ├── transformer.py             # Transformación y agregación
│   │   ├── precompute.py              # Pipeline de precomputo
│   │   └── metadata.py                # Metadatos
│   ├── analytics/
│   │   ├── visualizations.py          # Gráficos Plotly
│   │   ├── segmentation.py            # K-Means clustering
│   │   └── recommender.py             # FPGrowth y similitud
│   └── utils/
│       ├── gcs.py                     # Helpers para GCS
│       └── api_client.py
├── app/
│   ├── main.py                        # Punto de entrada
│   └── pages/
│       ├── 1_Resumen_Ejecutivo.py
│       ├── 2_Visualizaciones_Analiticas.py
│       ├── 3_Segmentacion_Clientes.py
│       ├── 4_Recomendador.py
│       └── 5_Nuevos_Datos.py
├── api/
│   ├── main.py                        # FastAPI backend
│   └── routers/
├── docs/
│   ├── statement.md                   # Especificaciones
│   ├── plan.md                        # Plan de trabajo
│   └── informe_tecnico.md             # Informe detallado
├── Dockerfile
├── .dockerignore
└── requirements.txt
```

## Documentación

Para más detalles técnicos y especificaciones:

- [Informe Técnico](https://github.com/SilemNabib/market-basket-analytics/blob/main/docs/informe_tecnico.md) - Análisis detallado, metodología, resultados ML y conclusiones
- [Especificaciones del Proyecto](https://github.com/SilemNabib/market-basket-analytics/blob/main/docs/statement.md) - Requerimientos y criterios de evaluación