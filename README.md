# opinion-publica-nlp — Termómetro de descontento

> 🚧 En construcción. Etapa actual: análisis de texto y base de datos de Bluesky.

De qué se queja la gente, dónde y con qué tono, a partir de fuentes públicas, legales y gratuitas.

**Stack:** Python · pandas · pysentimiento (NLP en castellano) · PostgreSQL (Neon) · SQL · GitHub Actions · Grafana

## Fuentes

| Fuente | Qué aporta | Estado |
|---|---|---|
| Bluesky (API pública de búsqueda) | Texto libre: sentimiento, emociones y discurso de odio por tema | Recolección semanal desde ene-2025 · análisis en curso |
| Defensa del Consumidor (Nación) | Denuncias por empresa y rubro | Pendiente |
| Reclamos 147 / BA Colaborativa (CABA) | Reclamos por comuna y tipo | Pendiente |

## Cómo funciona

```
API de Bluesky ──► Parquet crudo ──► análisis de texto ──► PostgreSQL ──► Grafana
   (lunes)          (en el repo)      (pysentimiento)      (modelo estrella + vistas)
```

Todo corre solo en GitHub Actions: recolección los lunes, análisis y carga a continuación,
y en cada push tests de código, tests de datos y una carga completa en un PostgreSQL de prueba.

## Documentación

| Documento | Contenido |
|---|---|
| [Arquitectura](docs/arquitectura.md) | Capas, flujo y automatización |
| [ETL paso a paso](docs/etl.md) | Extracción, limpieza, análisis y carga |
| [Modelo de datos](docs/modelo-de-datos.md) | Diagrama de tablas, diccionario de datos y vistas |
| [Metodología](docs/metodologia.md) | Sesgos, métricas e intervalos de confianza |
| [Calidad de datos](docs/calidad-de-datos.md) | Tests y controles |
| [Decisiones](docs/decisiones.md) | Qué se eligió, qué se descartó y por qué |

## Uso rápido

```bash
pip install -e ".[dev]"
python scripts/recolectar_bluesky.py --semana-anterior
DATABASE_URL=postgresql://... python scripts/cargar_bd.py
pytest
```

Para el análisis de texto ver [docs/etl.md](docs/etl.md#cómo-correr-todo-en-local).

## Privacidad

- No se guardan handles, DIDs, nombres ni la URI del post. El id es un hash de la URI y sirve solo para evitar duplicados.
- Las menciones y los enlaces a perfiles dentro del texto se enmascaran.
- Los resultados se publican solo agregados por tema; no se perfila a ninguna persona.

## Alcance

Bluesky no representa a toda la población argentina: es un complemento, no una encuesta.
El proyecto no mide intención de voto (Ley 26.215). Más detalle en [Metodología](docs/metodologia.md).
