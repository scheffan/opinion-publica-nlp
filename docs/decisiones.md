# Registro de decisiones

Cada decisión importante, con las alternativas que se descartaron y por qué.

| # | Decisión | Alternativas | Motivo |
|---|---|---|---|
| 1 | **Bluesky** como fuente de texto | X, YouTube, Reddit | Es la única red grande con API pública sin autenticación y sin violar términos de uso |
| 2 | **Ventanas adaptativas** por día | Paginar con `cursor` | Sin autenticación el cursor da 403 desde la segunda página |
| 3 | **Parquet por semana** en el repo como capa cruda | CSV, un archivo único, base como única fuente | Compacto, tipado, versionado en git; reescribir una semana no infla el historial |
| 4 | **Hash de la URI** como id | Guardar la URI o el handle | Permite deduplicar sin poder volver al autor |
| 5 | **pysentimiento** (RoBERTuito) | Modelos multilingües, LLM | Entrenado con tuits en castellano; corre gratis en CPU |
| 6 | **PostgreSQL** | DuckDB, SQLite | Grafana Cloud tiene conector nativo; es el estándar en la industria |
| 7 | **Neon** (plan gratuito) | Supabase | Sin vencimiento ni tarjeta, 1 GB por proyecto, se apaga solo cuando no se usa |
| 8 | **Modelo estrella** con dimensiones compartidas | Una tabla plana por fuente | Permite cruzar las tres fuentes por fecha y tema |
| 9 | **Métricas en vistas SQL** | Calcular en Grafana | Reproducibles, versionadas y testeables |
| 10 | **Recarga completa idempotente** | Carga incremental por diferencias | Tarda ~5 s; más simple y no puede desincronizarse |
| 11 | **Intervalo de Wilson** | Intervalo normal (Wald) | Funciona bien con muestras chicas |
| 12 | Reclamos 147 y Defensa del Consumidor **agregados** en la base | Cargar crudos | Los crudos superan 1 GB; el agregado alcanza para el mapa y las tendencias |

## Licencias a tener en cuenta
- **pysentimiento**: la librería es de código abierto, pero sus modelos se entrenaron con
  datasets de terceros "sujetos a sus respectivas licencias, muchas de ellas de uso no comercial"
  (según su documentación). Para un uso comercial del proyecto habría que reemplazar los modelos.
- **Datos de Bluesky**: se usan solo agregados y sin datos de autor.
- **BA Data y datos.gob.ar**: datos abiertos del Estado.
