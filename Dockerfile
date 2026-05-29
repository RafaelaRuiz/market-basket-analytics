# Cloud Run Service — Streamlit Dashboard (Dockerfile.app)
# Consume la FastAPI vía API_URL. No lee GCS directamente.
# Variables requeridas: API_URL

FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/        ./src/
COPY app/        ./app/
COPY .streamlit/ ./.streamlit/
EXPOSE 8080
ENV PORT=8080
CMD ["streamlit", "run", "app/main.py", \
     "--server.port=8080", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
