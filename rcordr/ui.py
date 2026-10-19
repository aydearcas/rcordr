"""Paneles flotantes abajo a la derecha: guardar captura, indicador REC y avisos."""

import time
import tkinter as tk

from PIL import ImageTk

from .winapi import exclude_from_capture, work_area

BG = "#1f1f23"
FG = "#f2f2f2"
MUTED = "#a0a0a8"
ACCENT = "#3d9cff"
RED = "#e5383b"
FONT = "Segoe UI"


class Stack:
    """Apila los paneles desde la esquina inferior derecha hacia arriba."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.panels: list["Panel"] = []
        self.scale = root.winfo_fpixels("1i") / 96

    def px(self, n: float) -> int:
        return int(n * self.scale)

    def add(self, panel):
        self.panels.append(panel)
        self.relayout()

    def remove(self, panel):
        if panel in self.panels:
            self.panels.remove(panel)
            self.relayout()

    def relayout(self):
        _, _, right, bottom = work_area()
        margin = self.px(12)
        y = bottom - margin
        for p in reversed(self.panels):
            p.win.update_idletasks()
            w, h = p.win.winfo_reqwidth(), p.win.winfo_reqheight()
            y -= h
            p.win.geometry(f"+{right - margin - w}+{y}")
            y -= self.px(8)


class Panel:
    def __init__(self, stack: Stack, timeout: float | None = None):
        self.stack = stack
        px = stack.px
        self.win = tk.Toplevel(stack.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=BG, highlightthickness=1, highlightbackground="#3a3a42")
        self.body = tk.Frame(self.win, bg=BG, padx=px(12), pady=px(10))
        self.body.pack(fill="both", expand=True)
        exclude_from_capture(self.win)
        self._timer = None
        self._timeout = timeout
        self._hover = False
        self.win.bind("<Enter>", lambda e: self._set_hover(True))
        self.win.bind("<Leave>", lambda e: self._set_hover(False))

    def show(self):
        self.stack.add(self)
        self._arm()

    def _set_hover(self, value):
        self._hover = value
        if not value:
            self._arm()

    def _arm(self, seconds=None):
        if self._timer:
            self.win.after_cancel(self._timer)
            self._timer = None
        seconds = seconds or self._timeout
        if seconds:
            self._timer = self.win.after(int(seconds * 1000), self._expire)

    def _expire(self):
        if self._hover:
            return  # se cerrará al salir el ratón
        self.close()

    def close(self):
        self.stack.remove(self)
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    # Widgets con el estilo común
    def label(self, parent, text, color=FG, size=10, bold=False, **kw):
        return tk.Label(parent, text=text, bg=BG, fg=color,
                        font=(FONT, size, "bold" if bold else "normal"), **kw)

    def button(self, parent, text, command, color=ACCENT):
        px = self.stack.px
        b = tk.Label(parent, text=text, bg=color, fg="white", cursor="hand2",
                     font=(FONT, 10, "bold"), padx=px(14), pady=px(5))
        b.bind("<Button-1>", lambda e: command())
        return b

    def close_x(self, parent):
        x = tk.Label(parent, text="✕", bg=BG, fg=MUTED, cursor="hand2", font=(FONT, 10))
        x.bind("<Button-1>", lambda e: self.close())
        return x


class SavePanel(Panel):
    """Miniatura + "Copiado al portapapeles" + botón Guardar."""

    def __init__(self, stack: Stack, image, on_save):
        super().__init__(stack, timeout=8)
        self.on_save = on_save
        px = stack.px

        thumb = image.copy()
        thumb.thumbnail((px(96), px(64)))
        self._thumb = ImageTk.PhotoImage(thumb)
        tk.Label(self.body, image=self._thumb, bg=BG).grid(row=0, column=0, rowspan=2,
                                                          padx=(0, px(10)))
        self.title = self.label(self.body, "Copiado al portapapeles", bold=True)
        self.title.grid(row=0, column=1, sticky="w")
        self.label(self.body, f"{image.width} × {image.height}", MUTED, 9).grid(
            row=1, column=1, sticky="w")
        self.save_btn = self.button(self.body, "Guardar", self._save)
        self.save_btn.grid(row=0, column=2, rowspan=2, padx=(px(12), px(4)))
        self.close_x(self.body).grid(row=0, column=3, sticky="ne")

    def _save(self):
        path = self.on_save()
        if path:
            self.title.configure(text="Guardado ✓")
            self.save_btn.configure(text="Abrir", bg="#3a3a42")
            self.save_btn.bind("<Button-1>", lambda e: _reveal(path))
            self._arm(3)


class RecordingPanel(Panel):
    """Indicador mientras se graba: ● REC 00:12  [Detener]."""

    def __init__(self, stack: Stack, with_audio: bool, on_stop):
        super().__init__(stack, timeout=None)
        px = stack.px
        self.t0 = time.monotonic()
        self.dot = self.label(self.body, "●", RED, 12)
        self.dot.grid(row=0, column=0)
        self.time = self.label(self.body, "REC 00:00", bold=True)
        self.time.grid(row=0, column=1, padx=(px(4), px(10)))
        self.label(self.body, "🔊" if with_audio else "🔇", MUTED, 10).grid(
            row=0, column=2, padx=(0, px(10)))
        self.stop_btn = self.button(self.body, "■ Detener", on_stop, RED)
        self.stop_btn.grid(row=0, column=3)
        self._tick()

    def _tick(self):
        s = int(time.monotonic() - self.t0)
        self.time.configure(text=f"REC {s // 60:02d}:{s % 60:02d}")
        self.dot.configure(fg=RED if s % 2 == 0 else BG)
        self._tick_id = self.win.after(500, self._tick)

    def processing(self):
        self.win.after_cancel(self._tick_id)
        self.dot.configure(fg=MUTED)
        self.time.configure(text="Procesando vídeo…")
        self.stop_btn.grid_remove()
        self.stack.relayout()


class Toast(Panel):
    """Aviso breve con botón de acción opcional."""

    def __init__(self, stack: Stack, title: str, text: str = "",
                 action: tuple[str, callable] | None = None, timeout: float = 5):
        super().__init__(stack, timeout=timeout)
        px = stack.px
        self.label(self.body, title, bold=True, justify="left").grid(
            row=0, column=0, sticky="w")
        if text:
            self.label(self.body, text, MUTED, 9, justify="left",
                       wraplength=px(300)).grid(row=1, column=0, sticky="w")
        if action:
            self.button(self.body, action[0], action[1]).grid(
                row=0, column=1, rowspan=2, padx=(px(12), px(4)))
        self.close_x(self.body).grid(row=0, column=2, sticky="ne")


def _reveal(path):
    import subprocess
    subprocess.Popen(["explorer", "/select,", str(path)])
