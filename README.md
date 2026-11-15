# opinion-publica-nlp — Termómetro de descontento

> 🚧 En construcción. Etapa actual: recolección de datos.

De qué se queja la gente, dónde y con qué tono, a partir de fuentes públicas, legales y gratuitas.

## Fuentes

| Fuente | Qué aporta | Estado |
|---|---|---|
| Bluesky (API pública de búsqueda) | Texto en castellano por tema: sentimiento, emociones y motivo de la queja | Recolección semanal |
| Defensa del Consumidor (Nación) | Reclamos por empresa | Pendiente |
| Reclamos 147 / BA Colaborativa (CABA) | Reclamos por comuna y tema | Pendiente |

## Recolección de Bluesky

- Los términos están en [`config/terminos.yaml`](config/terminos.yaml), agrupados por tema.
- Se hace una búsqueda por término y por día (hora argentina). Si una ventana devuelve el máximo de 100 posts, se parte en mitades hasta llegar a ventanas de una hora; si aun así viene llena, queda marcada como `truncada` en el registro.
- Los datos quedan en `data/bluesky/AAAA-Www.parquet` (una semana ISO por archivo) y el detalle de cada consulta en `data/bluesky/registro/`.
- **GitHub Actions:** `recoleccion-semanal.yml` corre los lunes y trae la semana anterior; `historico.yml` se lanza a mano con un rango de fechas.

```bash
pip install -e ".[dev]"
python scripts/recolectar_bluesky.py --semana-anterior
python scripts/recolectar_bluesky.py --desde 2025-01-01 --hasta 2025-03-31
pytest
```

## Privacidad

- No se guardan handles, DIDs, nombres ni la URI del post. El id es un hash de la URI y sirve solo para evitar duplicados.
- Las menciones y los enlaces a perfiles dentro del texto se enmascaran.
- Los resultados se publican solo agregados por tema; no se perfila a ninguna persona.

## Alcance

Bluesky no representa a toda la población argentina: es un complemento, no una encuesta. El proyecto no mide intención de voto (Ley 26.215).
