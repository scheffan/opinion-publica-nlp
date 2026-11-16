"""Tests de datos: validan los archivos reales del repo, no código.

Corren en CI en cada push, así un dato roto se detecta antes de llegar a la base.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
import yaml

from opinion_publica.almacen import COLUMNAS

RAIZ = Path(__file__).resolve().parents[1]
CRUDO = sorted((RAIZ / "data/bluesky").glob("*.parquet"))
ANALISIS = sorted((RAIZ / "data/procesado/analisis").glob("*.parquet"))
REGISTRO = sorted((RAIZ / "data/bluesky/registro").glob("*.csv"))
TERMINOS = yaml.safe_load((RAIZ / "config/terminos.yaml").read_text(encoding="utf-8"))["temas"]
TEMAS = yaml.safe_load((RAIZ / "config/temas.yaml").read_text(encoding="utf-8"))

pytestmark = pytest.mark.skipif(not CRUDO, reason="todavía no hay datos recolectados")


def _dias_de_semana(semana: str) -> set[str]:
    anio, num = semana.split("-W")
    lunes = date.fromisocalendar(int(anio), int(num), 1)
    return {(lunes + timedelta(days=i)).isoformat() for i in range(7)}


def test_configs_de_temas_coinciden():
    assert set(TERMINOS) == set(TEMAS)


@pytest.mark.parametrize("archivo", CRUDO, ids=lambda p: p.stem)
def test_archivo_crudo(archivo):
    df = pd.read_parquet(archivo)
    assert list(df.columns) == COLUMNAS
    assert df.post_id.is_unique
    assert df.texto.notna().all()
    assert set(df.fecha) <= _dias_de_semana(archivo.stem), "hay fechas fuera de la semana del archivo"
    assert set(df.temas.explode()) <= set(TEMAS)
    assert not df.texto.str.contains(r"did:plc:|@[\w-]+\.bsky\.social", regex=True).any()
    assert (df[["likes", "reposts", "respuestas", "citas"]] >= 0).all().all()


@pytest.mark.parametrize("archivo", REGISTRO, ids=lambda p: p.stem)
def test_registro_cubre_cada_dia_y_termino(archivo):
    df = pd.read_csv(archivo)
    terminos = {t for lista in TERMINOS.values() for t in lista}
    por_dia = df.groupby("fecha").termino.apply(set)
    for dia, vistos in por_dia.items():
        assert vistos >= terminos, f"{dia}: faltan consultas para {terminos - vistos}"


@pytest.mark.parametrize("archivo", ANALISIS, ids=lambda p: p.stem)
def test_analisis_corresponde_a_posts_existentes(archivo):
    analisis = pd.read_parquet(archivo)
    crudo = pd.read_parquet(RAIZ / "data/bluesky" / archivo.name, columns=["post_id"])
    assert analisis.post_id.is_unique
    assert set(analisis.post_id) <= set(crudo.post_id)
    utiles = analisis[analisis.texto_util]
    suma = utiles[["p_positivo", "p_neutro", "p_negativo"]].sum(axis=1)
    assert ((suma - 1).abs() < 0.01).all()
    assert utiles.sentimiento.isin(["positivo", "neutro", "negativo"]).all()
