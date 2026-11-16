"""Carga de los archivos del repo a PostgreSQL.

Cada tabla se carga con el mismo patrón: COPY a una tabla temporal y después
INSERT ... ON CONFLICT DO UPDATE. Así la carga es idempotente: correrla dos
veces deja la base igual, y si algo falla a mitad no queda nada a medias
(todo va en una sola transacción).
"""

from __future__ import annotations

import io
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

RAIZ = Path(__file__).resolve().parents[2]

COLS_POST = ["post_id", "fecha", "creado", "texto", "es_respuesta",
             "likes", "reposts", "respuestas", "citas", "recolectado"]
COLS_ANALISIS = ["post_id", "modelo", "texto_util", "sentimiento", "p_positivo", "p_neutro",
                 "p_negativo", "emocion", "p_alegria", "p_tristeza", "p_enojo", "p_miedo",
                 "p_asco", "p_sorpresa", "p_otra", "odio", "p_odio", "p_agresivo",
                 "p_dirigido", "analizado"]
COLS_CONSULTA = ["fecha", "tema", "termino", "posts", "ventanas", "truncada"]


# ─── Lectura de archivos ────────────────────────────────────────────────────

def leer_parquets(carpeta: Path) -> pd.DataFrame:
    archivos = sorted(carpeta.glob("*.parquet"))
    if not archivos:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(a) for a in archivos], ignore_index=True)


def leer_registro(carpeta: Path) -> pd.DataFrame:
    archivos = sorted(carpeta.glob("*.csv"))
    if not archivos:
        return pd.DataFrame(columns=COLS_CONSULTA)
    df = pd.concat([pd.read_csv(a) for a in archivos], ignore_index=True)
    return df.drop_duplicates(["fecha", "termino"], keep="last")[COLS_CONSULTA]


def tabla_temas(ruta: Path) -> pd.DataFrame:
    temas = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    return pd.DataFrame([{"tema": t, **datos} for t, datos in temas.items()])[["tema", "etiqueta", "categoria"]]


def tabla_fechas(desde: date, hasta: date) -> pd.DataFrame:
    filas = []
    for i in range((hasta - desde).days + 1):
        d = desde + timedelta(days=i)
        anio_iso, semana, dia = d.isocalendar()
        filas.append({
            "fecha": d, "anio": d.year, "mes": d.month, "semana_iso": f"{anio_iso}-W{semana:02d}",
            "inicio_semana": d - timedelta(days=dia - 1), "dia_semana": dia, "es_fin_de_semana": dia >= 6,
        })
    return pd.DataFrame(filas)


def tabla_post_tema(posts: pd.DataFrame) -> pd.DataFrame:
    df = posts[["post_id", "temas"]].explode("temas").rename(columns={"temas": "tema"})
    return df.dropna().drop_duplicates()


# ─── Escritura en la base ───────────────────────────────────────────────────

def _copiar(cur, df: pd.DataFrame, tabla_tmp: str, columnas: list[str]) -> None:
    """COPY rápido de un DataFrame a una tabla temporal (formato CSV)."""
    buf = io.StringIO()
    df[columnas].to_csv(buf, index=False, header=False, na_rep="\\N")
    buf.seek(0)
    with cur.copy(f"COPY {tabla_tmp} ({', '.join(columnas)}) FROM STDIN WITH (FORMAT csv, NULL '\\N')") as cp:
        cp.write(buf.read())


def upsert(cur, df: pd.DataFrame, tabla: str, columnas: list[str], clave: list[str],
           actualizar: bool = True, filtro: str | None = None) -> int:
    if df.empty:
        return 0
    tmp = f"tmp_{tabla}"
    cur.execute(f"CREATE TEMP TABLE {tmp} (LIKE opinion.{tabla} INCLUDING DEFAULTS) ON COMMIT DROP")
    _copiar(cur, df, tmp, columnas)
    lista = ", ".join(columnas)
    resto = [c for c in columnas if c not in clave]
    accion = (f"DO UPDATE SET {', '.join(f'{c} = EXCLUDED.{c}' for c in resto)}"
              if actualizar and resto else "DO NOTHING")
    where = f"WHERE {filtro}" if filtro else ""
    cur.execute(f"INSERT INTO opinion.{tabla} ({lista}) SELECT {lista} FROM {tmp} {where} "
                f"ON CONFLICT ({', '.join(clave)}) {accion}")
    filas = cur.rowcount
    cur.execute(f"DROP TABLE {tmp}")
    return filas


def aplicar_sql(cur, carpeta: Path = RAIZ / "sql") -> None:
    for archivo in sorted(carpeta.glob("*.sql")):
        cur.execute(archivo.read_text(encoding="utf-8"))


def cargar_bluesky(cur, raiz: Path = RAIZ) -> dict:
    posts = leer_parquets(raiz / "data/bluesky")
    analisis = leer_parquets(raiz / "data/procesado/analisis")
    consultas = leer_registro(raiz / "data/bluesky/registro")
    if posts.empty:
        return {}

    fechas = pd.to_datetime(pd.concat([posts.fecha, consultas.fecha])).dt.date
    resumen = {
        "dim_tema": upsert(cur, tabla_temas(raiz / "config/temas.yaml"), "dim_tema",
                           ["tema", "etiqueta", "categoria"], ["tema"]),
        "dim_fecha": upsert(cur, tabla_fechas(fechas.min(), fechas.max()), "dim_fecha",
                            ["fecha", "anio", "mes", "semana_iso", "inicio_semana", "dia_semana",
                             "es_fin_de_semana"], ["fecha"], actualizar=False),
        "bsky_post": upsert(cur, posts, "bsky_post", COLS_POST, ["post_id"]),
        "bsky_post_tema": upsert(cur, tabla_post_tema(posts), "bsky_post_tema",
                                 ["post_id", "tema"], ["post_id", "tema"], actualizar=False),
        "bsky_consulta": upsert(cur, consultas, "bsky_consulta", COLS_CONSULTA, ["fecha", "termino"]),
    }
    if not analisis.empty:
        resumen["bsky_analisis"] = upsert(
            cur, analisis, "bsky_analisis", COLS_ANALISIS, ["post_id"],
            filtro="post_id IN (SELECT post_id FROM opinion.bsky_post)",
        )
    return resumen
