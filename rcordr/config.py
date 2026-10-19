"""Configuración: rutas de salida y atajos de teclado."""

import json
from pathlib import Path

APP_NAME = "rcordr"

# Carpeta de datos del usuario (config.json y temporales). No se usa %APPDATA%
# porque el Python de Microsoft Store lo virtualiza y ffmpeg no vería los archivos.
DATA_DIR = Path.home() / f".{APP_NAME}"
TEMP_DIR = DATA_DIR / "tmp"

DEFAULTS = {
    # Atajos globales. Formato: modificadores + tecla, separados por "+".
    # Modificadores válidos: ctrl, shift, alt, win.
    "hotkey_screenshot": "ctrl+shift+1",
    "hotkey_video": "ctrl+shift+2",
    "hotkey_audio": "ctrl+shift+3",
    "screenshots_dir": str(Path.home() / "Pictures" / APP_NAME),
    "videos_dir": str(Path.home() / "Videos" / APP_NAME),
    "record_audio": True,
    "fps": 30,
    # Altura máxima del vídeo final (se reduce si la pantalla es mayor).
    "max_video_height": 1080,
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    path = DATA_DIR / "config.json"
    try:
        cfg.update(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        save(cfg)
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg: dict) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "config.json").write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass
