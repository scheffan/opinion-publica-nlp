from datetime import date, datetime, timedelta, timezone

import pytest

from opinion_publica.bluesky import LIMITE, buscar_ventana, dia_en_utc, dias, iso_utc


def test_dia_argentino_empieza_a_las_3_utc():
    inicio, fin = dia_en_utc(date(2026, 11, 10))
    assert iso_utc(inicio) == "2026-11-10T03:00:00Z"
    assert iso_utc(fin) == "2026-11-11T03:00:00Z"


def test_dias_incluye_extremos():
    assert dias(date(2026, 1, 30), date(2026, 2, 2)) == [
        date(2026, 1, 30), date(2026, 1, 31), date(2026, 2, 1), date(2026, 2, 2)
    ]
    with pytest.raises(ValueError):
        dias(date(2026, 2, 2), date(2026, 1, 1))


def _buscador_con_volumen(posts_por_hora: int):
    """Simula la API: devuelve como mucho LIMITE posts por ventana."""
    llamadas = []

    def buscar(consulta, desde, hasta):
        llamadas.append((desde, hasta))
        horas = (hasta - desde) / timedelta(hours=1)
        n = min(int(posts_por_hora * horas), LIMITE)
        return [{"uri": f"{desde.isoformat()}-{i}"} for i in range(n)]

    return buscar, llamadas


def test_ventana_con_poco_volumen_no_se_parte():
    buscar, llamadas = _buscador_con_volumen(posts_por_hora=2)
    inicio, fin = dia_en_utc(date(2026, 11, 10))
    res = buscar_ventana(buscar, "subte", inicio, fin)
    assert len(llamadas) == 1
    assert len(res.posts) == 48
    assert not res.truncada


def test_ventana_llena_se_parte_hasta_bajar_del_tope():
    buscar, llamadas = _buscador_con_volumen(posts_por_hora=6)  # 144 por día
    inicio, fin = dia_en_utc(date(2026, 11, 10))
    res = buscar_ventana(buscar, "milei", inicio, fin)
    assert len(res.posts) == 144
    assert res.ventanas == 2
    assert len(llamadas) == 3  # el día entero + dos mitades
    assert not res.truncada


def test_ventana_minima_llena_queda_marcada_como_truncada():
    buscar, _ = _buscador_con_volumen(posts_por_hora=500)
    inicio = datetime(2026, 11, 10, 3, tzinfo=timezone.utc)
    res = buscar_ventana(buscar, "milei", inicio, inicio + timedelta(hours=2))
    assert res.truncada
    assert res.ventanas == 2
