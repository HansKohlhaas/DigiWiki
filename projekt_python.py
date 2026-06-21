"""Projekt-Interpreter: Skripte laufen in .venv, wenn vorhanden.

Fuer geplante Tasks (Task Scheduler), IDE-Start oder `python skript.py`
ohne .bat — kein Versions-Check, nur Vergleich sys.executable vs. .venv.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def venv_python() -> Path:
    return BASE_DIR / ".venv" / "Scripts" / "python.exe"


def lauft_in_projekt_venv() -> bool:
    py = venv_python()
    if not py.exists():
        return True
    try:
        return Path(sys.executable).resolve() == py.resolve()
    except OSError:
        return False


def ensure_venv(script: Path) -> None:
    """Startet script neu mit .venv-Python, falls noetig."""
    py = venv_python()
    if not py.exists() or lauft_in_projekt_venv():
        return
    script = script.resolve()
    cmd = [str(py), str(script), *sys.argv[1:]]
    print(f"Starte mit Projekt-Python: {py}")
    raise SystemExit(subprocess.call(cmd))
