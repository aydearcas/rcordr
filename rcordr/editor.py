"""Editor sencillo tras grabar: recortar inicio/fin y quitar el audio.

La vista previa se decodifica con el mismo ffmpeg (fotogramas RGB por
tubería) y el sonido se reproduce con PyAudio: no hacen falta más librerías.
"""

import os
import queue
import re
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path

import pyaudiowpatch as pyaudio
from PIL import Image, ImageTk

from . import ui, winapi
from .recorder import CREATE_NO_WINDOW, ffmpeg_exe

MIN_LEN = 0.5        # duración mínima del recorte (s)
AUDIO_RATE = 48000
TRACK = "#2b2b31"
SELECTED = "#24527f"


def probe(path: Path) -> dict:
    """Duración, tamaño, fps y si tiene audio (leyendo la salida de ffmpeg -i)."""
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)],
                       capture_output=True, creationflags=CREATE_NO_WINDOW)
    text = r.stderr.decode("utf-8", "replace")
    dur = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", text)
    size = re.search(r"Video: .*?, (\d{2,5})x(\d{2,5})", text)
    if not dur or not size:
        raise RuntimeError("No se pudo leer el vídeo.")
    fps = re.search(r"(\d+(?:\.\d+)?) fps", text)
    return {
        "duration": int(dur[1]) * 3600 + int(dur[2]) * 60 + float(dur[3]),
        "width": int(size[1]), "height": int(size[2]),
        "fps": float(fps[1]) if fps else 30.0,
        "has_audio": "Audio:" in text,
    }


def _ffmpeg(args, **kw) -> subprocess.Popen:
    return subprocess.Popen([ffmpeg_exe(), "-v", "error", *args], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            creationflags=CREATE_NO_WINDOW, **kw)


