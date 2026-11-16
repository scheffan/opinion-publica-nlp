"""Analiza los posts de Bluesky que todavía no tienen análisis y guarda el resultado.

Entrada:  data/bluesky/AAAA-Www.parquet          (crudo)
Salida:   data/procesado/analisis/AAAA-Www.parquet (una fila por post)

Es incremental: solo procesa posts sin análisis o analizados con otra versión
del modelo. Con --minutos corta prolijo antes del límite de tiempo y guarda lo
hecho; la próxima corrida sigue desde ahí.

Uso:
    python scripts/analizar_sentimiento.py --minutos 300
    python scripts/analizar_sentimiento.py --semanas 2026-W45 --max-posts 500   # prueba de velocidad
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import pandas as pd

from opinion_publica.nlp import analizar, cargar_modelos

log = logging.getLogger("analizar")
LOTE = 256


def pendientes(crudo: Path, salida: Path, modelo: str) -> pd.DataFrame:
    posts = pd.read_parquet(crudo, columns=["post_id", "texto"])
    if salida.exists():
        hechos = pd.read_parquet(salida, columns=["post_id", "modelo"])
        hechos = hechos.loc[hechos.modelo == modelo, "post_id"]
        posts = posts[~posts.post_id.isin(hechos)]
    return posts


def guardar(filas: list[dict], salida: Path) -> int:
    nuevas = pd.DataFrame(filas)
    if salida.exists():
        nuevas = pd.concat([pd.read_parquet(salida), nuevas], ignore_index=True)
    nuevas = nuevas.drop_duplicates("post_id", keep="last").sort_values("post_id")
    salida.parent.mkdir(parents=True, exist_ok=True)
    nuevas.to_parquet(salida, index=False)
    return len(nuevas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--crudo", type=Path, default=Path("data/bluesky"))
    parser.add_argument("--salida", type=Path, default=Path("data/procesado/analisis"))
    parser.add_argument("--semanas", nargs="*", help="solo estas semanas (AAAA-Www)")
    parser.add_argument("--minutos", type=float, default=None, help="presupuesto de tiempo")
    parser.add_argument("--max-posts", type=int, default=None, help="tope de posts (para pruebas)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    t0 = time.monotonic()
    sent, emo, odio, modelo = cargar_modelos()
    log.info("Modelos cargados (%s) en %.0f s", modelo, time.monotonic() - t0)

    archivos = sorted(args.crudo.glob("*.parquet"), reverse=True)  # primero lo más reciente
    if args.semanas:
        archivos = [a for a in archivos if a.stem in set(args.semanas)]

    total, inicio = 0, time.monotonic()
    for crudo in archivos:
        destino = args.salida / crudo.name
        faltan = pendientes(crudo, destino, modelo)
        if args.max_posts is not None:
            faltan = faltan.head(max(args.max_posts - total, 0))
        if faltan.empty:
            continue
        filas = []
        for i in range(0, len(faltan), LOTE):
            lote = faltan.iloc[i:i + LOTE]
            filas += analizar(zip(lote.post_id, lote.texto), sent, emo, odio, modelo)
            if args.minutos and (time.monotonic() - inicio) / 60 > args.minutos:
                break
        guardar(filas, destino)
        total += len(filas)
        ritmo = total / max(time.monotonic() - inicio, 1e-9)
        log.info("%s: %d posts analizados (%.1f posts/s acumulado)", crudo.stem, len(filas), ritmo)
        if args.minutos and (time.monotonic() - inicio) / 60 > args.minutos:
            log.warning("Se alcanzó el presupuesto de %s minutos; sigue en la próxima corrida", args.minutos)
            break
        if args.max_posts is not None and total >= args.max_posts:
            break

    log.info("Listo: %d posts en %.1f min", total, (time.monotonic() - inicio) / 60)


if __name__ == "__main__":
    main()
