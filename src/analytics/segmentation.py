"""
K-Means clustering pipeline sobre features de clientes.

Retorna resultados listos para visualización en Streamlit:
- labels y coordenadas PCA(2D)
- estadísticas por segmento
- curva de inercia (elbow) para k=2..8
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

AVAILABLE_FEATURES = [
    "frecuencia",
    "n_productos_distintos",
    "volumen_total",
    "n_categorias_distintas",
]

FEATURE_LABELS = {
    "frecuencia": "Frecuencia de Compra",
    "n_productos_distintos": "Diversidad de Productos",
    "volumen_total": "Volumen Total",
    "n_categorias_distintas": "Diversidad de Categorías",
}

# Descripciones interpretativas por percentil del centroide
_QUINTILE_LABELS = ["muy bajo", "bajo", "moderado", "alto", "muy alto"]


def _quintile_label(value: float, col_min: float, col_max: float) -> str:
    if col_max == col_min:
        return "moderado"
    pct = (value - col_min) / (col_max - col_min)
    idx = min(int(pct * 5), 4)
    return _QUINTILE_LABELS[idx]


def _interpret_cluster(row: dict, features: list[str],
                       col_ranges: dict) -> str:
    parts = []
    for f in features:
        label = FEATURE_LABELS.get(f, f)
        ql = _quintile_label(row[f"{f}_mean"], *col_ranges[f])
        parts.append(f"{label}: {ql}")
    return " | ".join(parts)


def get_kmeans_results(
    df_customers: pd.DataFrame,
    features: list[str],
    k: int,
) -> dict:
    """
    Ejecuta el pipeline completo de segmentación K-Means.

    Parámetros:
        df_customers: DataFrame con columna id_cliente + features
        features:     lista de columnas a usar (subconjunto de AVAILABLE_FEATURES)
        k:            número de clusters

    Retorna dict con:
        labels          lista de enteros (cluster por cliente)
        customer_ids    IDs correspondientes
        pca_x / pca_y  coordenadas 2D para scatter
        pca_var         varianza explicada por cada componente PCA
        centers         centroides en espacio original (list of dicts)
        stats           estadísticas por cluster (list of dicts)
        inertia_curve   [{k, inertia}, ...] para k=2..8
        interpretation  texto descriptivo por cluster
    """
    df_work = df_customers[["id_cliente"] + features].dropna().copy()

    X = df_work[features].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # K-Means principal
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X_scaled)

    # PCA 2D para visualización
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X_scaled)

    # Curva de inercia k=2..8 (con menos iteraciones para velocidad)
    inertia_curve = []
    for ki in range(2, 9):
        m = KMeans(n_clusters=ki, random_state=42, n_init=5, max_iter=100)
        m.fit(X_scaled)
        inertia_curve.append({"k": ki, "inercia": round(m.inertia_, 2)})

    # Centroides en espacio original
    centers_orig = scaler.inverse_transform(km.cluster_centers_)
    centers_df = pd.DataFrame(centers_orig, columns=features)
    centers_df.insert(0, "cluster", range(k))

    # Estadísticas por cluster
    df_work = df_work.copy()
    df_work["cluster"] = labels
    col_ranges = {f: (df_work[f].min(), df_work[f].max()) for f in features}

    stats_rows = []
    interpretations = []
    for c in range(k):
        subset = df_work[df_work["cluster"] == c]
        row: dict = {"cluster": c, "n_clientes": len(subset)}
        for f in features:
            row[f"{f}_mean"]   = round(float(subset[f].mean()), 2)
            row[f"{f}_median"] = round(float(subset[f].median()), 2)
        stats_rows.append(row)
        interpretations.append(_interpret_cluster(row, features, col_ranges))

    return {
        "labels":         labels.tolist(),
        "customer_ids":   df_work["id_cliente"].tolist(),
        "pca_x":          coords[:, 0].tolist(),
        "pca_y":          coords[:, 1].tolist(),
        "pca_var":        [round(float(v), 4) for v in pca.explained_variance_ratio_],
        "centers":        centers_df.to_dict(orient="records"),
        "stats":          stats_rows,
        "inertia_curve":  inertia_curve,
        "interpretation": interpretations,
    }
