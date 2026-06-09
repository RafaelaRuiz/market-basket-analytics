"""Arranque del backend para Docker/Render.

El backend espera que los parquet procesados ya estén incluidos en la imagen
para evitar recalcular ETL pesado durante el arranque.
"""

from __future__ import annotations

import os
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

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