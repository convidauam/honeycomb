from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()

def which(cmd: str) -> str | None:
    return shutil.which(cmd)

def run(cmd: list[str]) -> int:
    table = Table(box=box.SIMPLE, show_header=False, padding=(0,1))
    table.add_row("Comando", Text(" ".join(cmd), style="bold"))
    console.print(table)
    console.print()

    try:
        return subprocess.call(cmd, env=os.environ.copy())
    except FileNotFoundError:
        return 127

def main():
    parser = argparse.ArgumentParser(
        prog="dev.py",
        description="Lanza el servidor Pyramid usando uv si está disponible."
    )
    parser.add_argument(
        "ini",
        nargs="?",
        default="development.ini",
        help="Ruta al archivo .ini (por defecto: development.ini)"
    )
    # Captura cualquier flag extra y pásalo tal cual a pserve
    args, passthrough = parser.parse_known_args()

    ini_path = Path(args.ini)
    if not ini_path.exists():
        console.print(Panel.fit(
            Text(f"No encontré el archivo {ini_path!s}", style="bold red"),
            title="Error", border_style="red"
        ))
        sys.exit(2)

    console.print(Panel(
        Text("Launcher de desarrollo para Pyramid", justify="center", style="bold"),
        title="🚀 mise dev", border_style="cyan"
    ))

    # Mostrar contexto útil
    info = Table(box=box.MINIMAL_DOUBLE_HEAD, show_header=False, pad_edge=False)
    info.add_row("Proyecto", Text(Path.cwd().name, style="green"))
    info.add_row("INI", Text(str(ini_path), style="green"))
    py_exec = sys.executable or "python"
    info.add_row("Python", Text(py_exec, style="green"))
    console.print(info)
    console.print()

    # 1) Intento con uv
    uv = which("uv")
    if uv:
        console.print(Panel.fit(
            Text("Intentando con uv... (uv run pserve)", style="bold cyan"),
            border_style="cyan"
        ))
        cmd = [uv, "run", "pserve", str(ini_path)] + passthrough
        code = run(cmd)
        if code == 0:
            sys.exit(0)

    if code in (0, 127):
        sys.exit(code)

    # Si falló, damos hints
    tips = Table(box=box.SIMPLE_HEAVY, show_header=False, padding=(0,1))
    tips.add_row("💡 Tip", "Asegúrate de tener instalado uv.")
    tips.add_row("", "Con uv:  uv sync --package honeycomb || mise setup")
    tips.add_row("💡 Tip 2", "Verifica tu archivo INI y el puerto libre.")
    console.print(Panel(tips, title="Fallo al lanzar el servidor", border_style="red"))
    sys.exit(code)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(1)