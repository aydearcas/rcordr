"""Configuración: rutas de salida y atajos de teclado."""

import json
import os
from pathlib import Path

APP_NAME = "rcordr"

# Carpeta de datos del usuario (config.json y temporales). No se usa %APPDATA%
# porque el Python de Microsoft Store lo virtualiza y ffmpeg no vería los archivos.
# RCORDR_DATA_DIR permite usar otra carpeta (pruebas) sin tocar la config real.
DATA_DIR = Path(os.environ.get("RCORDR_DATA_DIR") or Path.home() / f".{APP_NAME}")
TEMP_DIR = DATA_DIR / "tmp"

DEFAULTS = {
    # Atajos globales. Formato: modificadores + tecla, separados por "+".
    # Modificadores válidos: ctrl, shift, alt, win.
    "hotkey_screenshot": "ctrl+shift+1",
    "hotkey_video": "ctrl+shift+2",
    "hotkey_video_edit": "ctrl+shift+3",  # grabar y abrir el editor al terminar
    "screenshots_dir": str(Path.home() / "Pictures" / APP_NAME),
    "videos_dir": str(Path.home() / "Videos" / APP_NAME),
    "record_audio": True,   # sonido del ordenador
    "record_mic": False,    # micrófono (entrada predeterminada de Windows)
    # Volúmenes de la mezcla (1.0 = 100 %). Los ajusta el editor al guardar.
    "volume_system": 1.0,
    "volume_mic": 1.0,
    "fps": 30,
    # Altura máxima del vídeo final (se reduce si la pantalla es mayor).
    "max_video_height": 1080,
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    path = DATA_DIR / "config.json"
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        cfg.update(saved)
        if "hotkey_audio" in cfg:
            # Versión anterior: Ctrl+Shift+3 era sonido on/off y 4 grabar y editar.
            # El sonido pasó al menú Configuración y grabar y editar ocupa su atajo.
            old = cfg.pop("hotkey_audio")
            if cfg.get("hotkey_video_edit") == "ctrl+shift+4":
                cfg["hotkey_video_edit"] = old
            save(cfg)
        elif DEFAULTS.keys() - saved.keys():
            save(cfg)  # añade al archivo las opciones nuevas de esta versión
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
