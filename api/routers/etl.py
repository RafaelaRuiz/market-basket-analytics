"""
POST /api/v1/etl — endpoints de control del pipeline ETL.

/trigger  → lanza el Cloud Run Job (producción) o subprocess (dev local)
/reload   → recarga los parquets en memoria sin reiniciar el servidor
/upload   → recibe un CSV y lo guarda en GCS raw/Transactions/
/status   → estado del último procesamiento (metadata)
"""

import io
import os
import subprocess
import sys

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from api.deps import DataStore, get_store, load_store
from src.etl.metadata import load_metadata
from src.utils.mongo import save_uploaded_transaction

router = APIRouter(prefix="/etl", tags=["etl"])

_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", )
)
_GCS_BUCKET   = os.environ.get("GCS_BUCKET", "").strip()
_GCR_PROJECT  = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
_GCR_REGION   = os.environ.get("CLOUD_RUN_REGION", "us-central1")
_ETL_JOB_NAME = os.environ.get("ETL_JOB_NAME", "market-basket-etl")


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """
    Recibe un CSV de transacciones y lo guarda en:
    - GCS: gs://<bucket>/raw/Transactions/<filename>   (si GCS_BUCKET está definido)
    - Local: data/raw/Transactions/<filename>            (siempre, como respaldo)
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Solo se aceptan archivos .csv")

    content = await file.read()

    # Validación rápida de formato
    try:
        import pandas as pd
        df_check = pd.read_csv(io.BytesIO(content), sep="|", header=None, nrows=5)
        if df_check.shape[1] != 4:
            raise HTTPException(
                400,
                f"Formato inválido: se esperan 4 columnas pipe-delimited, "
                f"se encontraron {df_check.shape[1]}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"No se pudo leer el archivo: {e}")

    # Guardar local
    local_dir = os.path.join(_ROOT, "data", "raw", "Transactions")
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, file.filename)
    with open(local_path, "wb") as f:
        f.write(content)

    mongo_warning = None
    try:
        save_uploaded_transaction(file.filename, content)
    except Exception as e:
        mongo_warning = str(e)

    # Subir a GCS
    if _GCS_BUCKET:
        try:
            from google.cloud import storage
            blob = storage.Client().bucket(_GCS_BUCKET).blob(
                f"raw/Transactions/{file.filename}"
            )
            blob.upload_from_filename(local_path)
        except Exception as e:
            return JSONResponse(
                status_code=207,
                content={
                    "message": "CSV guardado localmente pero no se pudo subir a GCS.",
                    "error": str(e),
                    "filename": file.filename,
                }
            )

    response = {"message": "CSV recibido y almacenado.", "filename": file.filename}
    if mongo_warning:
        response["mongo_warning"] = mongo_warning
    return response


@router.post("/trigger")
def trigger_etl():
    """
    Lanza el pipeline ETL incremental.
    - En GCP (si GOOGLE_CLOUD_PROJECT está definido): ejecuta el Cloud Run Job.
    - En desarrollo local: corre precompute.py como subprocess.
    """
    if _GCR_PROJECT and _GCS_BUCKET:
        return _trigger_cloud_run_job()
    else:
        return _trigger_local_subprocess()


def _trigger_cloud_run_job() -> dict:
    """Ejecuta el Cloud Run Job vía gcloud CLI."""
    cmd = [
        "gcloud", "run", "jobs", "execute", _ETL_JOB_NAME,
        f"--region={_GCR_REGION}",
        "--format=json",
        "--async",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise HTTPException(500, f"Error al lanzar Cloud Run Job: {result.stderr}")
        return {
            "status": "triggered",
            "mode": "cloud_run_job",
            "job": _ETL_JOB_NAME,
            "message": "ETL Job lanzado en segundo plano. Llama /etl/reload cuando termine."
        }
    except FileNotFoundError:
        raise HTTPException(500, "gcloud CLI no encontrado en el servidor.")


def _trigger_local_subprocess() -> dict:
    """Corre precompute.py en foreground (dev local)."""
    cmd = [sys.executable, "-m", "src.etl.precompute"]
    if _GCS_BUCKET:
        cmd.append(f"--bucket={_GCS_BUCKET}")
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=_ROOT, timeout=300
    )
    if result.returncode != 0:
        raise HTTPException(500, f"ETL falló:\n{result.stderr}")
    return {
        "status": "completed",
        "mode": "local_subprocess",
        "output": result.stdout,
    }


@router.post("/reload")
def reload_data(store: DataStore = Depends(get_store)):
    """
    Recarga los parquets procesados en memoria sin reiniciar el servidor.
    Llamar DESPUÉS de que el ETL Job haya terminado.
    """
    try:
        load_store()
        return {
            "status": "reloaded",
            "rows": {
                "flat":      len(store.flat),
                "customers": len(store.customers),
                "daily":     len(store.daily),
                "products":  len(store.products),
            }
        }
    except Exception as e:
        raise HTTPException(500, f"Error al recargar datos: {e}")


@router.get("/status")
def etl_status():
    """Retorna el estado del último procesamiento (desde _metadata.json)."""
    processed_dir = os.path.join(_ROOT, "data", "processed")
    metadata = load_metadata(processed_dir, _GCS_BUCKET or None)
    return {
        "processed_files": list(metadata.get("processed_files", {}).keys()),
        "last_updated": metadata.get("last_updated"),
        "total_files": len(metadata.get("processed_files", {})),
    }
