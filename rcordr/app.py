"""Aplicación: icono en la bandeja, atajos globales y coordinación."""

import faulthandler
import gc
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path

import pystray
from PIL import ImageTk

from . import __version__, config, icon, ui, winapi
from .editor import VideoEditor
from .hotkeys import HotkeyListener
from .recorder import MIC, SYSTEM, Recorder, clean_temp
from .screenshot import RegionSelector

MIN_VIDEO = 32  # lado mínimo (px) de la zona de vídeo
SOURCE_NAMES = {SYSTEM: "sonido del ordenador", MIC: "micrófono"}


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
        self.rec_frame: ui.RegionFrame | None = None
        self.selector: RegionSelector | None = None
        self.busy = False  # iniciando/parando grabación
        self.edit_after = False  # abrir el editor al terminar la grabación
        self._calls: queue.Queue = queue.Queue()
        self.activation = winapi.ActivationEvent(config.APP_NAME)

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
            pystray.MenuItem(f"Grabar vídeo y editar\t{hk('hotkey_video_edit')}",
                             lambda: self.call(self.toggle_video, True),
                             visible=lambda item: not self.recorder.recording),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Abrir carpeta de capturas",
                             lambda: _open_dir(self.cfg["screenshots_dir"])),
            pystray.MenuItem("Abrir carpeta de vídeos",
                             lambda: _open_dir(self.cfg["videos_dir"])),
            pystray.MenuItem("Configuración", pystray.Menu(
                pystray.MenuItem("Grabar sonido del ordenador",
                                 lambda: self.call(self.toggle_option, "record_audio"),
                                 checked=lambda item: self.cfg["record_audio"]),
                pystray.MenuItem("Grabar micrófono",
                                 lambda: self.call(self.toggle_option, "record_mic"),
                                 checked=lambda item: self.cfg["record_mic"]),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Editar atajos y carpetas (config.json)",
                                 lambda: os.startfile(config.DATA_DIR / "config.json")),
            )),
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

    def _on_selected(self, image, zone):
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
    def toggle_video(self, edit: bool = False):
        """Empieza (eligiendo zona) o detiene la grabación.

        Con edit=True, al terminar se abre el editor en vez de guardar directamente.
        Mientras se graba, cualquiera de los dos atajos la detiene.
        """
        if self.busy:
            return
        if self.recorder.recording:
            self._stop_video()
        elif not self.selector:
            self.edit_after = edit
            what = "grabar y editar" if edit else "grabar"
            self.selector = RegionSelector(
                self.root, self._on_video_zone, color=ui.RED,
                hint=f"Elige la zona a {what} · Clic = pantalla completa · Esc = cancelar")

    def _on_video_zone(self, image, zone):
        self.selector = None
        if zone is None:
            return
        if zone["width"] < MIN_VIDEO or zone["height"] < MIN_VIDEO:
            ui.Toast(self.stack, "Zona demasiado pequeña",
                     f"Selecciona al menos {MIN_VIDEO} × {MIN_VIDEO} píxeles.").show()
            return
        self._start_video(zone)

    def _start_video(self, zone):
        self.busy = True
        wanted = [src for src, key in ((SYSTEM, "record_audio"), (MIC, "record_mic"))
                  if self.cfg[key]]

        def work():
            try:
                got = self.recorder.start(zone, int(self.cfg["fps"]), wanted,
                                          int(self.cfg["max_video_height"]))
                self.call(self._started, zone, wanted, got)
            except Exception as e:
                self.call(self._failed, "No se pudo iniciar la grabación", e)

        threading.Thread(target=work, daemon=True).start()

    def _started(self, zone, wanted, got):
        self.busy = False
        if not zone["full"]:
            self.rec_frame = ui.RegionFrame(self.stack, zone)
        self.rec_panel = ui.RecordingPanel(self.stack, got, lambda: self.call(self.toggle_video),
                                           stop_text="■ Detener y editar" if self.edit_after
                                           else "■ Detener")
        self.rec_panel.show()
        missing = [SOURCE_NAMES[src] for src in wanted if src not in got]
        if missing:
            ui.Toast(self.stack, "Grabando sin " + " ni ".join(missing),
                     "No se pudo abrir el dispositivo de audio.").show()
        self.tray.title = "rcordr — grabando"
        self.tray.update_menu()
        self._blink_tray()

    def _stop_video(self):
        self.busy = True
        if self.rec_frame:
            self.rec_frame.close()
            self.rec_frame = None
        if self.rec_panel:
            self.rec_panel.processing()
        # Para editar, cada fuente en su pista (el editor ajusta los volúmenes);
        # si no, se mezclan ya con los volúmenes guardados.
        self.recorder.stop(Path(self.cfg["videos_dir"]),
                           lambda path, err: self.call(self._stopped, path, err),
                           separate=self.edit_after, volumes=self._volumes())
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
        if self.edit_after:
            try:
                VideoEditor(self.root, path, self._edited, self._volumes())
                return
            except Exception as e:  # si el editor falla, el vídeo ya está guardado
                ui.Toast(self.stack, "No se pudo abrir el editor", str(e)[:200]).show()
        self._video_ready(path)

    def _volumes(self) -> dict[str, float]:
        return {SYSTEM: float(self.cfg["volume_system"]), MIC: float(self.cfg["volume_mic"])}

    def _edited(self, path, volumes):
        if volumes:  # recordar la mezcla elegida para las próximas grabaciones
            self.cfg["volume_system"] = volumes.get(SYSTEM, self.cfg["volume_system"])
            self.cfg["volume_mic"] = volumes.get(MIC, self.cfg["volume_mic"])
            config.save(self.cfg)
        if path is None:
            ui.Toast(self.stack, "Vídeo descartado", timeout=3).show()
        else:
            self._video_ready(path)

    def _video_ready(self, path):
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

    # --- Configuración ------------------------------------------------------
    def toggle_option(self, key):
        self.cfg[key] = not self.cfg[key]
        config.save(self.cfg)
        self.tray.update_menu()
        if self.recorder.recording:
            ui.Toast(self.stack, "Se aplicará en la próxima grabación", timeout=3).show()

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
            self.cfg["hotkey_video_edit"]: lambda: self.call(self.toggle_video, True),
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
            self.show_ready()

        def wait_activation():  # se abrió otra instancia (icono del escritorio/barra)
            while True:
                self.activation.wait()
                self.call(self.show_ready)

        threading.Thread(target=wait_activation, daemon=True, name="activation").start()
        self.root.mainloop()

    def show_ready(self):
        c = self.cfg
        state = "grabando" if self.recorder.recording else "está listo"
        ui.Toast(self.stack, f"rcordr {state}",
                 f"{c['hotkey_screenshot'].upper()}  captura de imagen\n"
                 f"{c['hotkey_video'].upper()}  grabar / detener vídeo\n"
                 f"{c['hotkey_video_edit'].upper()}  grabar y editar", timeout=6).show()

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


