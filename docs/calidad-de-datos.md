# Calidad de datos

Hay tres barreras. Un dato tiene que pasar las tres para llegar al tablero.

## 1. Tests de código (`tests/test_bluesky.py`, `test_almacen.py`, `test_nlp.py`)
Prueban la lógica con casos controlados: que el día argentino empiece a las 03:00 UTC, que
una ventana llena se parta, que no se guarden datos del autor, que las menciones se enmascaren,
que el filtro de texto útil funcione, que las etiquetas del modelo se traduzcan bien.

## 2. Tests de datos (`tests/test_datos.py`), en CI con cada push
Validan los **archivos reales** del repo:

| Control | Por qué importa |
|---|---|
| Columnas esperadas en cada Parquet | Un cambio de formato rompería la carga |
| `post_id` único por archivo | Duplicados inflarían los porcentajes |
| Fechas dentro de la semana del archivo | Detecta errores de zona horaria |
| Temas válidos según la configuración | Un tema sin definir no aparecería en el tablero |
| Ningún handle ni DID en el texto | Regla de privacidad |
| Interacciones no negativas | Datos corruptos |
| El registro tiene todos los términos para cada día | Un día incompleto bajaría artificialmente el volumen |
| El análisis corresponde a posts existentes y sus probabilidades suman 1 | Coherencia entre capas |

## 3. Controles en la base (`src/opinion_publica/controles.py`), después de cada carga

| Control | Nivel |
|---|---|
| Posts sin tema | Bloqueante |
| Probabilidades de sentimiento o emoción que no suman 1 | Bloqueante |
| Handles o DIDs en el texto | Bloqueante |
| Días sin consultas dentro del período | Bloqueante |
| Consultas truncadas (puede faltar volumen) | Advertencia |
| Posts sin análisis | Advertencia |

Un control **bloqueante** hace fallar el workflow y queda registrado en `etl_corrida` con estado `error`.

## Además, en la base
- Restricciones `CHECK` en el esquema: probabilidades entre 0 y 1, etiquetas válidas,
  interacciones no negativas, y `texto_util` coherente con que haya sentimiento.
- Claves foráneas entre todas las tablas.
- El CI hace **dos cargas seguidas** en un PostgreSQL de prueba para comprobar que la carga es idempotente.
