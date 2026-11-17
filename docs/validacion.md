# Validación del modelo de sentimiento

Comparación entre las etiquetas hechas a mano por una persona, sin ver la predicción, y las
predicciones de `pysentimiento-0.7.3`, sobre una muestra estratificada por tema
(ver [`scripts/muestra_etiquetado.py`](../scripts/muestra_etiquetado.py)).

- Posts evaluados: **182** (16 salteados por no entenderse o no ser pertinentes)
- Exactitud: **71.4%**
- F1 macro (promedio simple de las tres clases): **0.50**
- Posts irónicos: 41; el modelo acertó en 68% de ellos

## Métricas por clase

| clase | precision | recall | f1 | casos |
|---|---|---|---|---|
| negativo | 0.88 | 0.79 | 0.83 | 124 |
| neutro | 0.48 | 0.72 | 0.58 | 43 |
| positivo | 0.17 | 0.07 | 0.10 | 15 |

## Matriz de confusión

Filas: etiqueta a mano. Columnas: predicción del modelo.

| real | negativo | neutro | positivo |
|---|---|---|---|
| negativo | 98 | 22 | 4 |
| neutro | 11 | 31 | 1 |
| positivo | 3 | 11 | 1 |

## Reparto de clases

| clase | a mano | modelo |
|---|---|---|
| negativo | 0.68 | 0.62 |
| neutro | 0.24 | 0.35 |
| positivo | 0.08 | 0.03 |

## Exactitud por tema

| tema | casos | exactitud |
|---|---|---|
| anses | 22 | 0.91 |
| aysa | 19 | 0.79 |
| jorge_macri | 20 | 0.80 |
| kicillof | 18 | 0.50 |
| milei | 21 | 0.76 |
| pami | 21 | 0.62 |
| peyorativos | 21 | 0.71 |
| servicios_publicos | 20 | 0.65 |
| subte | 20 | 0.65 |

## Comparación con un modelo de lenguaje

Los mismos 182 posts, clasificados por un modelo de lenguaje de Groq con los mismos
criterios que se usaron para etiquetar a mano (ver [`src/opinion_publica/llm.py`](../src/opinion_publica/llm.py)).

| modelo | exactitud | F1 negativo | F1 neutro | F1 positivo | F1 macro |
|---|---|---|---|---|---|
| pysentimiento | 0.71 | 0.83 | 0.58 | 0.10 | 0.50 |
| LLM (openai/gpt-oss-120b) | 0.79 | 0.89 | 0.69 | 0.24 | 0.60 |

Matriz de confusión del modelo de lenguaje (filas: etiqueta a mano, columnas: modelo):

| real | negativo | neutro | positivo |
|---|---|---|---|
| negativo | 109 | 10 | 5 |
| neutro | 9 | 32 | 2 |
| positivo | 4 | 8 | 3 |

Reparto que predice el modelo de lenguaje: negativo 67%,
neutro 27%, positivo 5%.


_Generado el 2026-11-17 con `python scripts/evaluar_modelo.py`._
