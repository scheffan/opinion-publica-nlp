import json

from opinion_publica.llm import armar_mensajes, clasificar, interpretar


def test_mensajes_numeran_los_posts():
    m = armar_mensajes(["uno", "dos"])
    assert "[1] uno" in m[1]["content"] and "[2] dos" in m[1]["content"]
    assert "tono" in m[0]["content"].lower()


def test_interpretar_respuesta_valida_e_ignora_basura():
    resp = json.dumps({"resultados": [
        {"id": 2, "sentimiento": "Negativo"},
        {"id": 1, "sentimiento": "neutro"},
        {"id": 9, "sentimiento": "positivo"},      # fuera de rango
        {"id": 3, "sentimiento": "enojado"},       # etiqueta inválida
    ]})
    assert interpretar(resp, 3) == ["neutro", "negativo", None]


def test_interpretar_json_con_texto_alrededor():
    assert interpretar('Acá va: {"resultados": [{"id": 1, "sentimiento": "positivo"}]}', 1) == ["positivo"]


def test_clasificar_usa_el_modelo_de_respaldo_si_el_primero_falla():
    llamados = []

    def llamar(modelo, mensajes):
        llamados.append(modelo)
        if modelo == "principal":
            raise RuntimeError("caído")
        n = mensajes[1]["content"].count("\n\n[")
        return json.dumps({"resultados": [{"id": i, "sentimiento": "negativo"} for i in range(1, n + 1)]})

    etiquetas, usados = clasificar(["a", "b", "c"], llamar, lote=2, modelos=["principal", "respaldo"])
    assert etiquetas == ["negativo"] * 3
    assert usados == ["respaldo"] * 3
    assert llamados == ["principal", "respaldo", "principal", "respaldo"]
