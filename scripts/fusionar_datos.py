"""Fusiona los datos recién recolectados con los que ya están en el repo.

Git no puede mezclar dos Parquet: si dos corridas tocaron la misma semana
(por ejemplo, una semana que cruza el cambio de año), el rebase da conflicto.
Este script une archivo por archivo sin duplicar posts ni consultas.

Uso: python scripts/fusionar_datos.py ORIGEN DESTINO
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from opinion_publica.almacen import guardar_registro, guardar_semana


def main(origen: Path, destino: Path) -> None:
    for archivo in sorted(origen.glob("*.parquet")):
        nuevas = pd.read_parquet(archivo)
        nuevas["temas"] = nuevas["temas"].map(list)
        nuevas["terminos"] = nuevas["terminos"].map(list)
        total = guardar_semana(nuevas, destino / archivo.name)
        print(f"{archivo.name}: {total} posts")
    for archivo in sorted((origen / "registro").glob("*.csv")):
        guardar_registro(pd.read_csv(archivo).to_dict("records"), destino / "registro" / archivo.name)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
