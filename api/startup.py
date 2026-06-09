"""Arranque del backend para Docker/Render.

Si no existen los parquet procesados, ejecuta el precompute local usando los
CSV de data/raw y luego levanta Uvicorn.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
REQUIRED_FILES = [
    "transactions_flat.parquet",
    "customer_features.parquet",
    "daily_summary.parquet",
    "product_freq.parquet",
    "association_rules.parquet",
]


def _needs_precompute() -> bool:
    if os.environ.get("REBUILD_PROCESSED", "").strip() == "1":
        return True
    return any(not (PROCESSED_DIR / name).exists() for name in REQUIRED_FILES)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    if _needs_precompute():
        subprocess.run(
            [sys.executable, "-m", "src.etl.precompute", "--force"],
            cwd=ROOT,
            check=True,
        )

    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "api.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            os.environ.get("PORT", "8000"),
            "--workers",
            os.environ.get("UVICORN_WORKERS", "2"),
        ],
    )


if __name__ == "__main__":
    main()