"""Recolecta posts de Bluesky por término y por día, y los guarda por semana ISO.

Uso:
    python scripts/recolectar_bluesky.py --semana-anterior
    python scripts/recolectar_bluesky.py --desde 2025-01-01 --hasta 2025-03-31
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from opinion_publica.almacen import (
    consolidar, guardar_registro, guardar_semana, limpiar_post, semana_iso,
)
from opinion_publica.bluesky import ZONA_AR, ClienteBluesky, buscar_ventana, dia_en_utc, dias

log = logging.getLogger("recolectar")


def semana_anterior(hoy: date) -> tuple[date, date]:
    lunes = hoy - timedelta(days=hoy.weekday() + 7)
    return lunes, lunes + timedelta(days=6)


def cargar_config(ruta: Path) -> tuple[str, list[tuple[str, str]]]:
    config = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    pares = [(tema, termino) for tema, terminos in config["temas"].items() for termino in terminos]
    return config.get("idioma", "es"), pares


def guardar(filas: list[dict], registro: list[dict], semana: str, salida: Path) -> None:
    total = guardar_semana(consolidar(filas), salida / f"{semana}.parquet")
    guardar_registro(registro, salida / "registro" / f"{semana}.csv")
    log.info("Semana %s guardada: %d posts únicos en el archivo", semana, total)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--semana-anterior", action="store_true", help="lunes a domingo de la semana pasada")
    grupo.add_argument("--desde", type=date.fromisoformat, help="AAAA-MM-DD (incluido)")
    parser.add_argument("--hasta", type=date.fromisoformat, help="AAAA-MM-DD (incluido)")
    parser.add_argument("--config", type=Path, default=Path("config/terminos.yaml"))
    parser.add_argument("--salida", type=Path, default=Path("data/bluesky"))
    parser.add_argument("--pausa", type=float, default=0.4, help="segundos entre pedidos")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    hoy = datetime.now(ZONA_AR).date()
    if args.semana_anterior:
        desde, hasta = semana_anterior(hoy)
    else:
        desde, hasta = args.desde, args.hasta or hoy - timedelta(days=1)
    if hasta >= hoy:
        hasta = hoy - timedelta(days=1)
        log.warning("Se recorta `hasta` a %s para no guardar el día en curso incompleto", hasta)

    idioma, pares = cargar_config(args.config)
    cliente = ClienteBluesky(pausa=args.pausa)

    def buscador(consulta, ini, fin):
        return cliente.buscar(consulta, ini, fin, idioma=idioma)

    log.info("Recolectando %s a %s, %d términos", desde, hasta, len(pares))
    semana_actual, filas, registro = None, [], []

    for dia in dias(desde, hasta):
        semana = semana_iso(dia)
        if semana_actual and semana != semana_actual:
            guardar(filas, registro, semana_actual, args.salida)
            filas, registro = [], []
        semana_actual = semana

        inicio, fin = dia_en_utc(dia)
        recolectado = datetime.now(timezone.utc)
        for tema, termino in pares:
            res = buscar_ventana(buscador, termino, inicio, fin)
            filas += [limpiar_post(p, tema, termino, dia, recolectado) for p in res.posts]
            registro.append({
                "fecha": dia.isoformat(), "tema": tema, "termino": termino,
                "posts": len(res.posts), "ventanas": res.ventanas, "truncada": res.truncada,
            })
            if res.truncada:
                log.warning("%s %r: ventana truncada, puede faltar volumen", dia, termino)
        log.info("%s listo (%d pedidos acumulados)", dia, cliente.pedidos)

    if semana_actual:
        guardar(filas, registro, semana_actual, args.salida)


if __name__ == "__main__":
    main()
