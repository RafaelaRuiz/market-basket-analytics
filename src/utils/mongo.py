"""Helpers opcionales para persistencia en MongoDB.

Se usan solo si MONGODB_URI está definido.
"""

from __future__ import annotations

import os


_CLIENT = None


def _uri() -> str:
    return os.environ.get("MONGODB_URI", "").strip()


def _db_name() -> str:
    return os.environ.get("MONGODB_DB", "market_basket").strip() or "market_basket"


def is_enabled() -> bool:
    return bool(_uri())


def get_client():
    global _CLIENT
    if not is_enabled():
        return None
    if _CLIENT is None:
        from pymongo import MongoClient

        _CLIENT = MongoClient(_uri(), serverSelectionTimeoutMS=5000)
    return _CLIENT


def get_db():
    client = get_client()
    if client is None:
        return None
    return client[_db_name()]


def load_metadata_doc() -> dict | None:
    db = get_db()
    if db is None:
        return None
    doc = db.etl_metadata.find_one({"_id": "current"})
    if not doc:
        return None
    metadata = doc.get("metadata") or {}
    return metadata if isinstance(metadata, dict) else None


def save_metadata_doc(metadata: dict) -> None:
    db = get_db()
    if db is None:
        return
    db.etl_metadata.replace_one(
        {"_id": "current"},
        {"_id": "current", "metadata": metadata},
        upsert=True,
    )


def save_uploaded_transaction(filename: str, content: bytes) -> None:
    db = get_db()
    if db is None:
        return

    from gridfs import GridFS

    fs = GridFS(db, collection="transaction_uploads")
    existing = fs.find_one({"filename": filename})
    if existing is not None:
        existing.delete()
    fs.put(content, filename=filename, metadata={"kind": "transaction_csv"})


def sync_uploaded_transactions(target_dir: str) -> int:
    db = get_db()
    if db is None:
        return 0

    from gridfs import GridFS

    fs = GridFS(db, collection="transaction_uploads")
    os.makedirs(target_dir, exist_ok=True)
    count = 0
    for file_obj in fs.find({"metadata.kind": "transaction_csv"}):
        output_path = os.path.join(target_dir, file_obj.filename)
        if not os.path.exists(output_path):
            with open(output_path, "wb") as handle:
                handle.write(file_obj.read())
        count += 1
    return count