_log_file = None


def _setup_log():
    """Con pythonw no hay consola: errores y cierres inesperados van a rcordr.log.

    faulthandler registra también los fallos nativos (p. ej. en el audio) con la
    traza de Python. Se guarda el log de la sesión anterior como rcordr.log.1.
    """
    global _log_file
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = config.DATA_DIR / "rcordr.log"
        if path.exists():
            os.replace(path, path.with_name("rcordr.log.1"))
        _log_file = open(path, "w", encoding="utf-8", buffering=1)
    except OSError:
        return
    sys.stdout = sys.stderr = _log_file  # tracebacks de Tk y de hilos
    faulthandler.enable(_log_file, all_threads=True)
    print(f"rcordr {__version__} · {datetime.now():%Y-%m-%d %H:%M:%S}")


def selftest(quiet: bool = False) -> int:
    """rcordr --selftest: comprueba que todo funciona (ventanas, ffmpeg, audio).

    Graba 2 s de una esquina de la pantalla con las fuentes de audio
    configuradas, comprueba el MP4 y lo borra. El resultado queda en
    rcordr-selftest.log y, salvo con --quiet, en un mensaje.
    """
    from tkinter import messagebox

    from .editor import probe
    from .recorder import TEMP_DIR, ffmpeg_exe
    from .screenshot import monitor_at

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = config.DATA_DIR / "rcordr-selftest.log"
    log = open(path, "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log
    faulthandler.enable(log, all_threads=True)
    ok = True

    def check(name, fn):
        nonlocal ok
        try:
            print(f"[OK]    {name}: {fn()}")
        except Exception as e:
            ok = False
            print(f"[FALLO] {name}: {e!r}")

    print(f"rcordr {__version__} · {datetime.now():%Y-%m-%d %H:%M:%S} · "
          f"{'ejecutable' if getattr(sys, 'frozen', False) else 'Python'}")
    check("ffmpeg", ffmpeg_exe)

    def window():
        app = App()
        app.root.update()
        app.root.destroy()
        del app
        gc.collect()  # liberar Tk en este hilo y no en uno de los de audio
        return "Tk y bandeja"
    check("ventana", window)

    def record():
        cfg = config.load()
        sources = [s for s, k in ((SYSTEM, "record_audio"), (MIC, "record_mic")) if cfg[k]]
        mon = monitor_at(0, 0)
        zone = {"left": mon["left"], "top": mon["top"], "width": 320, "height": 240}
        rec = Recorder()
        got = rec.start(zone, 30, sources, 1080)
        time.sleep(2)
        done, res = threading.Event(), {}
        rec.stop(TEMP_DIR / "selftest", lambda p, e: (res.update(p=p, e=e), done.set()))
        if not done.wait(30) or res["e"]:
            raise RuntimeError(res.get("e") or "no terminó")
        info = probe(res["p"])
        res["p"].unlink(missing_ok=True)
        missing = [s for s in sources if s not in got]
        if missing:
            raise RuntimeError(f"no se pudo abrir el audio: {missing}")
        return (f"{info['width']}x{info['height']}, {info['duration']:.1f} s, "
                f"audio pedido {sources} → grabado {got}")
    check("grabación de 2 s", record)

    print("RESULTADO:", "correcto" if ok else "con fallos")
    if not quiet:
        title = "rcordr · diagnóstico"
        if ok:
            messagebox.showinfo(title, "Todo funciona correctamente.")
        else:
            messagebox.showerror(title, f"Hay fallos. Detalles en:\n{path}")
    return 0 if ok else 1


def main():
    winapi.set_dpi_aware()
    if "--selftest" in sys.argv:
        sys.exit(selftest(quiet="--quiet" in sys.argv))
    if not winapi.single_instance(config.APP_NAME):
        # Ya está abierta: que muestre el aviso con los atajos
        winapi.ActivationEvent(config.APP_NAME).signal()
        return
    _setup_log()
    App().run()
