"""Genera grafana/bluesky.json: el tablero de Bluesky definido como código.

Todas las consultas leen las vistas del esquema `opinion` (ver sql/02_vistas.sql),
así cualquier número del tablero se puede reproducir con la misma consulta en SQL.
Sin variables de plantilla: los tableros compartidos públicamente no las admiten bien.

Uso:  python grafana/generar_bluesky.py
"""

from __future__ import annotations

import json
from pathlib import Path

DS = {"type": "grafana-postgresql-datasource", "uid": "${DS_OPINION}"}
REPO = "https://github.com/scheffan/opinion-publica-nlp"

# Un color fijo por tema, igual en todos los paneles.
COLORES = {
    "Milei": "#8F3BB8", "Kicillof": "#1F78C1", "Jorge Macri": "#F2CC0C", "Subte": "#56A64B",
    "ANSES": "#FF9830", "PAMI": "#E02F44", "AySA": "#5794F2", "Servicios públicos": "#8AB8FF",
    "Peyorativos": "#B877D9",
}
OVERRIDES_TEMAS = [
    {"matcher": {"id": "byName", "options": nombre},
     "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": color}}]}
    for nombre, color in COLORES.items()
]

ULTIMOS_3_MESES = "mes >= (SELECT max(mes) FROM v_bsky_mensual_conteos) - interval '2 months'"
ULTIMOS_12_MESES = "mes >= (SELECT max(mes) FROM v_bsky_mensual_conteos) - interval '11 months'"


def consulta(sql: str, formato: str = "table") -> dict:
    return {"refId": "A", "datasource": DS, "rawQuery": True, "editorMode": "code",
            "format": formato, "rawSql": " ".join(sql.split())}


def panel(id_: int, tipo: str, titulo: str, x: int, y: int, w: int, h: int, sql: str | None = None,
          formato: str = "table", descripcion: str = "", **extra) -> dict:
    p = {"id": id_, "type": tipo, "title": titulo, "description": descripcion,
         "gridPos": {"x": x, "y": y, "w": w, "h": h}}
    if sql:
        p["datasource"] = DS
        p["targets"] = [consulta(sql, formato)]
    p.update(extra)
    return p


def stat(id_: int, titulo: str, x: int, sql: str, unidad: str = "none", campo: str = "", desc: str = "") -> dict:
    return panel(
        id_, "stat", titulo, x, 5, 6, 4, sql, descripcion=desc,
        fieldConfig={"defaults": {"unit": unidad, "decimals": 1 if unidad == "percent" else 0,
                                  "color": {"mode": "fixed", "fixedColor": "text"}}, "overrides": []},
        options={"reduceOptions": {"calcs": ["lastNotNull"], "fields": campo, "values": False},
                 "textMode": "value", "colorMode": "none", "graphMode": "none", "justifyMode": "center"},
    )


ENCABEZADO = f"""
## Termómetro de descontento · Bluesky

Tono de los posts en castellano sobre nueve temas de la agenda argentina, desde enero de 2025. Se actualiza todos los lunes.

**% negativo**: posts negativos sobre los posts con texto analizable, según el modelo pysentimiento.
Validado contra 198 posts etiquetados a mano: acierta en el 71 % de los casos y, si se equivoca, tiende a
**subestimar** lo negativo (62 % contra 68 % en la muestra). Los meses con menos de 30 posts no se grafican.

**Bluesky no representa a toda la población argentina**: es un complemento, no una encuesta, y no mide intención de voto (Ley 26.215).
Solo se muestran datos agregados por tema; no se guarda quién escribió cada post.
[Metodología]({REPO}/blob/main/docs/metodologia.md) · [Validación del modelo]({REPO}/blob/main/docs/validacion.md) · [Código y ETL]({REPO})
"""

PIE = f"""
#### Cómo se arma este tablero

1. **GitHub Actions** recolecta cada lunes los posts de la semana anterior desde la API pública de Bluesky.
2. **pysentimiento** clasifica sentimiento, emoción y discurso de odio de cada post.
3. Los datos se cargan en **PostgreSQL (Neon)** con controles de calidad; las métricas son vistas SQL.
4. **Grafana** lee esas vistas con un usuario de solo lectura.

Intervalos de confianza: método de Wilson al 95 %. Detalle en [docs/]({REPO}/tree/main/docs).
"""


