"""
Pipeline ETL con procesamiento INCREMENTAL.

- Primera ejecución: procesa todos los CSV existentes (carga completa).
- Ejecuciones siguientes: solo procesa archivos NUEVOS no registrados en
  _metadata.json, luego actualiza los parquets existentes (append/upsert).

Uso:
    python -m src.etl.precompute                               # local, incremental
    python -m src.etl.precompute --bucket=market-basket-data   # local + GCS
    python -m src.etl.precompute --force                       # recalcular todo
"""

import argparse
import glob
import os
import time

import pandas as pd

from src.etl.loader import load_categories, load_product_category
from src.etl.metadata import (
    get_new_files,
    load_metadata,
    register_file,
    save_metadata,
)
from src.etl.transformer import (
    build_customer_features,
    build_daily_summary,
    build_product_freq,
    explode_baskets,
    map_categories,
)
from src.analytics.recommender import compute_association_rules

DATA_RAW = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw")
)
DATA_PROCESSED = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "processed")
)


def _log(msg: str):
    print(f"[precompute] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de I/O
# ─────────────────────────────────────────────────────────────────────────────

def _parquet_path(processed_dir: str, name: str) -> str:
    return os.path.join(processed_dir, name)


def _load_parquet_if_exists(path: str) -> pd.DataFrame | None:
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None


def _save_parquet(df: pd.DataFrame, path: str, bucket: str | None,
                  gcs_key: str):
    df.to_parquet(path, index=False)
    size_mb = os.path.getsize(path) / 1e6
    _log(f"  ✓ {os.path.basename(path)} ({size_mb:.1f} MB)")
    if bucket:
        _upload_blob(bucket, path, f"processed/{gcs_key}")


def _upload_blob(bucket: str, local_path: str, blob_name: str):
    try:
        from google.cloud import storage
        blob = storage.Client().bucket(bucket).blob(blob_name)
        blob.upload_from_filename(local_path)
        _log(f"     ↑ gs://{bucket}/{blob_name}")
    except Exception as e:
        _log(f"     ⚠️  GCS upload error: {e}")


def _upload_raw_to_gcs(bucket: str, data_raw: str):
    """Sube CSVs raw a GCS si aún no existen allí."""
    try:
        from google.cloud import storage
        client = storage.Client()
        bkt = client.bucket(bucket)
        for subdir in ["Transactions", "Products"]:
            for csv in sorted(glob.glob(
                    os.path.join(data_raw, subdir, "*.csv"))):
                blob_name = f"raw/{subdir}/{os.path.basename(csv)}"
                if not bkt.blob(blob_name).exists():
                    _log(f"  Subiendo {blob_name}...")
                    bkt.blob(blob_name).upload_from_filename(csv)
    except Exception as e:
        _log(f"⚠️  No se pudo subir raw a GCS: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Lógica incremental
# ─────────────────────────────────────────────────────────────────────────────

def _process_new_files(new_files: list[str], cat_dict: dict,
                       pc_dict: dict) -> pd.DataFrame:
    """
    Lee y procesa SOLO los archivos CSV nuevos.
    Retorna un DataFrame flat con los nuevos ítems.
    """
    frames = []
    for f in new_files:
        df_raw = pd.read_csv(
            f, sep="|", header=None,
            names=["fecha", "id_tienda", "id_cliente", "basket_raw"],
            dtype={"id_tienda": "int16", "id_cliente": "int32", "basket_raw": str},
        )
        df_raw["fecha"] = pd.to_datetime(df_raw["fecha"])
        frames.append(df_raw)

    df_new_raw = pd.concat(frames, ignore_index=True)
    df_new_flat = explode_baskets(df_new_raw)
    df_new_flat = map_categories(df_new_flat, cat_dict, pc_dict)
    return df_new_flat


def _merge_flat(existing: pd.DataFrame | None,
                new_rows: pd.DataFrame) -> pd.DataFrame:
    """
    Append de nuevas filas al flat existente.
    Deduplica por (fecha, id_tienda, id_cliente, id_producto).
    """
    if existing is None:
        return new_rows
    merged = pd.concat([existing, new_rows], ignore_index=True)
    merged = merged.drop_duplicates(
        subset=["fecha", "id_tienda", "id_cliente", "id_producto"]
    )
    return merged.reset_index(drop=True)


def _rebuild_derived(df_flat: pd.DataFrame) -> tuple[
        pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Recalcula los tres DataFrames derivados a partir del flat actualizado.
    Son agregaciones ligeras (< 2s sobre 10M filas).
    """
    df_customers = build_customer_features(df_flat)
    df_daily = build_daily_summary(df_flat)
    df_products = build_product_freq(df_flat)
    return df_customers, df_daily, df_products


# ─────────────────────────────────────────────────────────────────────────────
# Punto de entrada principal
# ─────────────────────────────────────────────────────────────────────────────

def run(bucket: str | None = None,
        data_raw: str = DATA_RAW,
        data_processed: str = DATA_PROCESSED,
        force: bool = False) -> dict:
    """
    Ejecuta el pipeline ETL incremental.

    Args:
        bucket:         Nombre del bucket GCS (sin gs://). None = solo local.
        data_raw:       Ruta a los datos crudos.
        data_processed: Ruta de salida local.
        force:          Si True, reprocesa todo ignorando el metadata.
    """
    os.makedirs(data_processed, exist_ok=True)
    t0 = time.time()

    # ── 1. Metadata: qué ya fue procesado ────────────────────────────────────
    metadata = {} if force else load_metadata(data_processed, bucket)
    transactions_dir = os.path.join(data_raw, "Transactions")
    new_files = (
        sorted(glob.glob(os.path.join(transactions_dir, "*.csv")))
        if force
        else get_new_files(transactions_dir, metadata)
    )

    if not new_files:
        _log("✅ No hay archivos nuevos. Los parquets ya están actualizados.")
        return {}

    _log(f"Archivos nuevos a procesar: {[os.path.basename(f) for f in new_files]}")

    # ── 2. Catálogos (siempre se recargan, son pequeños) ─────────────────────
    cat_dict = load_categories(data_raw)
    pc_dict = load_product_category(data_raw)

    # ── 3. Procesar solo los archivos nuevos ──────────────────────────────────
    _log("Procesando archivos nuevos...")
    df_new_flat = _process_new_files(new_files, cat_dict, pc_dict)
    _log(f"  {len(df_new_flat):,} nuevas filas explosionadas")

    # ── 4. Merge con el flat existente ────────────────────────────────────────
    flat_path = _parquet_path(data_processed, "transactions_flat.parquet")
    existing_flat = _load_parquet_if_exists(flat_path)
    if existing_flat is not None:
        _log(f"  Flat existente: {len(existing_flat):,} filas → haciendo merge...")
    df_flat = _merge_flat(existing_flat, df_new_flat)
    _log(f"  Flat actualizado: {len(df_flat):,} filas en total")

    # ── 5. Recalcular tablas derivadas (rápido, son agregaciones) ─────────────
    _log("Recalculando tablas derivadas...")
    df_customers, df_daily, df_products = _rebuild_derived(df_flat)
    _log(f"  customers: {len(df_customers):,} | daily: {len(df_daily):,} | products: {len(df_products):,}")

    # ── 6. Guardar parquets ───────────────────────────────────────────────────
    _log("Guardando parquets...")
    outputs = {
        "transactions_flat.parquet": df_flat,
        "customer_features.parquet": df_customers,
        "daily_summary.parquet":     df_daily,
        "product_freq.parquet":      df_products,
    }
    for fname, df in outputs.items():
        _save_parquet(df, _parquet_path(data_processed, fname), bucket, fname)

    # ── 6b. Reglas de asociación (FPGrowth sobre muestra 30%) ────────────────
    rules_path = _parquet_path(data_processed, "association_rules.parquet")
    existing_rules = _load_parquet_if_exists(rules_path)
    if existing_rules is None or force:
        _log("Calculando reglas de asociación (FPGrowth, muestra 30%)...")
        try:
            df_rules = compute_association_rules(
                df_flat, sample_frac=0.30, min_support=0.01, min_confidence=0.3
            )
            _save_parquet(df_rules, rules_path, bucket, "association_rules.parquet")
            _log(f"  {len(df_rules):,} reglas generadas")
        except Exception as e:
            _log(f"  ⚠️  Error en FPGrowth: {e}")
    else:
        _log("  Reglas de asociación ya existen (usa --force para recalcular)")

    # ── 7. Actualizar metadata ────────────────────────────────────────────────
    for f in new_files:
        # rows = filas de este archivo en el flat nuevo
        rows = len(df_new_flat[
            df_new_flat["id_tienda"] == int(
                os.path.basename(f).split("_")[0]
            )
        ]) if "_" in os.path.basename(f) else len(df_new_flat)
        metadata = register_file(metadata, f, rows)

    save_metadata(metadata, data_processed, bucket)

    # ── 8. Subir raw a GCS si aplica ──────────────────────────────────────────
    if bucket:
        _upload_raw_to_gcs(bucket, data_raw)

    elapsed = time.time() - t0
    _log(f"✅ ETL incremental completado en {elapsed:.1f}s")
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ETL incremental de transacciones de supermercado"
    )
    parser.add_argument("--bucket", default=None,
                        help="Nombre del bucket GCS (sin gs://)")
    parser.add_argument("--raw", default=DATA_RAW,
                        help="Ruta a datos crudos")
    parser.add_argument("--out", default=DATA_PROCESSED,
                        help="Ruta de salida local")
    parser.add_argument("--force", action="store_true",
                        help="Reprocesar todo ignorando el metadata")
    args = parser.parse_args()
    run(bucket=args.bucket, data_raw=args.raw,
        data_processed=args.out, force=args.force)
