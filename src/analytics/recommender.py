"""
Módulo de recomendación en dos variantes:

1. Por producto  — reglas de asociación (FPGrowth/mlxtend)
   compute_association_rules()  ← ejecutar en precompute.py, no en tiempo real
   recommend_for_product()      ← consulta sobre las reglas precalculadas

2. Por cliente   — similitud coseno sobre matriz cliente×categoría (TruncatedSVD)
   recommend_for_customer()     ← calculado on-demand para un cliente específico
"""

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity


# ─── Reglas de asociación ────────────────────────────────────────────────────

def compute_association_rules(
    df_flat: pd.DataFrame,
    sample_frac: float = 0.30,
    min_support: float = 0.01,
    min_confidence: float = 0.3,
) -> pd.DataFrame:
    """
    Genera reglas de asociación entre productos usando FPGrowth.

    Usa una muestra aleatoria (sample_frac) para mantener tiempos razonables
    sobre el conjunto completo (~10 M ítems).

    Retorna DataFrame con columnas:
        antecedents  (list[int])
        consequents  (list[int])
        support, confidence, lift  (float)
    """
    from mlxtend.frequent_patterns import association_rules, fpgrowth

    # Agrupar ítems por (fecha, tienda, cliente) para obtener baskets
    baskets_series = (
        df_flat
        .groupby(["fecha", "id_tienda", "id_cliente"])["id_producto"]
        .apply(set)
        .reset_index(drop=True)
    )

    # Muestra aleatoria
    sample = baskets_series.sample(frac=sample_frac, random_state=42)

    # Todos los productos presentes en la muestra
    all_products = sorted({p for basket in sample for p in basket})

    # Matriz booleana transacciones × productos
    data = [{p: (p in basket) for p in all_products} for basket in sample]
    df_matrix = pd.DataFrame(data, dtype=bool)

    # FPGrowth
    freq_itemsets = fpgrowth(
        df_matrix, min_support=min_support, use_colnames=True
    )
    if freq_itemsets.empty:
        return pd.DataFrame(
            columns=["antecedents", "consequents", "support", "confidence", "lift"]
        )

    rules = association_rules(
        freq_itemsets, metric="confidence", min_threshold=min_confidence
    )

    # Serializar frozensets como listas de enteros (compatible con parquet)
    rules["antecedents"] = rules["antecedents"].apply(
        lambda s: sorted(int(x) for x in s)
    )
    rules["consequents"] = rules["consequents"].apply(
        lambda s: sorted(int(x) for x in s)
    )

    return rules[["antecedents", "consequents", "support", "confidence", "lift"]].reset_index(drop=True)


def recommend_for_product(
    product_id: int,
    rules_df: pd.DataFrame,
    top_n: int = 5,
) -> pd.DataFrame:
    """
    Filtra reglas cuyo antecedente contiene product_id.
    Ordena por lift descendente y retorna las top_n.
    """
    if rules_df is None or rules_df.empty:
        return pd.DataFrame(
            columns=["antecedents", "consequents", "support", "confidence", "lift"]
        )

    mask = rules_df["antecedents"].apply(lambda ant: product_id in ant)
    filtered = rules_df[mask].copy()
    return (
        filtered
        .sort_values("lift", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


# ─── Recomendación por cliente (similitud coseno) ────────────────────────────

def recommend_for_customer(
    customer_id: int,
    df_flat: pd.DataFrame,
    top_n: int = 5,
    n_neighbors: int = 10,
    n_components: int = 50,
) -> list[dict]:
    """
    Recomienda categorías para un cliente usando filtrado colaborativo:
      1. Construye matriz cliente × categoría (frecuencia de compra)
      2. Aplica TruncatedSVD para reducir dimensionalidad
      3. Calcula similitud coseno del cliente objetivo vs todos
      4. Reúne categorías compradas por vecinos que el cliente no ha comprado
      5. Ordena por puntaje acumulado de similitud

    Retorna lista de dicts: [{categoria, score}, ...]
    """
    # Matriz cliente × categoría
    pivot = (
        df_flat
        .groupby(["id_cliente", "nombre_categoria"])["id_producto"]
        .count()
        .unstack(fill_value=0)
    )

    if customer_id not in pivot.index:
        return []

    n_comp = min(n_components, pivot.shape[1] - 1, pivot.shape[0] - 1)
    if n_comp < 1:
        return []

    # SVD
    svd = TruncatedSVD(n_components=n_comp, random_state=42)
    matrix_svd = svd.fit_transform(pivot.values)

    customer_idx = pivot.index.get_loc(customer_id)
    customer_vec = matrix_svd[customer_idx].reshape(1, -1)

    # Similitud coseno
    sims = cosine_similarity(customer_vec, matrix_svd)[0]
    sims[customer_idx] = -1.0  # excluir al propio cliente

    # Índices de los n_neighbors más similares
    neighbor_indices = np.argsort(sims)[::-1][:n_neighbors]

    # Categorías ya compradas por el cliente
    customer_cats = set(pivot.columns[pivot.iloc[customer_idx].values > 0])

    # Acumular categorías nuevas ponderadas por similitud
    cat_scores: dict[str, float] = {}
    for idx in neighbor_indices:
        neighbor_cats = set(pivot.columns[pivot.iloc[idx].values > 0])
        for cat in neighbor_cats - customer_cats:
            cat_scores[cat] = cat_scores.get(cat, 0.0) + float(sims[idx])

    # Ordenar y devolver top_n
    sorted_cats = sorted(cat_scores.items(), key=lambda x: x[1], reverse=True)
    return [
        {"categoria": cat, "score": round(score, 4)}
        for cat, score in sorted_cats[:top_n]
    ]