def tablero() -> dict:
    paneles = [
        panel(1, "text", "", 0, 0, 24, 5, options={"mode": "markdown", "content": ENCABEZADO.strip()}),

        stat(2, "Posts analizados", 0, "SELECT posts FROM v_bsky_resumen"),
        stat(3, "% negativo · último mes completo", 6,
             "SELECT round(100.0 * sum(negativos) / nullif(sum(posts_utiles), 0), 1) AS valor "
             "FROM v_bsky_mensual_conteos WHERE mes = (SELECT max(mes) FROM v_bsky_mensual_conteos)",
             unidad="percent", desc="Todos los temas juntos, último mes calendario terminado."),
        stat(4, "Período", 12,
             "SELECT to_char(desde, 'DD/MM/YYYY') || ' – ' || to_char(hasta, 'DD/MM/YYYY') AS periodo "
             "FROM v_bsky_resumen", campo="/^periodo$/"),
        stat(5, "Última actualización", 18,
             "SELECT to_char(ultima_carga AT TIME ZONE 'America/Argentina/Buenos_Aires', 'DD/MM/YYYY HH24:MI') "
             "AS actualizado FROM v_bsky_resumen", campo="/^actualizado$/",
             desc="Última carga exitosa a la base (hora argentina)."),

        panel(6, "timeseries", "% negativo por mes y tema", 0, 9, 16, 10,
              "SELECT mes::timestamp AS time, etiqueta AS metric, "
              "CASE WHEN posts_utiles >= 30 THEN round(100.0 * negativos / posts_utiles, 1) END AS value "
              "FROM v_bsky_mensual_conteos WHERE $__timeFilter(mes::timestamp) ORDER BY 1",
              formato="time_series",
              descripcion="Meses con menos de 30 posts útiles quedan en blanco (poca muestra).",
              fieldConfig={"defaults": {"unit": "percent", "min": 0, "max": 100,
                                        "custom": {"lineWidth": 2, "pointSize": 5, "showPoints": "always",
                                                   "spanNulls": False}},
                           "overrides": OVERRIDES_TEMAS},
              options={"legend": {"displayMode": "list", "placement": "bottom"},
                       "tooltip": {"mode": "multi", "sort": "desc"}}),

        panel(7, "bargauge", "Ranking · % negativo en los últimos 3 meses", 16, 9, 8, 10,
              "SELECT etiqueta, round(100.0 * sum(negativos) / nullif(sum(posts_utiles), 0), 1) AS \"% negativo\" "
              f"FROM v_bsky_mensual_conteos WHERE {ULTIMOS_3_MESES} GROUP BY etiqueta ORDER BY 2 DESC",
              fieldConfig={"defaults": {"unit": "percent", "min": 0, "max": 100, "decimals": 1,
                                        "color": {"mode": "continuous-GrYlRd"}}, "overrides": []},
              options={"orientation": "horizontal", "displayMode": "gradient", "showUnfilled": True,
                       "reduceOptions": {"calcs": [], "fields": "", "values": True}}),

        panel(8, "timeseries", "Milei · % negativo por semana (con margen de error)", 0, 19, 12, 9,
              "SELECT inicio_semana::timestamp AS time, pct_negativo AS \"% negativo\", "
              "pct_negativo_ic_inf AS \"IC inferior\", pct_negativo_ic_sup AS \"IC superior\" "
              "FROM v_bsky_semanal_tema WHERE tema = 'milei' AND $__timeFilter(inicio_semana::timestamp) ORDER BY 1",
              descripcion="Único tema con volumen semanal suficiente. La banda es el intervalo de confianza del 95 %: "
                          "si dos semanas tienen bandas superpuestas, la diferencia puede ser ruido.",
              fieldConfig={"defaults": {"unit": "percent", "color": {"mode": "fixed", "fixedColor": COLORES["Milei"]},
                                        "custom": {"lineWidth": 2}},
                           "overrides": [
                               {"matcher": {"id": "byName", "options": "IC superior"},
                                "properties": [{"id": "custom.fillBelowTo", "value": "IC inferior"},
                                               {"id": "custom.lineWidth", "value": 0},
                                               {"id": "custom.fillOpacity", "value": 20},
                                               {"id": "custom.hideFrom", "value": {"legend": True, "tooltip": False, "viz": False}}]},
                               {"matcher": {"id": "byName", "options": "IC inferior"},
                                "properties": [{"id": "custom.lineWidth", "value": 0},
                                               {"id": "custom.hideFrom", "value": {"legend": True, "tooltip": False, "viz": False}}]},
                           ]},
              options={"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}),

        panel(9, "timeseries", "Atención · reparto del volumen de posts entre temas", 12, 19, 12, 9,
              "SELECT mes::timestamp AS time, etiqueta AS metric, posts AS value "
              "FROM v_bsky_mensual_conteos WHERE $__timeFilter(mes::timestamp) ORDER BY 1",
              formato="time_series",
              descripcion="Qué parte de la conversación se lleva cada tema por mes. Se usa el porcentaje porque "
                          "la actividad total de Bluesky bajó en 2026.",
              fieldConfig={"defaults": {"unit": "short",
                                        "custom": {"fillOpacity": 70, "lineWidth": 1,
                                                   "stacking": {"mode": "percent", "group": "A"}}},
                           "overrides": OVERRIDES_TEMAS},
              options={"legend": {"displayMode": "list", "placement": "bottom"},
                       "tooltip": {"mode": "multi", "sort": "desc"}}),

        panel(10, "barchart", "Emociones por tema · últimos 3 meses", 0, 28, 12, 10,
              "SELECT etiqueta AS \"Tema\", "
              + ", ".join(f"round(100.0 * coalesce(sum(posts) FILTER (WHERE emocion = '{e}'), 0) / sum(posts), 1) AS \"{n}\""
                          for e, n in [("enojo", "Enojo"), ("tristeza", "Tristeza"), ("miedo", "Miedo"),
                                       ("asco", "Asco"), ("alegria", "Alegría"), ("sorpresa", "Sorpresa"),
                                       ("otra", "Otra")])
              + " FROM v_bsky_emociones_mensual "
              "WHERE mes >= (SELECT max(mes) FROM v_bsky_emociones_mensual) - interval '2 months' "
              "GROUP BY etiqueta ORDER BY 2 DESC",
              descripcion="Emoción principal de cada post según el modelo, sobre los posts con texto analizable.",
              fieldConfig={"defaults": {"unit": "percent", "custom": {"fillOpacity": 85, "lineWidth": 0}},
                           "overrides": [
                               {"matcher": {"id": "byName", "options": n},
                                "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}]}
                               for n, c in [("Enojo", "#E02F44"), ("Tristeza", "#5794F2"), ("Miedo", "#8F3BB8"),
                                            ("Asco", "#56A64B"), ("Alegría", "#F2CC0C"), ("Sorpresa", "#FF9830"),
                                            ("Otra", "#808080")]]},
              options={"orientation": "horizontal", "stacking": "normal", "xField": "Tema",
                       "showValue": "never", "legend": {"displayMode": "list", "placement": "bottom"},
                       "tooltip": {"mode": "multi"}}),

        panel(11, "bargauge", "Discurso de odio · % de posts en los últimos 12 meses", 12, 28, 12, 10,
              "SELECT etiqueta, round(100.0 * sum(con_odio) / nullif(sum(posts_utiles), 0), 1) AS \"% con odio\" "
              f"FROM v_bsky_mensual_conteos WHERE {ULTIMOS_12_MESES} GROUP BY etiqueta ORDER BY 2 DESC",
              descripcion="Posts que el modelo marca como discurso de odio. El tema 'Peyorativos' se arma con "
                          "insultos partidarios, por eso encabeza.",
              fieldConfig={"defaults": {"unit": "percent", "min": 0, "decimals": 1,
                                        "color": {"mode": "fixed", "fixedColor": "#E02F44"}}, "overrides": []},
              options={"orientation": "horizontal", "displayMode": "basic", "showUnfilled": True,
                       "reduceOptions": {"calcs": [], "fields": "", "values": True}}),

        panel(12, "table", "Cobertura de la recolección · últimas 12 semanas", 0, 38, 12, 9,
              "SELECT semana_iso AS \"Semana\", dias_con_datos AS \"Días con datos\", "
              "consultas_truncadas AS \"Consultas truncadas\", posts_reportados_api AS \"Posts devueltos por la API\" "
              "FROM v_bsky_cobertura ORDER BY semana_iso DESC LIMIT 12",
              descripcion="Control de calidad: cada semana debería tener 7 días y 0 consultas truncadas.",
              fieldConfig={"defaults": {"custom": {"align": "center"}}, "overrides": []},
              options={"showHeader": True}),

        panel(13, "text", "", 12, 38, 12, 9, options={"mode": "markdown", "content": PIE.strip()}),
    ]
    return {
        "__inputs": [{"name": "DS_OPINION", "label": "PostgreSQL (Neon) · opinion", "type": "datasource",
                      "pluginId": "grafana-postgresql-datasource", "pluginName": "PostgreSQL"}],
        "title": "Termómetro de descontento · Bluesky",
        "uid": "opinion-bluesky",
        "description": "Tono de los posts en castellano sobre temas de la agenda argentina (opinion-publica-nlp).",
        "tags": ["opinion-publica-nlp", "bluesky", "nlp"],
        "timezone": "America/Argentina/Buenos_Aires",
        "time": {"from": "2025-01-01T00:00:00.000Z", "to": "now"},
        "refresh": "",
        "editable": True,
        "graphTooltip": 1,
        "schemaVersion": 39,
        "panels": paneles,
        "links": [{"title": "Repositorio", "url": REPO, "type": "link", "targetBlank": True, "icon": "external link"}],
    }


if __name__ == "__main__":
    destino = Path(__file__).with_name("bluesky.json")
    destino.write_text(json.dumps(tablero(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Tablero escrito en {destino}")
