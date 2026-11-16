"""Crea o actualiza el esquema, carga los datos del repo en PostgreSQL y corre los controles.

Uso:
    DATABASE_URL=postgresql://... python scripts/cargar_bd.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

import psycopg

from opinion_publica import carga, controles

log = logging.getLogger("cargar_bd")


def origen() -> str | None:
    if os.getenv("GITHUB_RUN_ID"):
        return f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    return None


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    url = os.environ.get("DATABASE_URL")
    if not url:
        log.error("Falta la variable DATABASE_URL")
        return 1

    with psycopg.connect(url, autocommit=True) as conn:
        with conn.cursor() as cur:
            carga.aplicar_sql(cur)
            cur.execute(
                "INSERT INTO opinion.etl_corrida (fuente, paso, inicio, estado, origen) "
                "VALUES ('bluesky', 'carga', %s, 'en_curso', %s) RETURNING corrida_id",
                (datetime.now(timezone.utc), origen()),
            )
            corrida = cur.fetchone()[0]

        try:
            with conn.transaction(), conn.cursor() as cur:
                resumen = carga.cargar_bluesky(cur)
            with conn.cursor() as cur:
                resultados, ok = controles.correr(cur)
        except Exception as error:
            with conn.cursor() as cur:
                cur.execute("UPDATE opinion.etl_corrida SET fin = now(), estado = 'error', detalle = %s "
                            "WHERE corrida_id = %s", (str(error)[:2000], corrida))
            raise

        detalle = "; ".join(f"{n}: {c}" for n, _, c in resultados)
        with conn.cursor() as cur:
            cur.execute("UPDATE opinion.etl_corrida SET fin = now(), estado = %s, filas = %s, detalle = %s "
                        "WHERE corrida_id = %s",
                        ("ok" if ok else "error", json.dumps(resumen), detalle, corrida))

    log.info("Filas insertadas o actualizadas: %s", resumen)
    for nombre, nivel, n in resultados:
        marca = "OK " if n == 0 else ("ERR" if nivel == "bloqueante" else "AVISO")
        log.info("[%s] %s: %d", marca, nombre, n)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
