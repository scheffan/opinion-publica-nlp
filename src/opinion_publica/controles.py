"""Controles de calidad que corren en la base después de cada carga.

Cada control es una consulta que devuelve la cantidad de filas con problema.
Los 'bloqueantes' hacen fallar el workflow; las 'advertencias' solo se informan.
"""

from __future__ import annotations

CONTROLES = [
    # (nombre, nivel, consulta que cuenta filas con problema)
    ("posts sin tema", "bloqueante",
     "SELECT count(*) FROM opinion.bsky_post p WHERE NOT EXISTS "
     "(SELECT 1 FROM opinion.bsky_post_tema t WHERE t.post_id = p.post_id)"),
    ("probabilidades de sentimiento que no suman 1", "bloqueante",
     "SELECT count(*) FROM opinion.bsky_analisis WHERE texto_util "
     "AND abs(p_positivo + p_neutro + p_negativo - 1) > 0.01"),
    ("probabilidades de emoción que no suman 1", "bloqueante",
     "SELECT count(*) FROM opinion.bsky_analisis WHERE texto_util "
     "AND abs(p_alegria + p_tristeza + p_enojo + p_miedo + p_asco + p_sorpresa + p_otra - 1) > 0.01"),
    ("handles o DIDs en el texto", "bloqueante",
     r"SELECT count(*) FROM opinion.bsky_post WHERE texto ~* '(did:plc:|@[a-z0-9-]+\.bsky\.social)'"),
    ("días sin consultas dentro del período", "bloqueante",
     "SELECT count(*) FROM opinion.dim_fecha f WHERE f.fecha BETWEEN "
     "(SELECT min(fecha) FROM opinion.bsky_consulta) AND (SELECT max(fecha) FROM opinion.bsky_consulta) "
     "AND NOT EXISTS (SELECT 1 FROM opinion.bsky_consulta c WHERE c.fecha = f.fecha)"),
    ("consultas truncadas (puede faltar volumen)", "advertencia",
     "SELECT count(*) FROM opinion.bsky_consulta WHERE truncada"),
    ("posts sin análisis", "advertencia",
     "SELECT count(*) FROM opinion.bsky_post p LEFT JOIN opinion.bsky_analisis a USING (post_id) "
     "WHERE a.post_id IS NULL"),
]


def correr(cur) -> tuple[list[tuple[str, str, int]], bool]:
    resultados, ok = [], True
    for nombre, nivel, consulta in CONTROLES:
        cur.execute(consulta)
        n = cur.fetchone()[0]
        resultados.append((nombre, nivel, n))
        if n and nivel == "bloqueante":
            ok = False
    return resultados, ok
