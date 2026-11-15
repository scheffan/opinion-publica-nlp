from datetime import date, datetime, timezone

import pandas as pd

from opinion_publica.almacen import (
    anonimizar_texto, consolidar, guardar_semana, hash_uri, limpiar_post, semana_iso,
)

AHORA = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)


def _post(uri="at://did:plc:abc123/app.bsky.feed.post/xyz", texto="hola", **extra):
    return {
        "uri": uri,
        "author": {"did": "did:plc:abc123", "handle": "alguien.bsky.social", "displayName": "Alguien"},
        "record": {"text": texto, "createdAt": "2026-11-10T12:00:00.000Z", "langs": ["es"], **extra},
        "indexedAt": "2026-11-10T12:00:01.000Z",
        "likeCount": 3, "repostCount": 1, "replyCount": 0, "quoteCount": 0,
    }


def test_no_guarda_datos_del_autor():
    fila = limpiar_post(_post(), "subte", "subte", date(2026, 11, 10), AHORA)
    serializado = str(fila)
    assert "abc123" not in serializado
    assert "alguien" not in serializado.lower()
    assert fila["post_id"] == hash_uri("at://did:plc:abc123/app.bsky.feed.post/xyz")


def test_enmascara_menciones_y_perfiles_pero_no_mails():
    texto = "@juan.bsky.social mirá https://bsky.app/profile/ana.com/post/1 y escribí a info@aysa.com.ar"
    limpio = anonimizar_texto(texto)
    assert "juan" not in limpio and "ana.com" not in limpio
    assert limpio.startswith("@usuario mirá")
    assert "bsky.app/profile/<usuario>/post/1" in limpio
    assert "info@aysa.com.ar" in limpio


def test_detecta_respuestas():
    fila = limpiar_post(_post(reply={"parent": {}}), "pami", "pami", date(2026, 11, 10), AHORA)
    assert fila["es_respuesta"] is True


def test_consolidar_une_temas_de_un_mismo_post():
    dia = date(2026, 11, 10)
    filas = [
        limpiar_post(_post(), "milei", "milei", dia, AHORA),
        limpiar_post(_post(), "peyorativos", "kuka", dia, AHORA),
        limpiar_post(_post(uri="at://otro"), "subte", "subte", dia, AHORA),
    ]
    df = consolidar(filas)
    assert len(df) == 2
    fila = df[df.post_id == hash_uri("at://did:plc:abc123/app.bsky.feed.post/xyz")].iloc[0]
    assert fila.temas == ["milei", "peyorativos"]
    assert fila.terminos == ["kuka", "milei"]


def test_guardar_semana_dos_veces_no_duplica(tmp_path):
    dia = date(2026, 11, 10)
    ruta = tmp_path / f"{semana_iso(dia)}.parquet"
    filas = consolidar([limpiar_post(_post(), "milei", "milei", dia, AHORA)])
    assert guardar_semana(filas, ruta) == 1
    otra = consolidar([limpiar_post(_post(), "peyorativos", "kuka", dia, AHORA)])
    assert guardar_semana(otra, ruta) == 1
    leido = pd.read_parquet(ruta)
    assert list(leido.iloc[0].temas) == ["milei", "peyorativos"]


def test_semana_iso():
    assert semana_iso(date(2026, 11, 16)) == "2026-W47"
    assert semana_iso(date(2027, 1, 1)) == "2026-W53"
