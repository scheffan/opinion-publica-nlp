"""Clasifica con un modelo de lenguaje de Groq los posts etiquetados a mano.

Entradas:  data/etiquetado/etiquetas.csv, data/etiquetado/muestra.csv
Salida:    data/etiquetado/predicciones_llm.csv  (post_id, sentimiento, modelo)

Requiere la variable GROQ_API_KEY. Corre en GitHub Actions (workflow comparar-llm.yml).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pandas as pd

from opinion_publica.llm import clasificar, llamador_groq

CARPETA = Path("data/etiquetado")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    clave = os.environ.get("GROQ_API_KEY")
    if not clave:
        logging.error("Falta la variable GROQ_API_KEY")
        return 1

    etiquetas = pd.read_csv(CARPETA / "etiquetas.csv")
    muestra = pd.read_csv(CARPETA / "muestra.csv")
    posts = (etiquetas[etiquetas.sentimiento != "saltear"][["post_id"]]
             .merge(muestra[["post_id", "texto"]], on="post_id"))

    predichas, modelos = clasificar(posts.texto.tolist(), llamador_groq(clave))
    salida = posts[["post_id"]].assign(sentimiento=predichas, modelo=modelos)
    salida.to_csv(CARPETA / "predicciones_llm.csv", index=False)

    faltan = salida.sentimiento.isna().sum()
    logging.info("%d posts clasificados, %d sin respuesta. Modelos: %s",
                 len(salida) - faltan, faltan, salida.modelo.value_counts().to_dict())
    return 0 if faltan < len(salida) * 0.05 else 2


if __name__ == "__main__":
    sys.exit(main())
