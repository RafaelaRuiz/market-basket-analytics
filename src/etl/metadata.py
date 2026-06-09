"""
Gestión de _metadata.json — registro de qué archivos CSV ya fueron procesados.

Esto permite ETL incremental: solo se procesan archivos NUEVOS,
los ya procesados se saltan, evitando recalcular todo desde cero.

Estructura del archivo:
{
  "processed_files": {
    "102_Tran.csv": {"processed_at": "2026-05-27T14:36:00Z", "rows": 314286},
    "103_Tran.csv": {"processed_at": "2026-05-27T14:36:00Z", "rows": 407130}
  },
  "last_updated": "2026-05-27T14:36:00Z"
}
"""

import glob
import json
import os
from datetime import datetime, timezone

from src.utils.mongo import load_metadata_doc, save_metadata_doc

METADATA_FILENAME = "_metadata.json"


def _local_path(processed_dir: str) -> str:
    return os.path.join(processed_dir, METADATA_FILENAME)


def load_metadata(processed_dir: str, bucket: str | None = None) -> dict:
    """
    Carga el metadata desde MongoDB, GCS o local.
    Si no existe, retorna un dict vacío con estructura válida.
    """
    mongo_metadata = load_metadata_doc()
    if mongo_metadata is not None:
        return mongo_metadata

    if bucket:
        gcs_path = f"gs://{bucket}/processed/{METADATA_FILENAME}"
        try:
            import gcsfs
            fs = gcsfs.GCSFileSystem()
            with fs.open(gcs_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[metadata] ⚠️  No se pudo leer metadata de GCS: {e}")

    # Fallback local
    local = _local_path(processed_dir)
    if os.path.exists(local):
        with open(local, "r") as f:
            return json.load(f)

    return {"processed_files": {}}


def save_metadata(metadata: dict, processed_dir: str, bucket: str | None = None):
    """
    Guarda el metadata actualizado local y opcionalmente en MongoDB y GCS.
    """
    metadata["last_updated"] = datetime.now(timezone.utc).isoformat()

    # Siempre guarda local
    os.makedirs(processed_dir, exist_ok=True)
    local = _local_path(processed_dir)
    with open(local, "w") as f:
        json.dump(metadata, f, indent=2)

    try:
        save_metadata_doc(metadata)
    except Exception as e:
        print(f"[metadata] ⚠️  No se pudo guardar metadata en MongoDB: {e}")

    # Sube a GCS si aplica
    if bucket:
        try:
            from google.cloud import storage
            blob = storage.Client().bucket(bucket).blob(
                f"processed/{METADATA_FILENAME}"
            )
            blob.upload_from_filename(local)
        except Exception as e:
            print(f"[metadata] ⚠️  No se pudo subir metadata a GCS: {e}")


def get_new_files(transactions_dir: str, metadata: dict) -> list[str]:
    """
    Devuelve rutas absolutas de archivos CSV que AÚN NO han sido procesados.
    Compara por nombre de archivo (basename), no por ruta completa.
    """
    all_csv = sorted(glob.glob(os.path.join(transactions_dir, "*.csv")))
    already_done = set(metadata.get("processed_files", {}).keys())
    return [f for f in all_csv if os.path.basename(f) not in already_done]


def register_file(metadata: dict, filepath: str, rows: int) -> dict:
    """
    Marca un archivo como procesado en el metadata.
    """
    fname = os.path.basename(filepath)
    metadata.setdefault("processed_files", {})[fname] = {
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
    }
    return metadata