class Player:
    """Reproduce el tramo [t0, t1]: vídeo por tubería de ffmpeg + audio por PyAudio."""

    def __init__(self, path: Path, fps: float, size: tuple[int, int], pa):
        self.path, self.fps, (self.w, self.h), self.pa = path, fps, size, pa
        self.frames: queue.Queue = queue.Queue(maxsize=8)
        self._stop = threading.Event()
        self._go = threading.Event()   # el audio arranca con el primer fotograma
        self._procs: list[subprocess.Popen] = []
        self._audio_thread = None
        self._held = None
        self.eof = False
        self.wall0 = None

    def start(self, t0: float, t1: float, with_audio: bool):
        self.t0, self.t1 = t0, t1
        cut = ["-ss", f"{t0:.3f}", "-i", str(self.path), "-t", f"{t1 - t0:.3f}"]
        video = _ffmpeg([*cut, "-an", "-vf", f"fps={self.fps},scale={self.w}:{self.h}",
                         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
        self._procs.append(video)
        threading.Thread(target=self._read_video, args=(video,), daemon=True).start()
        if with_audio:
            audio = _ffmpeg([*cut, "-vn", "-f", "s16le", "-ac", "2",
                             "-ar", str(AUDIO_RATE), "-"])
            self._procs.append(audio)
            self._audio_thread = threading.Thread(target=self._play_audio, args=(audio,),
                                                  daemon=True)
            self._audio_thread.start()

    def _read_video(self, proc):
        size, i = self.w * self.h * 3, 0
        while not self._stop.is_set():
            data = proc.stdout.read(size)
            if len(data) < size:
                break
            while not self._stop.is_set():
                try:
                    self.frames.put((i, data), timeout=0.1)
                    break
                except queue.Full:
                    pass
            i += 1
        self.eof = True

    def _play_audio(self, proc):
        stream = None
        try:
            stream = self.pa.open(format=pyaudio.paInt16, channels=2, rate=AUDIO_RATE,
                                  output=True)
            self._go.wait()
            while not self._stop.is_set():
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                stream.write(chunk)
        except Exception:
            pass  # sin salida de audio: la vista previa sigue sin sonido
        finally:
            if stream:
                stream.stop_stream()
                stream.close()

    def next_frame(self) -> bytes | None:
        """El fotograma que toca mostrar ahora, o None si no hay que cambiarlo."""
        if self.wall0 is None:
            try:
                _, data = self.frames.get_nowait()
            except queue.Empty:
                return None
            self.wall0 = time.monotonic()
            self._go.set()
            return data
        target = int((time.monotonic() - self.wall0) * self.fps)
        latest = None
        while True:
            if self._held is None:
                try:
                    self._held = self.frames.get_nowait()
                except queue.Empty:
                    break
            if self._held[0] > target:
                break
            latest, self._held = self._held[1], None
        return latest

    @property
    def position(self) -> float:
        if self.wall0 is None:
            return self.t0
        return min(self.t1, self.t0 + time.monotonic() - self.wall0)

    @property
    def finished(self) -> bool:
        return self.eof and self._held is None and self.frames.empty()

    def stop(self):
        self._stop.set()
        self._go.set()
        for p in self._procs:
            p.kill()
        if self._audio_thread:
            self._audio_thread.join(1)


class FrameGrabber(threading.Thread):
    """Saca fotogramas sueltos al mover los tiradores; solo atiende el último pedido."""

    def __init__(self, path: Path, size: tuple[int, int], out: queue.Queue):
        super().__init__(daemon=True, name="frames")
        self.path, (self.w, self.h), self.out = path, size, out
        self._want = None
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._closed = False

    def request(self, t: float):
        with self._lock:
            self._want = t
            self._event.set()

    def close(self):
        self._closed = True
        self._event.set()

    def run(self):
        size = self.w * self.h * 3
        while True:
            self._event.wait()
            if self._closed:
                return
            with self._lock:
                t, self._want = self._want, None
                self._event.clear()
            if t is None:
                continue
            p = _ffmpeg(["-ss", f"{t:.3f}", "-i", str(self.path), "-frames:v", "1",
                         "-vf", f"scale={self.w}:{self.h}",
                         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
            data = p.stdout.read()
            p.wait()
            if len(data) >= size and not self._closed:
                self.out.put(data[:size])


def export(src: Path, dst: Path, start: float, end: float, trimmed: bool,
           keep_audio: bool, on_progress) -> None:
    """Escribe dst con el tramo elegido. Recodifica solo si hay recorte."""
    args = [ffmpeg_exe(), "-v", "error", "-y", "-nostats", "-progress", "pipe:1"]
    if trimmed:  # recodificar para cortar justo en el fotograma elegido
        args += ["-ss", f"{start:.3f}", "-i", str(src), "-t", f"{end - start:.3f}",
                 "-map", "0:v:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                 "-pix_fmt", "yuv420p"]
    else:        # solo quitar el audio: copia directa, instantánea
        args += ["-i", str(src), "-map", "0:v:0", "-c:v", "copy"]
    if keep_audio:
        args += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "160k"]
    args += ["-movflags", "+faststart", str(dst)]

    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=CREATE_NO_WINDOW)
    total = max(end - start, 0.001)
    for raw in p.stdout:
        key, _, value = raw.decode("utf-8", "replace").strip().partition("=")
        if key == "out_time_us" and value.isdigit():
            on_progress(min(1.0, int(value) / 1e6 / total))
    if p.wait() != 0:
        err = p.stderr.read().decode("utf-8", "replace").strip().splitlines()[-3:]
        raise RuntimeError("\n".join(err) or "ffmpeg falló")


def _fmt(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


class VideoEditor:
    """Ventana flotante: vista previa, recorte con dos tiradores y quitar audio.

    on_done(path) al guardar o cerrar (vídeo final), on_done(None) al descartar.
    """

    def __init__(self, root: tk.Tk, path: Path, on_done):
        self.root, self.path, self.on_done = root, Path(path), on_done
        self.info = probe(self.path)
        scale = root.winfo_fpixels("1i") / 96
        self.px = px = lambda n: int(n * scale)  # noqa: E731

        # Vista previa: cabe en 800×450 (lógicos), sin ampliar vídeos pequeños
        vw, vh = self.info["width"], self.info["height"]
        k = min(px(800) / vw, px(450) / vh, 1.0)
        self.w, self.h = max(2, int(vw * k) // 2 * 2), max(2, int(vh * k) // 2 * 2)

        self.dur = self.info["duration"]
        self.fps = self.info["fps"]
        self.start, self.end, self.pos = 0.0, self.dur, 0.0
        self.player: Player | None = None
        self.pa = pyaudio.PyAudio()
        self._scrub: queue.Queue = queue.Queue()
        self._ui: queue.Queue = queue.Queue()
        self.grabber = FrameGrabber(self.path, (self.w, self.h), self._scrub)
        self.grabber.start()
        self._drag = None
        self._exporting = False
        self._closed = False
        self._confirm_discard = None

        self._build()
        self._redraw_timeline()
        self.grabber.request(0)
        self._tick_id = self.win.after(15, self._tick)

    # --- Interfaz -----------------------------------------------------------
    def _build(self):
        px = self.px
        win = self.win = tk.Toplevel(self.root)
        win.title("rcordr — Editar vídeo")
        win.configure(bg=ui.BG)
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.protocol("WM_DELETE_WINDOW", self._close)

        body = tk.Frame(win, bg=ui.BG, padx=px(14), pady=px(12))
        body.pack()

        self.canvas = tk.Canvas(body, width=self.w, height=self.h, bg="black",
                                highlightthickness=0, cursor="hand2")
        self.canvas.grid(row=0, column=0, columnspan=6)
        self.photo = ImageTk.PhotoImage(Image.new("RGB", (self.w, self.h)))
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.canvas.bind("<Button-1>", lambda e: self.toggle_play())

        self.tl_h = px(40)
        self.tl = tk.Canvas(body, width=self.w, height=self.tl_h, bg=ui.BG,
                            highlightthickness=0)
        self.tl.grid(row=1, column=0, columnspan=6, pady=(px(10), px(2)))
        self.tl.bind("<ButtonPress-1>", self._press)
        self.tl.bind("<B1-Motion>", self._move)
        self.tl.bind("<ButtonRelease-1>", self._release)
        self.tl.bind("<Motion>", self._hover)

        self.range_lbl = tk.Label(body, bg=ui.BG, fg=ui.FG, font=(ui.FONT, 10))
        self.range_lbl.grid(row=2, column=0, columnspan=4, sticky="w")
        self.time_lbl = tk.Label(body, bg=ui.BG, fg=ui.MUTED, font=(ui.FONT, 10))
        self.time_lbl.grid(row=2, column=4, columnspan=2, sticky="e")

        row = tk.Frame(body, bg=ui.BG)
        row.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(px(10), 0))
        self.play_btn = ui.make_button(row, "▶  Reproducir", self.toggle_play, "#3a3a42", px)
        self.play_btn.pack(side="left")

        self.mute = tk.BooleanVar(value=not self.info["has_audio"])
        self.mute_chk = tk.Checkbutton(
            row, text="Quitar audio", variable=self.mute, command=self._mute_changed,
            bg=ui.BG, fg=ui.FG, selectcolor=ui.BG, activebackground=ui.BG,
            activeforeground=ui.FG, font=(ui.FONT, 10), cursor="hand2")
        if not self.info["has_audio"]:
            self.mute_chk.configure(text="Sin audio", state="disabled")
        self.mute_chk.pack(side="left", padx=(px(14), 0))

        self.save_btn = ui.make_button(row, "Guardar", self._save, ui.ACCENT, px)
        self.save_btn.pack(side="right")
        self.discard_btn = ui.make_button(row, "Descartar", self._discard, "#3a3a42", px)
        self.discard_btn.pack(side="right", padx=(0, px(8)))

        self.hint = tk.Label(
            body, bg=ui.BG, fg=ui.MUTED, font=(ui.FONT, 9),
            text="Arrastra los extremos azules para recortar · Espacio: reproducir/pausa"
                 " · I / O: inicio / fin en la posición actual")
        self.hint.grid(row=4, column=0, columnspan=6, sticky="w", pady=(px(8), 0))

        win.bind("<space>", lambda e: self.toggle_play())
        win.bind("<KeyPress-i>", lambda e: self._set_start(self.pos))
        win.bind("<KeyPress-o>", lambda e: self._set_end(self.pos))
        win.bind("<KeyPress-I>", lambda e: self._set_start(self.pos))
        win.bind("<KeyPress-O>", lambda e: self._set_end(self.pos))

        # Centrado en la pantalla principal
        win.update_idletasks()
        l, t, r, b = winapi.work_area()
        w, h = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry(f"+{l + (r - l - w) // 2}+{t + (b - t - h) // 2}")
        winapi.dark_title_bar(win)
        win.focus_force()

    # --- Línea de tiempo ----------------------------------------------------
    def _x(self, t: float) -> float:
        m = self.px(8)
        return m + t / self.dur * (self.w - 2 * m)

    def _t(self, x: float) -> float:
        m = self.px(8)
        return min(self.dur, max(0.0, (x - m) / (self.w - 2 * m) * self.dur))

    def _redraw_timeline(self):
        px, c = self.px, self.tl
        c.delete("all")
        top, bot = px(8), self.tl_h - px(8)
        c.create_rectangle(self._x(0), top, self._x(self.dur), bot, fill=TRACK, width=0)
        xs, xe = self._x(self.start), self._x(self.end)
        c.create_rectangle(xs, top, xe, bot, fill=SELECTED, width=0)
        hw = px(7)
        for x0, x1 in ((xs - hw, xs), (xe, xe + hw)):
            c.create_rectangle(x0, top - px(4), x1, bot + px(4), fill=ui.ACCENT, width=0)
            mid = (x0 + x1) / 2
            c.create_line(mid, top + px(6), mid, bot - px(6), fill="white", width=1)
        self._playhead = c.create_line(0, 0, 0, 0, fill="white", width=max(2, px(2)))
        self._move_playhead()
        length = self.end - self.start
        self.range_lbl.configure(
            text=f"Inicio {_fmt(self.start)}   ·   Fin {_fmt(self.end)}   ·   {length:.1f} s")

    def _move_playhead(self):
        x = self._x(self.pos)
        self.tl.coords(self._playhead, x, 0, x, self.tl_h)
        self.time_lbl.configure(text=f"{_fmt(self.pos)} / {_fmt(self.dur)}")

    def _handle_at(self, x) -> str | None:
        """"start"/"end" si x está sobre un tirador, si no None."""
        ds, de = abs(x - self._x(self.start)), abs(x - self._x(self.end))
        if min(ds, de) > self.px(12):
            return None
        return "start" if ds < de else "end"

    def _hover(self, e):
        if self._drag is None:  # durante el arrastre se mantiene el cursor
            self.tl.configure(cursor="sb_h_double_arrow" if self._handle_at(e.x) else "")

    def _press(self, e):
        if self._exporting:
            return
        self.pause()
        self._drag = self._handle_at(e.x) or "pos"
        self._move(e)

    def _release(self, e):
        self._drag = None
        self._hover(e)

    def _move(self, e):
        t = self._t(e.x)
        if self._drag == "start":
            self._set_start(t)
        elif self._drag == "end":
            self._set_end(t)
        elif self._drag == "pos":
            self.pos = t
            self._move_playhead()
            self._preview(t)

    def _set_start(self, t):
        if self._exporting:
            return
        self.pause()
        self.start = min(max(0.0, t), self.end - MIN_LEN)
        self.pos = self.start
        self._redraw_timeline()
        self._preview(self.start)

    def _set_end(self, t):
        if self._exporting:
            return
        self.pause()
        self.end = max(min(self.dur, t), self.start + MIN_LEN)
        self.pos = self.end
        self._redraw_timeline()
        self._preview(self.end - 1 / self.fps)

    def _preview(self, t):
        self.grabber.request(min(max(0.0, t), self.dur - 1 / self.fps))

    # --- Reproducción -------------------------------------------------------
    def toggle_play(self):
        if self.player:
            self.pause()
        else:
            self.play()

    def play(self):
        if self._exporting or self._closed:
            return
        if not (self.start <= self.pos < self.end - 0.05):
            self.pos = self.start
        self.player = Player(self.path, self.fps, (self.w, self.h), self.pa)
        self.player.start(self.pos, self.end, with_audio=not self.mute.get())
        self.play_btn.configure(text="⏸  Pausa")

    def pause(self):
        if not self.player:
            return
        self.pos = self.player.position
        self.player.stop()
        self.player = None
        self.play_btn.configure(text="▶  Reproducir")
        self._move_playhead()

    def _mute_changed(self):
        if self.player:  # aplica el cambio al momento
            self.pause()
            self.play()

    def _show(self, data: bytes):
        self.photo.paste(Image.frombuffer("RGB", (self.w, self.h), data, "raw", "RGB", 0, 1))

    def _tick(self):
        if self._closed:
            return
        try:
            while True:
                self._ui.get_nowait()()
        except queue.Empty:
            pass
        if self.player:
            data = self.player.next_frame()
            if data:
                self._show(data)
            self.pos = self.player.position
            self._move_playhead()
            if self.player.finished:
                self.pause()
                self.pos = self.end
                self._move_playhead()
        else:
            latest = None
            try:
                while True:
                    latest = self._scrub.get_nowait()
            except queue.Empty:
                pass
            if latest:
                self._show(latest)
        self._tick_id = self.win.after(15, self._tick)

    # --- Guardar / descartar ------------------------------------------------
    def _save(self):
        if self._exporting:
            return
        self.pause()
        trimmed = self.start > 0.05 or self.end < self.dur - 0.05
        drop_audio = self.info["has_audio"] and self.mute.get()
        if not trimmed and not drop_audio:
            self._finish(self.path)  # sin cambios
            return

        self._exporting = True
        self.save_btn.configure(text="Guardando…")
        self.discard_btn.pack_forget()
        self.hint.configure(text="Generando el vídeo editado…", fg=ui.MUTED)
        tmp = self.path.with_name(self.path.stem + ".editando.mp4")

        def progress(f):
            self._ui.put(lambda: self.save_btn.configure(text=f"Guardando {int(f * 100)} %"))

        def work():
            try:
                export(self.path, tmp, self.start, self.end, trimmed,
                       keep_audio=not drop_audio, on_progress=progress)
                os.replace(tmp, self.path)
                self._ui.put(lambda: self._finish(self.path))
            except Exception as e:
                tmp.unlink(missing_ok=True)
                self._ui.put(lambda: self._export_failed(e))

        threading.Thread(target=work, daemon=True, name="export").start()

    def _export_failed(self, err):
        self._exporting = False
        self.save_btn.configure(text="Guardar")
        self.discard_btn.pack(side="right", padx=(0, self.px(8)))
        self.hint.configure(text=f"No se pudo guardar: {str(err)[:150]}", fg=ui.RED)

    def _discard(self):
        if self._exporting:
            return
        if not self._confirm_discard:  # primer clic: pide confirmación
            self.discard_btn.configure(text="¿Seguro? Borrar vídeo", bg=ui.RED)
            self._confirm_discard = self.win.after(3000, self._reset_discard)
            return
        self._finish(None)
        path = self.path

        def remove():  # ffmpeg puede tardar un instante en soltar el archivo
            for _ in range(30):
                try:
                    path.unlink(missing_ok=True)
                    return
                except PermissionError:
                    time.sleep(0.1)

        threading.Thread(target=remove, daemon=True).start()

    def _reset_discard(self):
        self._confirm_discard = None
        self.discard_btn.configure(text="Descartar", bg="#3a3a42")

    def _close(self):
        if not self._exporting:
            self._finish(self.path)  # cerrar = conservar el vídeo tal cual

    def _finish(self, result):
        if self._closed:
            return
        self._closed = True
        self.pause()
        self.grabber.close()
        self.win.after_cancel(self._tick_id)
        self.win.destroy()
        threading.Thread(target=self.pa.terminate, daemon=True).start()
        self.on_done(result)
