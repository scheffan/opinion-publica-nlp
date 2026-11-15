"""Cliente mínimo de la búsqueda pública de Bluesky.

Sin autenticación, la API devuelve 403 al paginar con `cursor`. Por eso cada
búsqueda pide solo la primera página (hasta 100 posts) dentro de una ventana
de tiempo acotada con `since`/`until`. Si la ventana viene llena, se parte en
dos y se vuelve a pedir, hasta llegar a la ventana mínima.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo

import requests

API_URL = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
LIMITE = 100
VENTANA_MINIMA = timedelta(hours=1)
ZONA_AR = ZoneInfo("America/Argentina/Buenos_Aires")

log = logging.getLogger(__name__)

# Firma de una función de búsqueda: (consulta, desde, hasta) -> lista de posts
Buscador = Callable[[str, datetime, datetime], list[dict]]


def iso_utc(momento: datetime) -> str:
    """Formato que espera la API: ISO 8601 en UTC con Z."""
    return momento.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dia_en_utc(dia: date, zona: ZoneInfo = ZONA_AR) -> tuple[datetime, datetime]:
    """Inicio y fin de un día calendario de Argentina, como instantes UTC."""
    inicio = datetime(dia.year, dia.month, dia.day, tzinfo=zona)
    fin = inicio + timedelta(days=1)
    return inicio.astimezone(timezone.utc), fin.astimezone(timezone.utc)


def dias(desde: date, hasta: date) -> list[date]:
    """Días entre `desde` y `hasta`, ambos incluidos."""
    if hasta < desde:
        raise ValueError("`hasta` no puede ser anterior a `desde`")
    return [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]


class ClienteBluesky:
    """Hace las consultas HTTP, con pausa entre pedidos y reintentos."""

    def __init__(self, pausa: float = 0.4, reintentos: int = 4, timeout: float = 30):
        self.pausa = pausa
        self.reintentos = reintentos
        self.timeout = timeout
        self.sesion = requests.Session()
        self.sesion.headers["User-Agent"] = (
            "opinion-publica-nlp/0.1 (+https://github.com/scheffan/opinion-publica-nlp)"
        )
        self.pedidos = 0

    def buscar(self, consulta: str, desde: datetime, hasta: datetime, idioma: str = "es") -> list[dict]:
        params = {
            "q": consulta,
            "lang": idioma,
            "limit": LIMITE,
            "sort": "latest",
            "since": iso_utc(desde),
            "until": iso_utc(hasta),
        }
        espera = 2.0
        for intento in range(1, self.reintentos + 1):
            time.sleep(self.pausa)
            self.pedidos += 1
            try:
                resp = self.sesion.get(API_URL, params=params, timeout=self.timeout)
            except requests.RequestException as error:
                log.warning("Error de red (%s), intento %d", error, intento)
            else:
                if resp.status_code == 200:
                    return resp.json().get("posts", [])
                if resp.status_code not in (429, 500, 502, 503, 504):
                    resp.raise_for_status()
                log.warning("HTTP %d en %r, intento %d", resp.status_code, consulta, intento)
            time.sleep(espera)
            espera *= 2
        raise RuntimeError(f"Sin respuesta para {consulta!r} {params['since']}..{params['until']}")


@dataclass
class Resultado:
    posts: list[dict] = field(default_factory=list)
    ventanas: int = 0
    truncada: bool = False


def buscar_ventana(
    buscador: Buscador,
    consulta: str,
    desde: datetime,
    hasta: datetime,
    minima: timedelta = VENTANA_MINIMA,
) -> Resultado:
    """Busca en [desde, hasta). Si la respuesta llega al tope, parte la ventana en dos.

    `truncada` queda en True si alguna ventana mínima siguió llena: en ese caso
    puede haber posts que no se trajeron.
    """
    posts = buscador(consulta, desde, hasta)
    if len(posts) < LIMITE:
        return Resultado(posts=posts, ventanas=1)

    if hasta - desde <= minima:
        return Resultado(posts=posts, ventanas=1, truncada=True)

    mitad = desde + (hasta - desde) / 2
    izq = buscar_ventana(buscador, consulta, desde, mitad, minima)
    der = buscar_ventana(buscador, consulta, mitad, hasta, minima)
    return Resultado(
        posts=izq.posts + der.posts,
        ventanas=izq.ventanas + der.ventanas,
        truncada=izq.truncada or der.truncada,
    )
