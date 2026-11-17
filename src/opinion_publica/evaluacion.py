"""Métricas para comparar las etiquetas a mano con las predicciones del modelo.

Se implementan a mano (sin scikit-learn) para que las fórmulas queden a la vista:
  precisión = aciertos de la clase / veces que el modelo predijo esa clase
  recall    = aciertos de la clase / veces que la clase era la correcta
  F1        = media armónica de precisión y recall
"""

from __future__ import annotations

import pandas as pd

CLASES = ["negativo", "neutro", "positivo"]


def matriz_confusion(real: pd.Series, predicho: pd.Series, clases: list[str] = CLASES) -> pd.DataFrame:
    """Filas: etiqueta a mano. Columnas: predicción del modelo."""
    tabla = pd.crosstab(pd.Categorical(real, clases), pd.Categorical(predicho, clases), dropna=False)
    tabla.index.name, tabla.columns.name = "real", "modelo"
    return tabla.reindex(index=clases, columns=clases, fill_value=0)


def metricas_por_clase(matriz: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for clase in matriz.index:
        aciertos = matriz.loc[clase, clase]
        predichos = matriz[clase].sum()
        reales = matriz.loc[clase].sum()
        precision = aciertos / predichos if predichos else 0.0
        recall = aciertos / reales if reales else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        filas.append({"clase": clase, "precision": precision, "recall": recall, "f1": f1, "casos": int(reales)})
    return pd.DataFrame(filas).set_index("clase")


def resumen(real: pd.Series, predicho: pd.Series) -> dict:
    matriz = matriz_confusion(real, predicho)
    por_clase = metricas_por_clase(matriz)
    total = int(matriz.values.sum())
    return {
        "casos": total,
        "exactitud": float(matriz.values.trace() / total) if total else 0.0,
        "f1_macro": float(por_clase.f1.mean()),
        "por_clase": por_clase,
        "matriz": matriz,
    }
