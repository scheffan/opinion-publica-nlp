"""Clasificación de sentimiento con un modelo de lenguaje (Groq), para comparar con pysentimiento.

El modelo recibe los mismos criterios que usó la persona que etiquetó a mano
(ver la página de etiquetado), así la comparación es justa. Los posts van de a
lotes con un número corto como id, para que el modelo no tenga que copiar hashes.
"""

from __future__ import annotations

import json
import time
from typing import Callable

import requests

API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELOS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]
CLASES = {"negativo", "neutro", "positivo"}

CRITERIOS = """Sos un anotador de opinión pública que conoce el castellano rioplatense y la política argentina.
Para cada post, etiquetá el TONO QUE EXPRESA SU AUTOR, no si estás de acuerdo.

- negativo: queja, crítica, enojo, burla, insulto, denuncia, reclamo, mala noticia contada con desagrado.
  Los reclamos y protestas ("no permitamos que…") son negativos aunque estén escritos con calma.
- neutro: informa, pregunta o comparte una noticia sin tomar posición. Titulares descriptivos van acá.
- positivo: elogio, apoyo, alegría, agradecimiento, buena noticia celebrada, propaganda que destaca logros.
- Ironía y sarcasmo: etiquetá lo que el autor quiere decir de verdad (un elogio sarcástico es negativo).

Respondé solo con JSON: {"resultados": [{"id": <número>, "sentimiento": "negativo" | "neutro" | "positivo"}]}
con exactamente un resultado por post."""

# Firma de la función que hace la llamada: (modelo, mensajes) -> texto de la respuesta
Llamador = Callable[[str, list[dict]], str]


def armar_mensajes(textos: list[str]) -> list[dict]:
    posts = "\n\n".join(f"[{i}] {t}" for i, t in enumerate(textos, start=1))
    return [
        {"role": "system", "content": CRITERIOS},
        {"role": "user", "content": f"Posts a etiquetar:\n\n{posts}"},
    ]


def interpretar(respuesta: str, cantidad: int) -> list[str | None]:
    """Devuelve una etiqueta por post (None si el modelo no la dio o es inválida)."""
    try:
        datos = json.loads(respuesta)
    except json.JSONDecodeError:
        inicio, fin = respuesta.find("{"), respuesta.rfind("}")
        datos = json.loads(respuesta[inicio:fin + 1]) if inicio != -1 else {}
    etiquetas: list[str | None] = [None] * cantidad
    for item in datos.get("resultados", []):
        try:
            i = int(item["id"]) - 1
        except (KeyError, TypeError, ValueError):
            continue
        valor = str(item.get("sentimiento", "")).strip().lower()
        if 0 <= i < cantidad and valor in CLASES:
            etiquetas[i] = valor
    return etiquetas


def clasificar(textos: list[str], llamar: Llamador, lote: int = 10,
               modelos: list[str] = MODELOS) -> tuple[list[str | None], list[str | None]]:
    """Clasifica todos los textos. Devuelve (etiquetas, modelo que respondió cada una)."""
    etiquetas: list[str | None] = []
    usados: list[str | None] = []
    for i in range(0, len(textos), lote):
        parte = textos[i:i + lote]
        resultado, usado = [None] * len(parte), None
        for modelo in modelos:
            try:
                resultado = interpretar(llamar(modelo, armar_mensajes(parte)), len(parte))
                usado = modelo
                break
            except Exception:  # noqa: BLE001 - se prueba el modelo siguiente
                continue
        etiquetas += resultado
        usados += [usado if r else None for r in resultado]
    return etiquetas, usados


def llamador_groq(clave: str, pausa: float = 3.0, reintentos: int = 4) -> Llamador:  # pragma: no cover - red
    sesion = requests.Session()
    sesion.headers.update({"Authorization": f"Bearer {clave}", "Content-Type": "application/json"})

    def llamar(modelo: str, mensajes: list[dict]) -> str:
        cuerpo = {"model": modelo, "messages": mensajes, "temperature": 0,
                  "response_format": {"type": "json_object"}, "max_completion_tokens": 4000}
        espera = 10.0
        for _ in range(reintentos):
            time.sleep(pausa)
            resp = sesion.post(API_URL, json=cuerpo, timeout=120)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            if resp.status_code in (429, 500, 502, 503):
                time.sleep(espera)
                espera *= 2
                continue
            raise RuntimeError(f"Groq respondió {resp.status_code}: {resp.text[:200]}")
        raise RuntimeError("Groq no respondió después de varios intentos")

    return llamar
