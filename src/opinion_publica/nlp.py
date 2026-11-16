"""Análisis de texto con pysentimiento: sentimiento, emoción y discurso de odio.

Los modelos se inyectan (cualquier objeto con `.predict(lista_de_textos)`), así
los tests pueden usar modelos falsos y la lógica de armado de filas queda
probada sin descargar nada.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable, Protocol

RE_URL = re.compile(r"https?://\S+|\b[\w-]+(\.[\w-]+)+/\S*", re.IGNORECASE)
RE_MENCION = re.compile(r"@usuario")
RE_PALABRA = re.compile(r"[^\W\d_]{2,}")  # al menos dos letras seguidas

SENTIMIENTOS = {"POS": "positivo", "NEU": "neutro", "NEG": "negativo"}
EMOCIONES = {
    "joy": "alegria", "sadness": "tristeza", "anger": "enojo", "fear": "miedo",
    "disgust": "asco", "surprise": "sorpresa", "others": "otra",
}
MIN_PALABRAS = 2


class Salida(Protocol):
    output: object
    probas: dict


class Analizador(Protocol):
    def predict(self, textos: list[str]) -> list[Salida]: ...


def es_texto_util(texto: str) -> bool:
    """False si, sin links ni menciones, quedan menos de dos palabras."""
    limpio = RE_MENCION.sub(" ", RE_URL.sub(" ", texto or ""))
    return len(RE_PALABRA.findall(limpio)) >= MIN_PALABRAS


def fila_vacia(post_id: str, modelo: str, analizado: str) -> dict:
    fila = {"post_id": post_id, "modelo": modelo, "texto_util": False, "analizado": analizado}
    fila.update({"sentimiento": None, "p_positivo": None, "p_neutro": None, "p_negativo": None})
    fila["emocion"] = None
    fila.update({f"p_{e}": None for e in EMOCIONES.values()})
    fila.update({"odio": None, "p_odio": None, "p_agresivo": None, "p_dirigido": None})
    return fila


def armar_fila(post_id: str, modelo: str, analizado: str, sent: Salida, emo: Salida, odio: Salida) -> dict:
    fila = fila_vacia(post_id, modelo, analizado)
    fila["texto_util"] = True
    fila["sentimiento"] = SENTIMIENTOS[sent.output]
    for clave, nombre in SENTIMIENTOS.items():
        fila[f"p_{nombre}"] = float(sent.probas[clave])
    fila["emocion"] = EMOCIONES[emo.output]
    for clave, nombre in EMOCIONES.items():
        fila[f"p_{nombre}"] = float(emo.probas.get(clave, 0.0))
    etiquetas = odio.output or []
    fila["odio"] = "hateful" in etiquetas
    fila["p_odio"] = float(odio.probas["hateful"])
    fila["p_agresivo"] = float(odio.probas["aggressive"])
    fila["p_dirigido"] = float(odio.probas["targeted"])
    return fila


def analizar(
    posts: Iterable[tuple[str, str]],
    sentimiento: Analizador,
    emocion: Analizador,
    odio: Analizador,
    modelo: str,
) -> list[dict]:
    """Recibe pares (post_id, texto) y devuelve una fila por post."""
    analizado = datetime.now(timezone.utc).isoformat(timespec="seconds")
    posts = list(posts)
    utiles = [(pid, txt) for pid, txt in posts if es_texto_util(txt)]
    filas = {pid: fila_vacia(pid, modelo, analizado) for pid, _ in posts}
    if utiles:
        textos = [txt for _, txt in utiles]
        resultados = zip(sentimiento.predict(textos), emocion.predict(textos), odio.predict(textos))
        for (pid, _), (s, e, o) in zip(utiles, resultados):
            filas[pid] = armar_fila(pid, modelo, analizado, s, e, o)
    return [filas[pid] for pid, _ in posts]


def cargar_modelos():  # pragma: no cover - requiere descargar modelos
    """Crea los tres analizadores reales de pysentimiento en castellano."""
    import pysentimiento
    from pysentimiento import create_analyzer

    modelo = f"pysentimiento-{pysentimiento.__version__}"
    return (
        create_analyzer(task="sentiment", lang="es"),
        create_analyzer(task="emotion", lang="es"),
        create_analyzer(task="hate_speech", lang="es"),
        modelo,
    )
