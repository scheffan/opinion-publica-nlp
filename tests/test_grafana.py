"""El tablero de Grafana está al día y solo usa vistas que el usuario de lectura puede leer."""

import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_json_generado_esta_al_dia(tmp_path):
    actual = (RAIZ / "grafana/bluesky.json").read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(RAIZ / "grafana/generar_bluesky.py")], check=True, capture_output=True)
    assert (RAIZ / "grafana/bluesky.json").read_text(encoding="utf-8") == actual, \
        "Corré python grafana/generar_bluesky.py y commiteá bluesky.json"


def test_consultas_solo_usan_vistas_con_permiso():
    permisos = (RAIZ / "sql/03_permisos.sql").read_text(encoding="utf-8")
    permitidas = set(re.findall(r"opinion\.(v_\w+)", permisos))
    tablero = json.loads((RAIZ / "grafana/bluesky.json").read_text(encoding="utf-8"))
    usadas = {v for p in tablero["panels"] for t in p.get("targets", [])
              for v in re.findall(r"FROM\s+(\w+)", t["rawSql"])}
    assert usadas, "el tablero no tiene consultas"
    assert usadas <= permitidas, f"vistas sin permiso para grafana_lector: {usadas - permitidas}"
