from dataclasses import dataclass, field

import pytest

from opinion_publica.nlp import analizar, es_texto_util


@dataclass
class _Salida:
    output: object
    probas: dict = field(default_factory=dict)


class _Fijo:
    """Analizador falso: devuelve siempre la misma salida y cuenta los textos."""

    def __init__(self, salida):
        self.salida, self.vistos = salida, []

    def predict(self, textos):
        self.vistos += textos
        return [self.salida for _ in textos]


SENT = _Salida("NEG", {"NEG": 0.8, "NEU": 0.15, "POS": 0.05})
EMO = _Salida("anger", {"anger": 0.7, "joy": 0.05, "sadness": 0.05, "fear": 0.05,
                        "disgust": 0.05, "surprise": 0.05, "others": 0.05})
ODIO = _Salida(["hateful", "aggressive"], {"hateful": 0.6, "aggressive": 0.7, "targeted": 0.1})


@pytest.mark.parametrize("texto, esperado", [
    ("Otra vez sin subte", True),
    ("Fuera Milei", True),
    ("https://x.com/algo", False),
    ("@usuario 👍", False),
    ("jaja", False),
    ("", False),
])
def test_texto_util(texto, esperado):
    assert es_texto_util(texto) is esperado


def test_solo_se_mandan_al_modelo_los_textos_utiles():
    s, e, o = _Fijo(SENT), _Fijo(EMO), _Fijo(ODIO)
    filas = analizar([("a", "Otra vez sin luz en el barrio"), ("b", "https://x.com/1")], s, e, o, "test")
    assert s.vistos == ["Otra vez sin luz en el barrio"]
    assert [f["post_id"] for f in filas] == ["a", "b"]
    assert filas[1]["texto_util"] is False and filas[1]["sentimiento"] is None


def test_traduce_etiquetas_y_probabilidades():
    fila = analizar([("a", "Edesur nos dejó sin luz")], _Fijo(SENT), _Fijo(EMO), _Fijo(ODIO), "test")[0]
    assert fila["sentimiento"] == "negativo"
    assert fila["emocion"] == "enojo"
    assert fila["odio"] is True
    assert fila["p_negativo"] == pytest.approx(0.8)
    assert fila["p_enojo"] == pytest.approx(0.7)
    assert fila["p_positivo"] + fila["p_neutro"] + fila["p_negativo"] == pytest.approx(1)


def test_sin_etiquetas_de_odio_es_false():
    sin_odio = _Salida([], {"hateful": 0.02, "aggressive": 0.01, "targeted": 0.01})
    fila = analizar([("a", "Hoy anduvo bien el subte")], _Fijo(SENT), _Fijo(EMO), _Fijo(sin_odio), "t")[0]
    assert fila["odio"] is False
