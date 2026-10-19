"""Aplicación: icono en la bandeja, atajos globales y coordinación."""

import os
import queue
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path

import pystray
from PIL import ImageTk

from . import config, icon, ui, winapi
from .hotkeys import HotkeyListener
from .recorder import Recorder, clean_temp
from .screenshot import RegionSelector, monitor_under_cursor


class App:
    def __init__(self):
        self.cfg = config.load()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("rcordr")
        self._icon_img = icon.make(64)
        self._icon_tk = ImageTk.PhotoImage(self._icon_img)
        self.root.iconphoto(True, self._icon_tk)

        self.stack = ui.Stack(self.root)
        self.recorder = Recorder()
        self.rec_panel: ui.RecordingPanel | None = None
        self.selector: RegionSelector | None = None
        self.busy = False  # iniciando/parando grabación
        self._calls: queue.Queue = queue.Queue()

        self.tray = pystray.Icon("rcordr", self._icon_img, "rcordr", self._menu())
        self._blink = False

    # --- Hilos -> hilo de Tk ------------------------------------------------
    def call(self, fn, *args):
        """Ejecuta fn en el hilo de Tk (desde atajos, bandeja o grabador)."""
        self._calls.put((fn, args))

    def _pump(self):
        try:
            while True:
                fn, args = self._calls.get_nowait()
                fn(*args)
        except queue.Empty:
            pass
        self.root.after(30, self._pump)

    # --- Bandeja ------------------------------------------------------------
    def _menu(self):
        hk = lambda key: self.cfg[key].upper()  # noqa: E731
        return pystray.Menu(
            pystray.MenuItem(f"Capturar imagen\t{hk('hotkey_screenshot')}",
                             lambda: self.call(self.screenshot), default=True),
            pystray.MenuItem(
                lambda item: ("Detener grabación" if self.recorder.recording
                              else "Grabar vídeo") + f"\t{hk('hotkey_video')}",
                lambda: self.call(self.toggle_video)),
            pystray.MenuItem(f"Grabar sonido del ordenador\t{hk('hotkey_audio')}",
                             lambda: self.call(self.toggle_audio),
                             checked=lambda item: self.cfg["record_audio"]),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Abrir carpeta de capturas",
                             lambda: _open_dir(self.cfg["screenshots_dir"])),
            pystray.MenuItem("Abrir carpeta de vídeos",
                             lambda: _open_dir(self.cfg["videos_dir"])),
            pystray.MenuItem("Editar atajos (config.json)",
                             lambda: os.startfile(config.DATA_DIR / "config.json")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", lambda: self.call(self.quit)),
        )

    def _blink_tray(self):
        """Hace parpadear el punto rojo del icono mientras se graba."""
        if not self.recorder.recording:
            self.tray.icon = self._icon_img
            return
        self._blink = not self._blink
        self.tray.icon = icon.make(64, dot=not self._blink)
        self.root.after(600, self._blink_tray)

    # --- Captura de imagen --------------------------------------------------
    def screenshot(self):
        if self.selector:
            return
        self.selector = RegionSelector(self.root, self._on_selected)

    def _on_selected(self, image):
        self.selector = None
        if image is None:
            return
        copied = winapi.copy_image_to_clipboard(image)
        panel = ui.SavePanel(self.stack, image, lambda: self._save_image(image))
        if not copied:
            panel.title.configure(text="No se pudo copiar al portapapeles")
        panel.show()

    def _save_image(self, image) -> Path | None:
        folder = Path(self.cfg["screenshots_dir"])
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"captura_{datetime.now():%Y%m%d_%H%M%S}.png"
            image.save(path, "PNG", optimize=True)
            return path
        except OSError as e:
            ui.Toast(self.stack, "No se pudo guardar", str(e)).show()
            return None

    # --- Vídeo --------------------------------------------------------------
    def toggle_video(self):
        if self.busy:
            return
        if self.recorder.recording:
            self._stop_video()
        else:
            self._start_video()

    def _start_video(self):
        self.busy = True
        rect = monitor_under_cursor()
        with_audio = self.cfg["record_audio"]

        def work():
            try:
                audio_ok = self.recorder.start(rect, int(self.cfg["fps"]), with_audio,
                                               int(self.cfg["max_video_height"]))
                self.call(self._started, with_audio, audio_ok)
            except Exception as e:
                self.call(self._failed, "No se pudo iniciar la grabación", e)

        threading.Thread(target=work, daemon=True).start()

    def _started(self, wanted_audio, audio_ok):
        self.busy = False
        self.rec_panel = ui.RecordingPanel(self.stack, audio_ok, lambda: self.call(self.toggle_video))
        self.rec_panel.show()
        if wanted_audio and not audio_ok:
            ui.Toast(self.stack, "Grabando sin sonido",
                     "No se encontró la salida de audio del ordenador.").show()
        self.tray.title = "rcordr — grabando"
        self.tray.update_menu()
        self._blink_tray()

    def _stop_video(self):
        self.busy = True
        if self.rec_panel:
            self.rec_panel.processing()
        self.recorder.stop(Path(self.cfg["videos_dir"]),
                           lambda path, err: self.call(self._stopped, path, err))
        self.tray.title = "rcordr"
        self.tray.update_menu()

    def _stopped(self, path, err):
        self.busy = False
        if self.rec_panel:
            self.rec_panel.close()
            self.rec_panel = None
        if err:
            self._failed("Error al guardar el vídeo", err)
            return
        size_mb = path.stat().st_size / 1_048_576
        copied = winapi.copy_file_to_clipboard(path)
        text = f"{path.name} · {size_mb:.1f} MB"
        if copied:
            text += "\nCopiado: pégalo en WhatsApp con Ctrl+V"
        ui.Toast(self.stack, "Vídeo guardado ✓", text,
                 action=("Abrir", lambda: ui._reveal(path)), timeout=10).show()

    def _failed(self, title, err):
        self.busy = False
        ui.Toast(self.stack, title, str(err)[:400], timeout=10).show()

    # --- Sonido -------------------------------------------------------------
    def toggle_audio(self):
        self.cfg["record_audio"] = not self.cfg["record_audio"]
        config.save(self.cfg)
        self.tray.update_menu()
        state = "activado" if self.cfg["record_audio"] else "desactivado"
        note = "Se aplicará en la próxima grabación." if self.recorder.recording else ""
        ui.Toast(self.stack, f"Sonido del ordenador {state}", note, timeout=3).show()

    # --- Ciclo de vida ------------------------------------------------------
    def run(self):
        # Antes de activar los atajos, para no tocar una grabación nueva
        try:
            recovered = clean_temp(Path(self.cfg["videos_dir"]))
        except Exception:
            recovered = []
        if recovered:
            ui.Toast(self.stack, "Vídeo recuperado",
                     "Se recuperó una grabación que quedó a medias (sin sonido).",
                     action=("Abrir", lambda: ui._reveal(recovered[-1])),
                     timeout=10).show()

        hotkeys = HotkeyListener({
            self.cfg["hotkey_screenshot"]: lambda: self.call(self.screenshot),
            self.cfg["hotkey_video"]: lambda: self.call(self.toggle_video),
            self.cfg["hotkey_audio"]: lambda: self.call(self.toggle_audio),
        })
        failed = hotkeys.start()
        self.hotkeys = hotkeys

        threading.Thread(target=self.tray.run, daemon=True, name="tray").start()
        self.root.after(30, self._pump)

        if failed:
            ui.Toast(self.stack, "Atajos no disponibles",
                     "Otra aplicación ya usa: " + ", ".join(failed).upper()
                     + ". Puedes cambiarlos en config.json.", timeout=10).show()
        else:
            c = self.cfg
            ui.Toast(self.stack, "rcordr está listo",
                     f"{c['hotkey_screenshot'].upper()}  captura de imagen\n"
                     f"{c['hotkey_video'].upper()}  grabar / detener vídeo\n"
                     f"{c['hotkey_audio'].upper()}  sonido on/off", timeout=6).show()
        self.root.mainloop()

    def quit(self):
        if self.recorder.recording:
            # Guarda lo grabado antes de salir
            self.recorder.stop(Path(self.cfg["videos_dir"]),
                               lambda p, e: self.call(self._exit))
            return
        self._exit()

    def _exit(self):
        self.hotkeys.stop()
        self.tray.stop()
        self.root.quit()


def _open_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)
    subprocess.Popen(["explorer", str(path)])


def main():
    winapi.set_dpi_aware()
    if not winapi.single_instance(config.APP_NAME):
        return
    App().run()
