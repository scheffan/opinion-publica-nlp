import pandas as pd
import pytest

from opinion_publica.evaluacion import matriz_confusion, resumen


def test_matriz_incluye_clases_ausentes():
    m = matriz_confusion(pd.Series(["negativo", "negativo"]), pd.Series(["negativo", "neutro"]))
    assert list(m.index) == ["negativo", "neutro", "positivo"]
    assert m.loc["negativo", "negativo"] == 1
    assert m.loc["negativo", "neutro"] == 1
    assert m.loc["positivo"].sum() == 0


def test_metricas_calculadas_a_mano():
    # 4 negativos reales: el modelo acierta 3 y confunde 1 con neutro.
    # 2 neutros reales: acierta 1 y confunde 1 con negativo. 1 positivo: acierta.
    real = pd.Series(["negativo"] * 4 + ["neutro"] * 2 + ["positivo"])
    modelo = pd.Series(["negativo"] * 3 + ["neutro"] + ["neutro", "negativo"] + ["positivo"])
    r = resumen(real, modelo)
    neg = r["por_clase"].loc["negativo"]
    assert neg.precision == pytest.approx(3 / 4)   # predijo 4 negativos, 3 bien
    assert neg.recall == pytest.approx(3 / 4)      # había 4 negativos, encontró 3
    assert neg.f1 == pytest.approx(0.75)
    assert r["por_clase"].loc["neutro"].f1 == pytest.approx(0.5)
    assert r["exactitud"] == pytest.approx(5 / 7)
    assert r["f1_macro"] == pytest.approx((0.75 + 0.5 + 1) / 3)


def test_clase_nunca_predicha_da_f1_cero():
    r = resumen(pd.Series(["positivo", "negativo"]), pd.Series(["negativo", "negativo"]))
    assert r["por_clase"].loc["positivo"].f1 == 0
