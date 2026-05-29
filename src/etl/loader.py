"""
Carga de datos crudos desde el sistema de archivos local.
"""

import os
import glob
import pandas as pd


def load_transactions(data_dir: str) -> pd.DataFrame:
    """
    Lee todos los CSV de transacciones en data_dir/Transactions/
    Formato: Fecha|IDTienda|IDCliente|IDProductos (sin header)
    IDProductos: lista de enteros separados por espacio.
    """
    pattern = os.path.join(data_dir, "Transactions", "*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No se encontraron CSVs en {pattern}")

    frames = []
    for f in files:
        df = pd.read_csv(
            f,
            sep="|",
            header=None,
            names=["fecha", "id_tienda", "id_cliente", "basket_raw"],
            dtype={"id_tienda": "int16", "id_cliente": "int32", "basket_raw": str},
        )
        frames.append(df)

    df_all = pd.concat(frames, ignore_index=True)
    df_all["fecha"] = pd.to_datetime(df_all["fecha"])
    df_all["basket_raw"] = df_all["basket_raw"].fillna("").str.strip()
    return df_all


def load_categories(data_dir: str) -> dict:
    """
    Lee Categories.csv → {category_id (int): category_name (str)}
    Formato: v.Code_pr|v.code  (sin header en algunos, con header en otros)
    """
    path = os.path.join(data_dir, "Products", "Categories.csv")
    df = pd.read_csv(path, sep="|", header=None, names=["cat_id", "cat_name"],
                     dtype={"cat_id": int, "cat_name": str})
    # Si la primera fila es el header textual, omitirla
    if df.iloc[0]["cat_name"] in ("v.code", "cat_name"):
        df = df.iloc[1:].reset_index(drop=True)
    return dict(zip(df["cat_id"].astype(int), df["cat_name"].str.strip()))


def load_product_category(data_dir: str) -> dict:
    """
    Lee ProductCategory.csv → {product_id (int): category_id (int)}
    Formato: v.Code_pr|v.code  (con header)
    """
    path = os.path.join(data_dir, "Products", "ProductCategory.csv")
    df = pd.read_csv(path, sep="|", dtype=int)
    # Normaliza nombres de columna (puede variar)
    df.columns = ["prod_id", "cat_id"]
    return dict(zip(df["prod_id"], df["cat_id"]))
