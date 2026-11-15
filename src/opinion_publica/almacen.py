"""Limpieza de posts (privacidad) y guardado en Parquet por semana ISO.

Qué NO se guarda: handle, DID, nombre ni avatar del autor, ni la URI del post
(contiene el DID). El id es un hash de la URI: sirve para no duplicar, pero no
permite volver al autor. Las menciones dentro del texto se enmascaran.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

RE_MENCION = re.compile(r"(?<![\w@])@[A-Za-z0-9][A-Za-z0-9.\-]*[A-Za-z0-9]")
RE_PERFIL = re.compile(r"bsky\.app/profile/[^\s/]+", re.IGNORECASE)

COLUMNAS = [
    "post_id", "fecha", "creado", "indexado", "idiomas", "texto",
    "es_respuesta", "likes", "reposts", "respuestas", "citas",
    "temas", "terminos", "recolectado",
]


def hash_uri(uri: str) -> str:
    return hashlib.sha256(uri.encode("utf-8")).hexdigest()[:20]


def anonimizar_texto(texto: str) -> str:
    texto = RE_PERFIL.sub("bsky.app/profile/<usuario>", texto)
    return RE_MENCION.sub("@usuario", texto)


def limpiar_post(post: dict, tema: str, termino: str, fecha: date, recolectado: datetime) -> dict:
    """Convierte un post crudo de la API en una fila sin datos del autor."""
    record = post.get("record", {}) or {}
    return {
        "post_id": hash_uri(post["uri"]),
        "fecha": fecha.isoformat(),
        "creado": record.get("createdAt"),
        "indexado": post.get("indexedAt"),
        "idiomas": ",".join(record.get("langs") or []),
        "texto": anonimizar_texto(record.get("text", "")),
        "es_respuesta": "reply" in record,
        "likes": int(post.get("likeCount") or 0),
        "reposts": int(post.get("repostCount") or 0),
        "respuestas": int(post.get("replyCount") or 0),
        "citas": int(post.get("quoteCount") or 0),
        "temas": [tema],
        "terminos": [termino],
        "recolectado": recolectado.astimezone(timezone.utc).isoformat(timespec="seconds"),
    }


def _union_ordenada(listas) -> list[str]:
    vistos: set[str] = set()
    for lista in listas:
        vistos.update(lista)
    return sorted(vistos)


def consolidar(filas: list[dict] | pd.DataFrame) -> pd.DataFrame:
    """Un post por fila: si apareció en varios términos, une temas y términos.

    Para métricas y texto se queda con la recolección más reciente.
    """
    df = filas if isinstance(filas, pd.DataFrame) else pd.DataFrame(filas, columns=COLUMNAS)
    if df.empty:
        return pd.DataFrame(columns=COLUMNAS)
    df = df.sort_values("recolectado")
    listas = df.groupby("post_id").agg(
        temas=("temas", _union_ordenada), terminos=("terminos", _union_ordenada)
    )
    resto = df.drop(columns=["temas", "terminos"]).drop_duplicates("post_id", keep="last")
    salida = resto.set_index("post_id").join(listas).reset_index()
    return salida[COLUMNAS].sort_values(["fecha", "creado", "post_id"]).reset_index(drop=True)


def semana_iso(fecha: date) -> str:
    anio, semana, _ = fecha.isocalendar()
    return f"{anio}-W{semana:02d}"


def guardar_semana(nuevas: pd.DataFrame, ruta: Path) -> int:
    """Une con lo que ya hubiera en el archivo de esa semana y reescribe. Devuelve filas totales."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if ruta.exists():
        previas = pd.read_parquet(ruta)
        previas["temas"] = previas["temas"].map(list)
        previas["terminos"] = previas["terminos"].map(list)
        nuevas = pd.concat([previas, nuevas], ignore_index=True)
    df = consolidar(nuevas)
    df.to_parquet(ruta, index=False)
    return len(df)


def guardar_registro(registro: list[dict], ruta: Path) -> None:
    """Registro de cada consulta (fecha, término, cantidad, truncada). Reemplaza filas repetidas."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(registro)
    if ruta.exists():
        df = pd.concat([pd.read_csv(ruta), df], ignore_index=True)
    df = df.drop_duplicates(["fecha", "termino"], keep="last").sort_values(["fecha", "tema", "termino"])
    df.to_csv(ruta, index=False)
