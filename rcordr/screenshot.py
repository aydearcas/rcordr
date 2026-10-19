"""Captura de pantalla con selección de región (estilo Recortes de Windows)."""

import tkinter as tk

import mss
from PIL import Image, ImageEnhance, ImageTk

from .winapi import cursor_pos

MIN_DRAG = 4  # píxeles: por debajo, el clic cuenta como "monitor completo"


def grab_all() -> tuple[Image.Image, int, int]:
    """Captura todo el escritorio virtual. Devuelve (imagen, left, top)."""
    with mss.MSS() as sct:
        mon = sct.monitors[0]
        shot = sct.grab(mon)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        return img, mon["left"], mon["top"]


def monitor_at(x: int, y: int) -> dict:
    """Monitor (formato mss) que contiene el punto (x, y)."""
    with mss.MSS() as sct:
        for mon in sct.monitors[1:]:
            if (mon["left"] <= x < mon["left"] + mon["width"]
                    and mon["top"] <= y < mon["top"] + mon["height"]):
                return dict(mon)
        return dict(sct.monitors[1])


def monitor_under_cursor() -> dict:
    return monitor_at(*cursor_pos())


class RegionSelector:
    """Overlay a pantalla completa sobre una captura congelada.

    Arrastra para seleccionar, clic simple = monitor completo,
    Esc o clic derecho = cancelar. Llama a on_done(imagen | None).
    """

    def __init__(self, root: tk.Tk, on_done):
        self.on_done = on_done
        self.image, self.ox, self.oy = grab_all()
        self.start = None
        self.rect = None
        self._pending = False

        w, h = self.image.size
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry(f"{w}x{h}+{self.ox}+{self.oy}")

        self.canvas = tk.Canvas(self.win, width=w, height=h, highlightthickness=0,
                                cursor="crosshair", bg="black")
        self.canvas.pack()
        dim = ImageEnhance.Brightness(self.image).enhance(0.55)
        self._bg = ImageTk.PhotoImage(dim)
        self._crop_tk = None
        self.canvas.create_image(0, 0, image=self._bg, anchor="nw")
        self.crop_item = self.canvas.create_image(0, 0, anchor="nw")
        self.border = self.canvas.create_rectangle(0, 0, 0, 0, outline="#3d9cff",
                                                   width=2, state="hidden")
        self.label = self.canvas.create_text(0, 0, anchor="nw", fill="white",
                                             font=("Segoe UI", 10, "bold"),
                                             state="hidden")
        self._hint()

        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<ButtonPress-3>", lambda e: self._finish(None))
        self.win.bind("<Escape>", lambda e: self._finish(None))
        self.win.after(10, self._focus)

    def _focus(self):
        self.win.lift()
        self.win.focus_force()

    def _hint(self):
        mon = monitor_under_cursor()
        cx = mon["left"] - self.ox + mon["width"] // 2
        cy = mon["top"] - self.oy + 40
        self.hint = self.canvas.create_text(
            cx, cy, fill="white", font=("Segoe UI", 12),
            text="Arrastra para seleccionar · Clic = pantalla completa · Esc = cancelar")

    def _press(self, e):
        self.start = (e.x, e.y)
        self.canvas.delete(self.hint)

    def _drag(self, e):
        if not self.start:
            return
        x0, y0 = self.start
        self.rect = (min(x0, e.x), min(y0, e.y), max(x0, e.x), max(y0, e.y))
        if not self._pending:  # limita los redibujados a uno por ciclo de eventos
            self._pending = True
            self.win.after_idle(self._redraw)

    def _redraw(self):
        self._pending = False
        if not self.rect:
            return
        x0, y0, x1, y1 = self.rect
        if x1 - x0 < 1 or y1 - y0 < 1:
            return
        self._crop_tk = ImageTk.PhotoImage(self.image.crop(self.rect))
        self.canvas.itemconfigure(self.crop_item, image=self._crop_tk)
        self.canvas.coords(self.crop_item, x0, y0)
        self.canvas.coords(self.border, x0, y0, x1, y1)
        self.canvas.itemconfigure(self.border, state="normal")
        ly = y0 - 22 if y0 > 26 else y1 + 6
        self.canvas.coords(self.label, x0, ly)
        self.canvas.itemconfigure(self.label, text=f"{x1 - x0} × {y1 - y0}",
                                  state="normal")

    def _release(self, e):
        if not self.start:
            return
        x0, y0, x1, y1 = self.rect or (e.x, e.y, e.x, e.y)
        if x1 - x0 < MIN_DRAG or y1 - y0 < MIN_DRAG:
            mon = monitor_at(e.x + self.ox, e.y + self.oy)
            l, t = mon["left"] - self.ox, mon["top"] - self.oy
            box = (l, t, l + mon["width"], t + mon["height"])
        else:
            box = (x0, y0, x1, y1)
        self._finish(self.image.crop(box))

    def _finish(self, result):
        self.win.destroy()
        self.on_done(result)
