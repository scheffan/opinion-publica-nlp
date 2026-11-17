"""Arma la muestra de posts para etiquetar a mano y validar el modelo.

Diseño:
- Estratificada por tema: la misma cantidad de posts por tema, para que no
  sean casi todos de Milei (que es el 70 % del volumen).
- Solo posts con texto útil (mismo filtro que el análisis).
- Sin la predicción del modelo: quien etiqueta no la ve, así no se deja llevar.
- Semilla fija: la muestra se puede reproducir exactamente.

Salida: data/etiquetado/muestra.csv  (post_id, tema, fecha, texto)

Uso:
    python scripts/muestra_etiquetado.py --por-tema 22
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from opinion_publica.nlp import es_texto_util

SEMILLA = 2026


def armar_muestra(posts: pd.DataFrame, por_tema: int, semilla: int = SEMILLA) -> pd.DataFrame:
    posts = posts[posts.texto.map(es_texto_util)]
    elegidos: list[pd.DataFrame] = []
    usados: set[str] = set()
    for tema in sorted(posts.temas.explode().unique()):
        candidatos = posts[posts.temas.map(lambda t: tema in t) & ~posts.post_id.isin(usados)]
        tomados = candidatos.sample(n=min(por_tema, len(candidatos)), random_state=semilla)
        usados.update(tomados.post_id)
        elegidos.append(tomados.assign(tema=tema)[["post_id", "tema", "fecha", "texto"]])
    muestra = pd.concat(elegidos, ignore_index=True)
    # Orden aleatorio para que los temas queden mezclados al etiquetar.
    return muestra.sample(frac=1, random_state=semilla).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--crudo", type=Path, default=Path("data/bluesky"))
    parser.add_argument("--salida", type=Path, default=Path("data/etiquetado/muestra.csv"))
    parser.add_argument("--por-tema", type=int, default=22)
    args = parser.parse_args()

    posts = pd.concat([pd.read_parquet(a) for a in sorted(args.crudo.glob("*.parquet"))], ignore_index=True)
    muestra = armar_muestra(posts, args.por_tema)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    muestra.to_csv(args.salida, index=False)
    print(f"{len(muestra)} posts → {args.salida}")
    print(muestra.tema.value_counts().to_string())


if __name__ == "__main__":
    main()
