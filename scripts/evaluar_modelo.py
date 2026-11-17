"""Compara las etiquetas hechas a mano con las predicciones del modelo.

Entradas:
    data/etiquetado/etiquetas.csv   (post_id, tema, sentimiento, emocion, ironia, etiquetado)
    data/procesado/analisis/*.parquet
Salida:
    docs/validacion.md  (exactitud, F1 por clase, matriz de confusión, ironía, por tema)

Los posts marcados como "saltear" no cuentan.

Uso:
    python scripts/evaluar_modelo.py
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from opinion_publica.evaluacion import CLASES, resumen


def tabla_md(df: pd.DataFrame, decimales: int = 2) -> str:
    cols = [df.index.name or ""] + [str(c) for c in df.columns]
    filas = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for idx, fila in df.astype(object).iterrows():
        valores = [f"{v:.{decimales}f}" if isinstance(v, float) else str(v) for v in fila]
        filas.append("| " + " | ".join([str(idx)] + valores) + " |")
    return "\n".join(filas)


def fila_comparacion(nombre: str, real: pd.Series, predicho: pd.Series) -> dict:
    r = resumen(real, predicho)
    fila = {"modelo": nombre, "exactitud": r["exactitud"]}
    fila.update({f"F1 {c}": r["por_clase"].loc[c, "f1"] for c in CLASES})
    fila["F1 macro"] = r["f1_macro"]
    return fila


def seccion_llm(datos: pd.DataFrame, ruta: Path) -> str:
    """Compara pysentimiento con el modelo de lenguaje sobre los mismos posts."""
    if not ruta.exists():
        return ""
    llm = pd.read_csv(ruta).rename(columns={"sentimiento": "llm_sent", "modelo": "llm_modelo"})
    comun = datos.merge(llm, on="post_id").dropna(subset=["llm_sent"])
    tabla = pd.DataFrame([
        fila_comparacion("pysentimiento", comun.sentimiento, comun.modelo_sent),
        fila_comparacion(f"LLM ({comun.llm_modelo.mode().iloc[0]})", comun.sentimiento, comun.llm_sent),
    ]).set_index("modelo")
    r = resumen(comun.sentimiento, comun.llm_sent)
    reparto = comun.llm_sent.value_counts(normalize=True).reindex(CLASES).fillna(0.0)
    return f"""## Comparación con un modelo de lenguaje

Los mismos {len(comun)} posts, clasificados por un modelo de lenguaje de Groq con los mismos
criterios que se usaron para etiquetar a mano (ver [`src/opinion_publica/llm.py`](../src/opinion_publica/llm.py)).

{tabla_md(tabla)}

Matriz de confusión del modelo de lenguaje (filas: etiqueta a mano, columnas: modelo):

{tabla_md(r['matriz'], 0)}

Reparto que predice el modelo de lenguaje: negativo {reparto['negativo']:.0%},
neutro {reparto['neutro']:.0%}, positivo {reparto['positivo']:.0%}.

"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--etiquetas", type=Path, default=Path("data/etiquetado/etiquetas.csv"))
    parser.add_argument("--analisis", type=Path, default=Path("data/procesado/analisis"))
    parser.add_argument("--llm", type=Path, default=Path("data/etiquetado/predicciones_llm.csv"))
    parser.add_argument("--salida", type=Path, default=Path("docs/validacion.md"))
    args = parser.parse_args()

    etiquetas = pd.read_csv(args.etiquetas)
    salteados = int((etiquetas.sentimiento == "saltear").sum())
    etiquetas = etiquetas[etiquetas.sentimiento.isin(CLASES)]
    analisis = pd.concat([pd.read_parquet(a, columns=["post_id", "sentimiento", "modelo"])
                          for a in sorted(args.analisis.glob("*.parquet"))])
    datos = etiquetas.merge(analisis.rename(columns={"sentimiento": "modelo_sent"}), on="post_id", how="inner")

    r = resumen(datos.sentimiento, datos.modelo_sent)
    ironicos = datos[datos.ironia.astype(str).str.lower() == "true"]
    acierto_ironia = (ironicos.sentimiento == ironicos.modelo_sent).mean() if len(ironicos) else float("nan")
    por_tema = (datos.assign(acierto=datos.sentimiento == datos.modelo_sent)
                .groupby("tema").agg(casos=("acierto", "size"), exactitud=("acierto", "mean")))
    reparto = pd.DataFrame({
        "a mano": datos.sentimiento.value_counts(normalize=True),
        "modelo": datos.modelo_sent.value_counts(normalize=True),
    }).reindex(CLASES).fillna(0.0)
    reparto.index.name = "clase"

    texto = f"""# Validación del modelo de sentimiento

Comparación entre las etiquetas hechas a mano por una persona, sin ver la predicción, y las
predicciones de `{datos.modelo.iloc[0]}`, sobre una muestra estratificada por tema
(ver [`scripts/muestra_etiquetado.py`](../scripts/muestra_etiquetado.py)).

- Posts evaluados: **{r['casos']}** ({salteados} salteados por no entenderse o no ser pertinentes)
- Exactitud: **{r['exactitud']:.1%}**
- F1 macro (promedio simple de las tres clases): **{r['f1_macro']:.2f}**
- Posts irónicos: {len(ironicos)}; el modelo acertó en {acierto_ironia:.0%} de ellos

## Métricas por clase

{tabla_md(r['por_clase'])}

## Matriz de confusión

Filas: etiqueta a mano. Columnas: predicción del modelo.

{tabla_md(r['matriz'], 0)}

## Reparto de clases

{tabla_md(reparto)}

## Exactitud por tema

{tabla_md(por_tema)}

{seccion_llm(datos, args.llm)}
_Generado el {date.today().isoformat()} con `python scripts/evaluar_modelo.py`._
"""
    args.salida.write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
