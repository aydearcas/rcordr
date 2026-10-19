"""Empaqueta rcordr para enviarlo: ejecutable portable + manual PDF en un .zip.

Uso (con el entorno de compilación, ver requirements-build.in):
    uv venv .venv-build --python 3.13 --python-preference only-managed
    uv pip install --python .venv-build/Scripts/python.exe --require-hashes \\
        -r scripts/requirements-build.txt
    .venv-build/Scripts/python.exe scripts/empaquetar.py

Resultado: dist/rcordr-<versión>-windows.zip con la carpeta rcordr/
(rcordr.exe, _internal/ y el manual).
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"
sys.path.insert(0, str(ROOT))

from rcordr import __version__  # noqa: E402

MANUAL_NAME = "Manual de instrucciones - rcordr.pdf"


def build_exe() -> Path:
    """Carpeta portable con rcordr.exe (PyInstaller, modo carpeta: arranca rápido
    y los antivirus lo marcan menos que un único .exe autoextraíble)."""
    subprocess.run([
        sys.executable, "-m", "PyInstaller", str(ROOT / "rcordr.pyw"),
        "--name", "rcordr", "--windowed", "--noconfirm", "--clean",
        "--icon", str(ROOT / "assets" / "rcordr.ico"),
        "--distpath", str(BUILD / "dist"), "--workpath", str(BUILD / "work"),
        "--specpath", str(BUILD),
        "--collect-data", "imageio_ffmpeg",     # el ffmpeg incluido
        "--hidden-import", "pystray._win32",     # backend de la bandeja en Windows
    ], check=True)
    return BUILD / "dist" / "rcordr"


def build_manual() -> Path:
    from manual import build  # scripts/manual.py
    return build(BUILD / MANUAL_NAME)


def make_zip(app_dir: Path) -> Path:
    DIST.mkdir(exist_ok=True)
    out = DIST / f"rcordr-{__version__}-windows.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(app_dir.rglob("*")):
            if f.is_file():
                z.write(f, Path("rcordr") / f.relative_to(app_dir))
    return out


def main():
    args = set(sys.argv[1:])
    sys.path.insert(0, str(Path(__file__).parent))
    if "--solo-manual" in args:
        print(build_manual())
        return
    app_dir = build_exe()
    if "--solo-exe" in args:
        print(app_dir)
        return
    shutil.copy(build_manual(), app_dir / MANUAL_NAME)  # junto a rcordr.exe
    out = make_zip(app_dir)
    print(f"{out}  ({out.stat().st_size / 1_048_576:.0f} MB)")


if __name__ == "__main__":
    main()
