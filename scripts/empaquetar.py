"""Empaqueta rcordr para enviarlo: ejecutable portable + manual PDF en un .zip.

Uso (con el entorno de compilación, ver requirements-build.in):
    uv venv .venv-build --python 3.13 --python-preference only-managed
    uv pip install --python .venv-build/Scripts/python.exe --require-hashes \\
        -r scripts/requirements-build.txt
    .venv-build/Scripts/python.exe scripts/empaquetar.py

Resultado: dist/rcordr-<versión>-windows.zip con la carpeta rcordr/
(rcordr.exe, _internal/ y el manual).
"""

import re
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


LICENSED_DISTS = ["imageio-ffmpeg", "PyAudioWPatch", "pillow", "mss", "pystray", "six"]


def collect_licenses(app_dir: Path) -> Path:
    """Carpeta licencias/: GPLv3 de rcordr (y de FFmpeg), avisos de terceros y el
    texto de licencia de cada componente incluido, sacado de su propio paquete."""
    import importlib.metadata as md

    dest = app_dir / "licencias"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir()
    shutil.copy(ROOT / "LICENSE", dest / "rcordr y FFmpeg - GPL-3.0.txt")
    shutil.copy(ROOT / "THIRD_PARTY_NOTICES.md", dest / "LÉAME - componentes de terceros.txt")
    for name in LICENSED_DISTS:
        for f in md.distribution(name).files or []:
            fname = Path(str(f)).name
            if re.match(r"(LICEN[CS]E|COPYING)", fname, re.I):
                # .txt para que se abran con doble clic (p. ej. COPYING.LGPL)
                txt = "" if Path(fname).suffix.lower() in (".txt", ".md", ".rst") else ".txt"
                target = f"{name} - {fname}{txt}"
                shutil.copy(f.locate(), dest / target)
    # Apache-2.0 completo (PyAudioWPatch y OpenSSL solo lo citan): el de `packaging`
    apache = next(Path(str(f.locate())) for f in md.distribution("packaging").files
                  if Path(str(f)).name == "LICENSE.APACHE")
    shutil.copy(apache, dest / "Apache-2.0.txt")
    shutil.copy(Path(sys.base_prefix) / "LICENSE.txt", dest / "Python - LICENSE.txt")
    tk_terms = app_dir / "_internal" / "_tk_data" / "license.terms"
    if tk_terms.exists():
        shutil.copy(tk_terms, dest / "Tcl-Tk - license.terms.txt")
    return dest


def export_docs(manual: Path) -> None:
    """docs/: el manual en PDF y dos páginas en PNG para el README de GitHub."""
    import pypdfium2 as pdfium

    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    shutil.copy(manual, docs / "manual.pdf")
    pdf = pdfium.PdfDocument(str(manual))
    pages = {"manual-portada.png": 0}
    for i in range(len(pdf)):
        if "EDITOR DE VÍDEO" in pdf[i].get_textpage().get_text_range():
            pages["manual-editor.png"] = i
            break
    for name, i in pages.items():
        img = pdf[i].render(scale=1.5).to_pil().convert("RGB")
        img.save(docs / name, optimize=True)
    pdf.close()


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
        manual = build_manual()
        export_docs(manual)
        print(manual)
        return
    app_dir = build_exe()
    if "--solo-exe" in args:
        print(app_dir)
        return
    manual = build_manual()
    shutil.copy(manual, app_dir / MANUAL_NAME)  # junto a rcordr.exe
    collect_licenses(app_dir)
    export_docs(manual)
    out = make_zip(app_dir)
    print(f"{out}  ({out.stat().st_size / 1_048_576:.0f} MB)")


if __name__ == "__main__":
    main()
