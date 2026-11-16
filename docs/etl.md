# ETL paso a paso

## 1. Extracción: recolección de Bluesky

**Script:** `scripts/recolectar_bluesky.py` · **Workflow:** `recoleccion-semanal.yml`, `historico.yml`

1. Lee los términos de `config/terminos.yaml` (19 términos en 9 temas).
2. Para cada día (en hora argentina) y cada término, consulta
   `app.bsky.feed.searchPosts` con `lang=es`, `limit=100` y la ventana `since`/`until` de ese día.
3. **Ventanas adaptativas.** Sin autenticación la API no deja pasar a la segunda página
   (da 403 con `cursor`). Si una ventana devuelve 100 posts (el tope), puede haber más:
   se parte en dos mitades y se repite, hasta ventanas de 1 hora. Si una ventana de 1 hora
   sigue llena, se marca `truncada` en el registro (hasta ahora no pasó nunca).
4. Reintenta ante errores 429 y 5xx con espera creciente (2, 4, 8 s).
5. Anota cada consulta en `data/bluesky/registro/AAAA-Www.csv`: fecha, término, posts, ventanas, truncada.

## 2. Transformación A: limpieza y privacidad

**Módulo:** `src/opinion_publica/almacen.py`

| Campo de la API | Qué se hace |
|---|---|
| `author` (handle, DID, nombre, avatar) | **Se descarta** |
| `uri` (contiene el DID) | Se reemplaza por `post_id` = primeros 20 caracteres del SHA-256 |
| `record.text` | Se enmascaran menciones (`@alguien.bsky.social` → `@usuario`) y links a perfiles |
| `record.createdAt`, `indexedAt`, `langs` | Se guardan |
| `likeCount`, `repostCount`, `replyCount`, `quoteCount` | Se guardan (valor al momento de recolectar) |
| `record.reply` | Se convierte en `es_respuesta` (sí/no) |

Si un post aparece en varios términos, queda **una sola fila** con la lista de temas.
Los datos se guardan en `data/bluesky/AAAA-Www.parquet` (una semana ISO por archivo);
volver a correr una semana la reescribe sin duplicar.

## 3. Transformación B: análisis de texto

**Script:** `scripts/analizar_sentimiento.py` · **Módulo:** `nlp.py` · **Workflow:** `procesar.yml`

1. **Filtro de texto útil.** Se sacan links y menciones; si quedan menos de dos palabras
   (por ejemplo, un post que es solo un link o un emoji), el post se marca `texto_util = false`
   y no pasa por los modelos. Esos posts cuentan para el volumen, no para el sentimiento.
2. **Tres modelos de pysentimiento** (RoBERTuito, entrenado con tuits en castellano):
   - Sentimiento: positivo / neutro / negativo, con probabilidad de cada uno.
   - Emoción: alegría, tristeza, enojo, miedo, asco, sorpresa u otra.
   - Discurso de odio: odio sí/no, y probabilidad de que sea agresivo o dirigido a alguien.
3. **Incremental.** Solo se procesan posts sin análisis, o analizados con otra versión del
   modelo (columna `modelo`). Si se actualiza pysentimiento, se recalcula todo solo.
4. **Presupuesto de tiempo.** Con `--minutos` corta antes del límite de GitHub Actions y
   guarda lo hecho; el histórico se completa en varias corridas. Empieza por lo más reciente.
5. Resultado en `data/procesado/analisis/AAAA-Www.parquet`.

## 4. Carga: PostgreSQL

**Script:** `scripts/cargar_bd.py` · **Módulo:** `carga.py`

1. Aplica `sql/01_esquema.sql` y `sql/02_vistas.sql` (idempotentes: `IF NOT EXISTS`, `OR REPLACE`).
2. Registra el inicio en `etl_corrida`, con el link a la corrida de Actions.
3. En **una sola transacción**, para cada tabla: `COPY` a una tabla temporal y luego
   `INSERT … ON CONFLICT DO UPDATE` (upsert). Si algo falla, no queda nada a medias.
4. Corre los controles de calidad (ver [calidad-de-datos.md](calidad-de-datos.md)).
5. Cierra la corrida en `etl_corrida` con estado, filas por tabla y resultado de los controles.

La carga completa de unos 90.000 posts tarda alrededor de 5 segundos. Por eso se recarga
todo en cada corrida en lugar de calcular diferencias: es más simple y no puede desincronizarse.

## Cómo correr todo en local

```bash
pip install -e ".[dev]"                       # recolección, carga y tests
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[nlp]"                       # análisis de texto

python scripts/recolectar_bluesky.py --semana-anterior
python scripts/analizar_sentimiento.py --minutos 30
DATABASE_URL=postgresql://... python scripts/cargar_bd.py
pytest
```
