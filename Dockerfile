# Backend FastAPI para Render u otros PaaS.
# Lee data/raw y data/processed, y arranca con un bootstrap que genera
# los parquet si faltan antes de levantar Uvicorn.

FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY api/ ./api/
COPY data/ ./data/
EXPOSE 8000
ENV PORT=8000
CMD ["python", "-m", "api.startup"]
