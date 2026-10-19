"""Manual de instrucciones de rcordr en PDF.

Estética de manual de videocámara de finales de los 80 / principios de los 90:
cuadernillo A5, papel crema, franjas arcoíris, cabeceras en bloques negros,
«Nombre de las partes» con llamadas numeradas, teclas dibujadas como botones,
lecturas tipo visor LCD y hoja de especificaciones.

    python scripts/manual.py [salida.pdf]
"""

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable, Frame,
                                KeepTogether, NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rcordr import __version__  # noqa: E402
from rcordr.config import DEFAULTS  # noqa: E402

MODEL = "RC-90"

# --- Fuentes (Windows) ---------------------------------------------------------
FONTS = Path(r"C:\Windows\Fonts")
for name, file in [("Body", "arial.ttf"), ("Body-Bold", "arialbd.ttf"),
                   ("Body-Italic", "ariali.ttf"), ("Heavy", "ariblk.ttf"),
                   ("Mono", "consola.ttf"), ("Mono-Bold", "consolab.ttf"),
                   ("Sym", "seguisym.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(FONTS / file)))
registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic",
                   boldItalic="Body-Bold")

# --- Colores de la época -------------------------------------------------------
PAPER = colors.HexColor("#F2ECDC")
PAPER_DARK = colors.HexColor("#E6DDC6")
INK = colors.HexColor("#1B1B1B")
GREY = colors.HexColor("#6E675B")
RULE = colors.HexColor("#B8AE96")
RAINBOW = [colors.HexColor(c) for c in ("#D7322B", "#EE7F22", "#F2BE2E", "#3E9B4F", "#2C64AE")]
REC_RED = colors.HexColor("#E5383B")
LCD_BG = colors.HexColor("#1D231F")
LCD_FG = colors.HexColor("#B9F2A1")
UI_BG = colors.HexColor("#1F1F23")
UI_ACCENT = colors.HexColor("#3D9CFF")

W, H = A5
MARGIN = 15 * mm
TOP = 19 * mm
BOTTOM = 15 * mm
CONTENT_W = W - 2 * MARGIN

# --- Estilos de texto ----------------------------------------------------------
BODY = ParagraphStyle("body", fontName="Body", fontSize=8.6, leading=11.6,
                      textColor=INK, alignment=TA_JUSTIFY, spaceAfter=4)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=7.4, leading=9.6, alignment=0)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=7.8, leading=10, alignment=0,
                      spaceAfter=0)
CELL_B = ParagraphStyle("cellb", parent=CELL, fontName="Body-Bold")
SUB = ParagraphStyle("sub", fontName="Heavy", fontSize=9.5, leading=12, textColor=INK,
                     spaceBefore=7, spaceAfter=3)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=10, bulletIndent=0,
                        bulletFontName="Body", bulletFontSize=5.5, alignment=0)
TOC_STYLE = ParagraphStyle("toc", fontName="Body-Bold", fontSize=9.5, leading=17,
                           textColor=INK)


def p(text, style=BODY):
    return Paragraph(text, style)


def bullets(*items):
    return [Paragraph(t, BULLET, bulletText="■") for t in items]


def note(text):
    """Nota con etiqueta negra y mano señalando, como en los manuales de la época."""
    return Paragraph(
        '<font name="Sym" size="10">☞</font> '
        '<font name="Body-Bold" backColor="#1B1B1B" color="#F2ECDC">&nbsp;NOTA&nbsp;</font>'
        f'&nbsp; {text}', ParagraphStyle("note", parent=BODY, alignment=0, spaceBefore=2))


# --- Elementos dibujados -------------------------------------------------------
def draw_r_icon(c, x, y, size, badge=True):
    """El icono de rcordr: «r» blanca con contorno y punto rojo abajo a la derecha."""
    if badge:
        c.setFillColor(INK)
        c.roundRect(x, y, size, size, size * 0.16, stroke=0, fill=1)
    c.saveState()
    t = c.beginText()
    t.setTextRenderMode(2)  # relleno + contorno
    c.setLineWidth(size * 0.035)
    c.setStrokeColor(INK)
    c.setFillColor(colors.white)
    fs = size * 1.0
    t.setFont("Heavy", fs)
    t.setTextOrigin(x + size * 0.17, y + size * 0.2)
    t.textOut("r")
    c.drawText(t)
    c.restoreState()
    rad = size * 0.14
    c.setFillColor(REC_RED)
    c.setStrokeColor(INK)
    c.setLineWidth(size * 0.035)
    c.circle(x + size * 0.76, y + size * 0.25, rad, stroke=1, fill=1)


def rainbow_bars(c, x, y, w, total_h):
    h = total_h / len(RAINBOW)
    for i, col in enumerate(RAINBOW):
        c.setFillColor(col)
        c.rect(x, y + (len(RAINBOW) - 1 - i) * h, w, h, stroke=0, fill=1)


def marker(c, x, y, n, r=6.2):
    """Llamada numerada: círculo negro con número blanco."""
    c.setFillColor(INK)
    c.setStrokeColor(PAPER)
    c.setLineWidth(1)
    c.circle(x, y, r, stroke=1, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Heavy", 7 if n < 10 else 6)
    c.drawCentredString(x, y - 2.5, str(n))


def color_bars(c, x, y, w, h):
    """Carta de ajuste de barras de color (la imagen típica de vídeo de la época)."""
    cols = ["#C0C0C0", "#C0C000", "#00C0C0", "#00C000", "#C000C0", "#C00000", "#0000C0"]
    bw = w / len(cols)
    top_h = h * 0.68
    for i, col in enumerate(cols):
        c.setFillColor(colors.HexColor(col))
        c.rect(x + i * bw, y + h - top_h, bw + 0.3, top_h, stroke=0, fill=1)
    rev = ["#0000C0", "#131313", "#C000C0", "#131313", "#00C0C0", "#131313", "#C0C0C0"]
    mid_h = h * 0.08
    for i, col in enumerate(rev):
        c.setFillColor(colors.HexColor(col))
        c.rect(x + i * bw, y + h - top_h - mid_h, bw + 0.3, mid_h, stroke=0, fill=1)
    low = [("#00214C", 1.25), ("#FFFFFF", 1.25), ("#32006A", 1.25), ("#131313", 3.25)]
    xx = x
    for col, k in low:
        c.setFillColor(colors.HexColor(col))
        c.rect(xx, y, bw * k + 0.3, h - top_h - mid_h, stroke=0, fill=1)
        xx += bw * k


class SectionHeader(Flowable):
    """Bloque negro con el número de sección en una casilla de color."""

    def __init__(self, num, title):
        super().__init__()
        self.num, self.title = num, title
        self.h = 8.5 * mm

    def wrap(self, aw, ah):
        self.w = aw
        return aw, self.h + 5

    def draw(self):
        c = self.canv
        c.setFillColor(INK)
        c.rect(0, 5, self.w, self.h, stroke=0, fill=1)
        c.setFillColor(RAINBOW[(self.num - 1) % len(RAINBOW)])
        c.rect(0, 5, self.h, self.h, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Heavy", 12)
        c.drawCentredString(self.h / 2, 5 + self.h / 2 - 4.3, str(self.num))
        c.setFont("Heavy", 10)
        c.drawString(self.h + 7, 5 + self.h / 2 - 3.6, self.title.upper())


class KeyCombo(Flowable):
    """Combinación de teclas dibujada como teclas físicas: [CTRL] + [SHIFT] + [1]."""

    def __init__(self, *keys, size=7.2):
        super().__init__()
        self.keys, self.size = keys, size
        self.kh = size * 2.3
        self.widths = [max(self.kh, pdfmetrics.stringWidth(k, "Body-Bold", size) + 9)
                       for k in keys]
        self.plus = pdfmetrics.stringWidth(" + ", "Body-Bold", size)

    def wrap(self, aw, ah):
        return sum(self.widths) + self.plus * (len(self.keys) - 1), self.kh + 2

    def draw(self):
        c, x = self.canv, 0
        for i, (k, w) in enumerate(zip(self.keys, self.widths)):
            c.setFillColor(colors.HexColor("#8C846F"))   # sombra / grosor de la tecla
            c.roundRect(x, 0, w, self.kh, 2.2, stroke=0, fill=1)
            c.setFillColor(colors.HexColor("#FBF8EE"))
            c.setStrokeColor(INK)
            c.setLineWidth(0.7)
            c.roundRect(x, 2, w, self.kh - 2, 2.2, stroke=1, fill=1)
            c.setFillColor(INK)
            c.setFont("Body-Bold", self.size)
            c.drawCentredString(x + w / 2, 2 + (self.kh - 2) / 2 - self.size * 0.35, k)
            x += w
            if i < len(self.keys) - 1:
                c.drawString(x, self.kh / 2 - self.size * 0.3, " + ")
                x += self.plus


class Lcd(Flowable):
    """Lectura de visor LCD de videocámara."""

    def __init__(self, left, right="", width=None, rec=True):
        super().__init__()
        self.left, self.right, self.width, self.rec = left, right, width, rec

    def wrap(self, aw, ah):
        self.w = self.width or aw
        return self.w, 24

    def draw(self):
        c = self.canv
        c.setFillColor(LCD_BG)
        c.roundRect(0, 0, self.w, 22, 4, stroke=0, fill=1)
        x = 10
        if self.rec:
            c.setFillColor(REC_RED)
            c.circle(x + 3, 11, 3.4, stroke=0, fill=1)
            x += 11
        c.setFillColor(LCD_FG)
        c.setFont("Mono-Bold", 10)
        c.drawString(x, 7.5, self.left)
        c.drawRightString(self.w - 10, 7.5, self.right)


class Warning(Flowable):
    """Recuadro de PRECAUCIÓN con triángulo de aviso."""

    def __init__(self, title, paras):
        super().__init__()
        self.title, self.paras = title, paras

    def wrap(self, aw, ah):
        self.w = aw
        self.inner = []
        h = 0
        for para in self.paras:
            _, ph = para.wrap(aw - 46, ah)
            self.inner.append((para, ph))
            h += ph + 3
        self.h = max(h + 24, 46)
        return aw, self.h + 4

    def draw(self):
        c = self.canv
        c.setFillColor(PAPER_DARK)
        c.setStrokeColor(INK)
        c.setLineWidth(1.2)
        c.rect(0, 4, self.w, self.h, stroke=1, fill=1)
        c.setFillColor(INK)
        c.rect(0, 4 + self.h - 15, self.w, 15, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Heavy", 8.5)
        c.drawString(32, 4 + self.h - 11, self.title.upper())
        # triángulo
        tx, ty = 8, 4 + self.h - 13.5
        c.setFillColor(colors.HexColor("#F2BE2E"))
        c.setStrokeColor(colors.white)
        c.setLineWidth(0.8)
        path = c.beginPath()
        path.moveTo(tx, ty)
        path.lineTo(tx + 16, ty)
        path.lineTo(tx + 8, ty + 12)
        path.close()
        c.drawPath(path, stroke=1, fill=1)
        c.setFillColor(INK)
        c.setFont("Heavy", 8)
        c.drawCentredString(tx + 8, ty + 2, "!")
        y = 4 + self.h - 20
        for para, ph in self.inner:
            y -= ph
            para.drawOn(c, 36, y)
            y -= 3


class Steps(Flowable):
    """Pasos numerados con números grandes en círculo negro."""

    def __init__(self, steps):
        super().__init__()
        self.steps = [Paragraph(s, ParagraphStyle("st", parent=BODY, spaceAfter=0))
                      for s in steps]

    def wrap(self, aw, ah):
        self.w = aw
        self.sizes = [max(para.wrap(aw - 26, ah)[1], 16) for para in self.steps]
        return aw, sum(self.sizes) + 6 * len(self.steps)

    def split(self, aw, ah):
        """Permite partir la lista entre páginas."""
        self.wrap(aw, ah)
        acc, n = 0, 0
        for s in self.sizes:
            if acc + s + 6 > ah:
                break
            acc += s + 6
            n += 1
        if n == 0 or n == len(self.steps):
            return []
        first = Steps([])
        first.steps = self.steps[:n]
        rest = Steps([])
        rest.steps = self.steps[n:]
        return [first, rest]

    def draw(self):
        c = self.canv
        y = sum(self.sizes) + 6 * len(self.steps)
        for i, (para, h) in enumerate(zip(self.steps, self.sizes), start=1):
            y -= h + 6
            c.setFillColor(INK)
            c.circle(8, y + h - 7, 8, stroke=0, fill=1)
            c.setFillColor(colors.white)
            c.setFont("Heavy", 9.5)
            c.drawCentredString(8, y + h - 10.4, str(getattr(para, "_num", i)))
            para.drawOn(c, 24, y + h - para.wrap(self.w - 26, 1000)[1] - 1.5)


def numbered_steps(*texts, start=1):
    s = Steps(list(texts))
    for i, para in enumerate(s.steps):
        para._num = start + i
    return s


class EditorDiagram(Flowable):
    """Esquema del editor con llamadas numeradas."""

    def wrap(self, aw, ah):
        self.w = aw
        return aw, 236

    def draw(self):
        c = self.canv
        x0, w = 8, self.w - 16
        top = 232
        # ventana
        c.setFillColor(UI_BG)
        c.setStrokeColor(INK)
        c.setLineWidth(1.2)
        c.roundRect(x0, 4, w, top - 4, 4, stroke=1, fill=1)
        c.setFillColor(colors.HexColor("#2C2C31"))
        c.rect(x0 + 1, top - 15, w - 2, 14, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#D6D6DE"))
        c.setFont("Body", 6.5)
        c.drawString(x0 + 8, top - 10.5, "rcordr — Editar vídeo")
        c.drawRightString(x0 + w - 8, top - 10.5, "—   □   ×")
        # vista previa
        px, pw = x0 + 10, w - 20
        ph = 118
        py = top - 20 - ph
        color_bars(c, px, py, pw, ph)
        c.setFillColor(colors.Color(0, 0, 0, alpha=0.55))
        c.circle(px + pw / 2, py + ph / 2, 14, stroke=0, fill=1)
        c.setFillColor(colors.white)
        tri = c.beginPath()
        tri.moveTo(px + pw / 2 - 4, py + ph / 2 - 7)
        tri.lineTo(px + pw / 2 - 4, py + ph / 2 + 7)
        tri.lineTo(px + pw / 2 + 8, py + ph / 2)
        tri.close()
        c.drawPath(tri, stroke=0, fill=1)
        # línea de tiempo
        ty = py - 18
        c.setFillColor(colors.HexColor("#2B2B31"))
        c.rect(px, ty, pw, 9, stroke=0, fill=1)
        sx, ex = px + pw * 0.18, px + pw * 0.74
        c.setFillColor(colors.HexColor("#24527F"))
        c.rect(sx, ty, ex - sx, 9, stroke=0, fill=1)
        c.setFillColor(UI_ACCENT)
        c.rect(sx - 4, ty - 2, 4, 13, stroke=0, fill=1)
        c.rect(ex, ty - 2, 4, 13, stroke=0, fill=1)
        hx = px + pw * 0.43
        c.setStrokeColor(colors.white)
        c.setLineWidth(1.4)
        c.line(hx, ty - 4, hx, ty + 13)
        # etiquetas
        ly = ty - 13
        c.setFillColor(colors.HexColor("#F2F2F2"))
        c.setFont("Body", 6)
        c.drawString(px, ly, "Inicio 00:02.0  ·  Fin 00:09.5  ·  7.5 s")
        c.setFillColor(colors.HexColor("#A0A0A8"))
        c.drawRightString(px + pw, ly, "00:04.6 / 00:12.8")
        # mezclador
        my = ly - 14
        c.setFillColor(colors.HexColor("#F2F2F2"))
        c.setFont("Body", 6)
        c.drawString(px, my, "Ordenador")
        c.drawString(px + pw * 0.5, my, "Micrófono")
        for sx0, frac in ((px + 34, 0.5), (px + pw * 0.5 + 34, 0.75)):
            c.setFillColor(colors.HexColor("#3A3A42"))
            c.rect(sx0, my, 64, 4.5, stroke=0, fill=1)
            c.setFillColor(colors.HexColor("#D6D6DE"))
            c.rect(sx0 + 64 * frac - 4, my - 1, 8, 6.5, stroke=0, fill=1)
            c.setFillColor(colors.HexColor("#A0A0A8"))
            c.drawString(sx0 + 70, my, f"{int(frac * 200)} %")
        # botones
        by = my - 22
        c.setFillColor(colors.HexColor("#3A3A42"))
        c.rect(px, by, 52, 13, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Body-Bold", 6)
        c.drawString(px + 7, by + 4.5, "► Reproducir")
        c.setStrokeColor(colors.HexColor("#F2F2F2"))
        c.setLineWidth(0.6)
        c.rect(px + 62, by + 3.5, 6, 6, stroke=1, fill=0)
        c.setFillColor(colors.HexColor("#F2F2F2"))
        c.setFont("Body", 6)
        c.drawString(px + 72, by + 4.5, "Quitar audio")
        c.setFillColor(UI_ACCENT)
        c.rect(px + pw - 40, by, 40, 13, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#3A3A42"))
        c.rect(px + pw - 88, by, 44, 13, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Body-Bold", 6)
        c.drawCentredString(px + pw - 20, by + 4.5, "Guardar")
        c.drawCentredString(px + pw - 66, by + 4.5, "Descartar")
        # llamadas
        marker(c, px + 14, py + ph - 14, 1)
        marker(c, px + pw * 0.92, ty + 4.5, 2)
        marker(c, sx - 2, ty + 19, 3)
        marker(c, ex + 2, ty + 19, 4)
        marker(c, hx, ty + 19, 5)
        marker(c, px + pw * 0.62, ly + 2.5, 6)
        marker(c, px + 34 + 100, my + 2.5, 7)   # a la derecha del «%»
        marker(c, px + pw * 0.5 + 34 + 100, my + 2.5, 8)
        marker(c, px + 26, by - 4, 9)
        marker(c, px + 92, by - 4, 10)
        marker(c, px + pw - 66, by - 4, 11)
        marker(c, px + pw - 20, by - 4, 12)


class TrayDiagram(Flowable):
    """Esquina inferior derecha de la pantalla mientras se graba."""

    def wrap(self, aw, ah):
        self.w = aw
        return aw, 128

    def draw(self):
        c, w = self.canv, self.w
        # escritorio
        c.setFillColor(colors.HexColor("#C9CDD3"))
        c.setStrokeColor(INK)
        c.setLineWidth(1.2)
        c.rect(0, 2, w, 124, stroke=1, fill=1)
        # zona que se graba
        c.setFillColor(colors.HexColor("#E9ECEF"))
        c.rect(18, 52, 120, 62, stroke=0, fill=1)
        color_bars(c, 24, 58, 108, 50)
        c.setStrokeColor(REC_RED)
        c.setLineWidth(2.2)
        c.rect(18, 52, 120, 62, stroke=1, fill=0)
        # barra de tareas
        c.setFillColor(colors.HexColor("#2A2A2F"))
        c.rect(0.6, 2.6, w - 1.2, 20, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Body", 6)
        c.drawRightString(w - 8, 14.5, "23:09")
        c.drawRightString(w - 8, 7, "19/10/2026")
        c.setFont("Body-Bold", 8)
        c.drawString(w - 98, 9, "^")
        draw_r_icon(c, w - 84, 6, 13, badge=False)
        # indicador REC
        rx, ry, rw, rh = w - 148, 44, 140, 22
        c.setFillColor(UI_BG)
        c.rect(rx, ry, rw, rh, stroke=0, fill=1)
        c.setFillColor(REC_RED)
        c.circle(rx + 10, ry + 11, 3.2, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Body-Bold", 7)
        c.drawString(rx + 17, ry + 8.5, "REC 00:12")
        c.setFillColor(REC_RED)
        c.rect(rx + rw - 52, ry + 4, 46, 14, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Body-Bold", 6.3)
        c.drawCentredString(rx + rw - 29, ry + 9, "■ Detener")
        c.setFillColor(colors.HexColor("#A0A0A8"))
        c.setFont("Body", 6)
        c.drawString(rx + 62, ry + 8.5, "PC  MIC")
        # llamadas
        marker(c, 18, 114, 1)
        marker(c, rx + 40, ry + rh + 3, 2)
        marker(c, rx + 72, ry + rh + 3, 3)
        marker(c, rx + rw - 29, ry + rh + 3, 4)
        marker(c, w - 77, 33, 5)
        marker(c, w - 96, 33, 6)


# --- Páginas ---------------------------------------------------------------------
def draw_cover(c, doc):
    c.saveState()
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)

    c.setFillColor(INK)
    c.setFont("Body-Bold", 8.5)
    c.drawString(MARGIN, H - 34, "MANUAL DE INSTRUCCIONES")
    c.setFillColor(GREY)
    c.setFont("Body", 6.8)
    c.drawString(MARGIN, H - 44, "OPERATING INSTRUCTIONS  ·  MODE D'EMPLOI  ·  BEDIENUNGSANLEITUNG")
    c.setFillColor(INK)
    c.rect(W - MARGIN - 22, H - 40, 22, 13, stroke=0, fill=1)
    c.setFillColor(PAPER)
    c.setFont("Heavy", 8)
    c.drawCentredString(W - MARGIN - 11, H - 36, "ES")

    # franjas diagonales arcoíris
    band, rise, y0 = 8.5, 70, H - 150
    for i, col in enumerate(RAINBOW):
        c.setFillColor(col)
        path = c.beginPath()
        b = y0 - i * band
        path.moveTo(0, b)
        path.lineTo(W, b + rise)
        path.lineTo(W, b + rise - band)
        path.lineTo(0, b - band)
        path.close()
        c.drawPath(path, stroke=0, fill=1)

    # marca
    by = H - 252
    draw_r_icon(c, MARGIN, by, 62)
    c.setFillColor(INK)
    c.setFont("Heavy", 50)
    c.drawString(MARGIN + 74, by + 9, "rcordr")
    c.setFont("Body-Bold", 8)
    c.drawString(MARGIN, by - 18, "SISTEMA DE CAPTURA DE PANTALLA  ·  IMAGEN Y VÍDEO")
    c.setFillColor(GREY)
    c.setFont("Body", 7.5)
    c.drawString(MARGIN, by - 30, f"Modelo {MODEL}   ·   Versión {__version__}   ·   Para Windows 10 / 11")

    # monitor de tubo con barras de color
    mx, my, mw, mh = W / 2 - 112, 128, 224, 150
    c.setFillColor(colors.HexColor("#3A372F"))
    path = c.beginPath()
    path.moveTo(mx + 70, my - 22)
    path.lineTo(mx + mw - 70, my - 22)
    path.lineTo(mx + mw - 86, my)
    path.lineTo(mx + 86, my)
    path.close()
    c.drawPath(path, stroke=0, fill=1)
    c.rect(mx + 56, my - 28, mw - 112, 7, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#D9D1BD"))
    c.setStrokeColor(INK)
    c.setLineWidth(1.4)
    c.roundRect(mx, my, mw, mh, 10, stroke=1, fill=1)
    sx, sy, sw, sh = mx + 14, my + 26, mw - 28, mh - 38
    c.setFillColor(LCD_BG)
    c.roundRect(sx - 3, sy - 3, sw + 6, sh + 6, 9, stroke=0, fill=1)
    color_bars(c, sx + 6, sy + 6, sw - 12, sh - 12)
    c.setStrokeColor(REC_RED)
    c.setLineWidth(1.8)
    c.rect(sx + 30, sy + 22, sw - 70, sh - 46, stroke=1, fill=0)
    c.setFillColor(colors.Color(0, 0, 0, alpha=0.6))
    c.rect(sx + 8, sy + sh - 22, 66, 13, stroke=0, fill=1)
    c.setFillColor(REC_RED)
    c.circle(sx + 15, sy + sh - 15.5, 3, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Mono-Bold", 8)
    c.drawString(sx + 21, sy + sh - 18.5, "REC 00:12")
    # mandos del monitor
    for i in range(6):
        c.setStrokeColor(colors.HexColor("#8C846F"))
        c.setLineWidth(1)
        c.line(mx + 18 + i * 5, my + 9, mx + 18 + i * 5, my + 18)
    c.setFillColor(colors.HexColor("#8C846F"))
    c.circle(mx + mw - 40, my + 13, 4, stroke=0, fill=1)
    c.circle(mx + mw - 27, my + 13, 4, stroke=0, fill=1)
    c.setFillColor(REC_RED)
    c.circle(mx + mw - 14, my + 13, 2, stroke=0, fill=1)

    # distintivos
    badges = ["MP4 · H.264", "HI-FI STEREO", "AUTO SYNC", "WINDOWS 10/11"]
    bw, gap = 74, (CONTENT_W - 4 * 74) / 3
    for i, txt in enumerate(badges):
        x = MARGIN + i * (bw + gap)
        c.setStrokeColor(INK)
        c.setLineWidth(1)
        c.roundRect(x, 74, bw, 15, 2, stroke=1, fill=0)
        c.setFillColor(INK)
        c.setFont("Heavy", 6.4)
        c.drawCentredString(x + bw / 2, 79, txt)

    c.setFillColor(GREY)
    c.setFont("Body-Italic", 7.2)
    c.drawCentredString(W / 2, 52, "Lea atentamente este manual antes de utilizar el programa")
    c.drawCentredString(W / 2, 42, "y consérvelo para futuras consultas.")
    rainbow_bars(c, 0, 0, W, 10)
    c.restoreState()


def draw_page(c, doc):
    c.saveState()
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    rainbow_bars(c, 0, H - 7, W, 7)
    c.setFillColor(GREY)
    c.setFont("Body-Bold", 6.5)
    c.drawString(MARGIN, H - 19, f"rcordr  ·  {MODEL}")
    c.setFont("Body", 6.5)
    c.drawRightString(W - MARGIN, H - 19, "MANUAL DE INSTRUCCIONES")
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.line(MARGIN, H - 23, W - MARGIN, H - 23)
    c.line(MARGIN, 26, W - MARGIN, 26)
    c.setFillColor(INK)
    c.rect(W - MARGIN - 30, 10, 15, 11, stroke=0, fill=1)
    c.setFillColor(PAPER)
    c.setFont("Heavy", 6.5)
    c.drawCentredString(W - MARGIN - 22.5, 13.3, "ES")
    c.setFillColor(INK)
    c.setFont("Heavy", 9)
    c.drawRightString(W - MARGIN, 12.5, str(doc.page))
    c.setFillColor(GREY)
    c.setFont("Body", 6)
    c.drawString(MARGIN, 13, f"Versión {__version__}")
    c.restoreState()


class Manual(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(str(path), pagesize=A5, title="rcordr — Manual de instrucciones",
                         author="rcordr", subject="Instalación, uso y opciones",
                         leftMargin=MARGIN, rightMargin=MARGIN, topMargin=TOP,
                         bottomMargin=BOTTOM)
        frame = Frame(MARGIN, BOTTOM + 14, CONTENT_W, H - TOP - BOTTOM - 22,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate("cover", [Frame(0, 0, W, H)], onPage=draw_cover),
            PageTemplate("page", [frame], onPage=draw_page),
        ])

    def afterFlowable(self, flowable):
        if isinstance(flowable, SectionHeader):
            self.notify("TOCEntry", (0, f"{flowable.num}.  {flowable.title}", self.page))


def table(rows, widths, header=True, bold_first=True):
    data = []
    for i, row in enumerate(rows):
        cells = []
        for j, cell in enumerate(row):
            if isinstance(cell, str):
                st = CELL_B if (header and i == 0) or (bold_first and j == 0) else CELL
                if header and i == 0:
                    st = ParagraphStyle("th", parent=CELL_B, textColor=colors.white)
                cell = Paragraph(cell, st)
            cells.append(cell)
        data.append(cells)
    t = Table(data, colWidths=[w * CONTENT_W for w in widths], repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
        ("BOX", (0, 0), (-1, -1), 1, INK),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), INK)]
    t.setStyle(TableStyle(style))
    return t


def legend(items):
    """Leyenda de llamadas numeradas en dos columnas."""
    half = (len(items) + 1) // 2
    rows = []
    for i in range(half):
        row = []
        for k in (i, i + half):
            if k < len(items):
                row += [Paragraph(f'<font name="Heavy">{k + 1}</font>', CELL),
                        Paragraph(items[k], CELL)]
            else:
                row += ["", ""]
        rows.append(row)
    t = Table(rows, colWidths=[20, CONTENT_W / 2 - 20] * 2)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 1),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    return t


def hotkey(combo):
    return KeyCombo(*[k.upper() for k in combo.split("+")])


# --- Contenido -------------------------------------------------------------------
def story():
    d = DEFAULTS
    s = [NextPageTemplate("page"), PageBreak()]

    # Índice
    s.append(Paragraph("ÍNDICE", ParagraphStyle("idx", fontName="Heavy", fontSize=16,
                                                textColor=INK, spaceAfter=10)))
    toc = TableOfContents(dotsMinLevel=0)
    toc.levelStyles = [TOC_STYLE]
    s.append(toc)
    s.append(Spacer(1, 14))
    s.append(Lcd("BIENVENIDO A rcordr", f"{MODEL}", rec=False))
    s.append(Spacer(1, 8))
    s.append(p("Gracias por elegir <b>rcordr</b>. Este programa permite capturar imágenes y "
               "grabar vídeos de la pantalla de su ordenador, con o sin sonido, y compartirlos "
               "al instante, por ejemplo por WhatsApp. Funciona desde un pequeño icono junto al "
               "reloj y se maneja con atajos de teclado."))

    # 1. Precauciones
    s += [PageBreak(), SectionHeader(1, "Precauciones")]
    s.append(Warning("Lea esto antes de empezar", [
        p("<b>Privacidad.</b> Con «sonido del ordenador» se graba todo lo que suena, también "
          "la voz de otras personas en una llamada. Avíseles antes de grabar.", SMALL),
        p("<b>Portapapeles.</b> Las capturas se copian automáticamente. Si tiene activado el "
          "historial del portapapeles (<b>Win+V</b>) o su sincronización, Windows guarda una "
          "copia de ellas.", SMALL),
        p("<b>No ejecute rcordr desde dentro del .zip.</b> Descomprímalo primero en una "
          "carpeta permanente.", SMALL),
    ]))
    s.append(Spacer(1, 6))
    s += bullets(
        "El programa <b>no está firmado digitalmente</b>: la primera vez Windows SmartScreen "
        "o el antivirus pueden mostrar un aviso. Vea «Preparativos».",
        "rcordr <b>no se conecta a Internet</b> ni envía datos: todo se queda en su ordenador.",
        "El marco rojo, el indicador REC y los paneles flotantes <b>no aparecen</b> en las "
        "capturas ni en los vídeos.",
        "Si usa unos <b>auriculares Bluetooth como micrófono</b> (AirPods, etc.), Windows los "
        "pasa a modo «manos libres» mientras graba y el sonido del ordenador pierde calidad.",
        "No mueva <b>rcordr.exe</b> fuera de su carpeta: necesita la carpeta <b>_internal</b> "
        "que lo acompaña.",
    )

    # 2. Características
    s += [Spacer(1, 4), SectionHeader(2, "Características")]
    s += bullets(
        "<b>Captura de imagen</b> de la zona que elija, copiada al portapapeles al momento y "
        "con botón para guardarla en PNG.",
        "<b>Grabación de vídeo</b> de una zona o de la pantalla completa, en MP4 compatible con "
        "WhatsApp, copiado al portapapeles como archivo.",
        "<b>Sonido del ordenador y micrófono</b>, mezclados y sincronizados automáticamente.",
        "<b>Editor</b> tras la grabación: recortar inicio y fin, mezclador de volumen y quitar "
        "el audio.",
        "<b>Portátil</b>: no requiere instalación, Python ni permisos de administrador.",
    )
    s.append(KeepTogether([p("<b>CONTENIDO DEL PAQUETE</b>", SUB), table([
        ["Elemento", "Descripción"],
        ["rcordr.exe", "El programa. Doble clic para abrirlo."],
        ["_internal", "Componentes necesarios (Python, ffmpeg, librerías). No los modifique."],
        ["Manual de instrucciones", "Este documento."],
    ], [0.35, 0.65])]))

    # 3. Nombre de las partes
    s += [Spacer(1, 10), CondPageBreak(230), SectionHeader(3, "Nombre de las partes")]
    s.append(p("<b>DURANTE LA GRABACIÓN</b> — esquina inferior derecha de la pantalla", SUB))
    s.append(TrayDiagram())
    s.append(Spacer(1, 4))
    s.append(legend([
        "Marco rojo: zona que se está grabando",
        "Tiempo de grabación (el punto rojo parpadea)",
        "Fuentes de audio activas: ordenador (PC) y micrófono (MIC)",
        "Botón Detener (o «Detener y editar»)",
        "Icono de rcordr: clic = captura; clic derecho = menú",
        "Mostrar iconos ocultos (si no ve el icono)",
    ]))
    s.append(CondPageBreak(250))
    s.append(p("<b>EDITOR DE VÍDEO</b> — se abre al usar «Grabar y editar»", SUB))
    s.append(EditorDiagram())
    s.append(Spacer(1, 4))
    s.append(legend([
        "Vista previa (clic = reproducir / pausa)",
        "Línea de tiempo (clic = ir a ese punto)",
        "Tirador de inicio del recorte",
        "Tirador de fin del recorte",
        "Posición de reproducción",
        "Inicio, fin y duración del recorte",
        "Volumen del sonido del ordenador",
        "Volumen del micrófono",
        "Reproducir / Pausa",
        "Quitar audio",
        "Descartar (borra el vídeo)",
        "Guardar",
    ]))

    # 4. Preparativos
    s += [PageBreak(), SectionHeader(4, "Preparativos")]
    s.append(p("<b>REQUISITOS</b>", SUB))
    s += bullets("Windows 10 (versión 2004 o posterior) o Windows 11, de 64 bits.",
                 "Unos 130 MB libres en el disco.",
                 "No necesita Python, conexión a Internet ni permisos de administrador.")
    s.append(p("<b>PUESTA EN MARCHA</b>", SUB))
    s.append(numbered_steps(
        "Haga clic derecho sobre el archivo <b>.zip</b> y elija <b>Extraer todo…</b>. "
        "Elija una carpeta permanente, por ejemplo <b>Documentos</b>.",
        "Abra la carpeta <b>rcordr</b> y haga doble clic en <b>rcordr.exe</b>.",
        "Si aparece «<b>Windows protegió su PC</b>», pulse <b>Más información</b> y después "
        "<b>Ejecutar de todas formas</b>. Solo ocurre la primera vez.",
        "Abajo a la derecha aparecerá el aviso «<b>rcordr está listo</b>» con los atajos, y el "
        "icono de rcordr junto al reloj. Si no lo ve, pulse <b>^</b> (iconos ocultos); puede "
        "arrastrarlo a la barra para tenerlo siempre a la vista.",
    ))
    s.append(p("<b>ACCESO DIRECTO Y BARRA DE TAREAS</b>", SUB))
    s.append(p("Clic derecho en <b>rcordr.exe</b> → <b>Mostrar más opciones</b> → "
               "<b>Anclar a la barra de tareas</b>, o <b>Enviar a</b> → <b>Escritorio (crear "
               "acceso directo)</b>."))
    s.append(p("<b>INICIAR CON WINDOWS</b> (opcional)", SUB))
    s.append(p("Pulse <b>Win+R</b>, escriba <b>shell:startup</b> y pulse Intro. Copie en esa "
               "carpeta un acceso directo a rcordr.exe."))
    s.append(note("Solo puede haber un rcordr abierto. Si lo abre de nuevo estando ya en marcha, "
                  "simplemente vuelve a mostrar el aviso con los atajos. Para cerrarlo: clic "
                  "derecho en el icono → <b>Salir</b>."))

    # 5. Funcionamiento básico / captura de imagen
    s += [PageBreak(), SectionHeader(5, "Atajos y captura de imagen")]
    s.append(p("<b>ATAJOS DE TECLADO</b>", SUB))
    s.append(table([
        ["Teclas", "Función"],
        [hotkey(d["hotkey_screenshot"]), "Captura de imagen"],
        [hotkey(d["hotkey_video"]), "Grabar vídeo / detener"],
        [hotkey(d["hotkey_video_edit"]), "Grabar vídeo y editar / detener"],
    ], [0.52, 0.48], bold_first=False))
    s.append(Spacer(1, 2))
    s.append(p("Funcionan desde cualquier programa. Se pueden cambiar en los ajustes (sección 8).",
               SMALL))
    s.append(p("<b>CAPTURA DE IMAGEN</b>", SUB))
    s.append(numbered_steps(
        f"Pulse {d['hotkey_screenshot'].upper()} (o haga clic en el icono de "
        "rcordr). La pantalla se congela y se oscurece.",
        "<b>Arrastre</b> para seleccionar la zona; verá su tamaño en píxeles. "
        "Un <b>clic simple</b> captura la pantalla completa. <b>Esc</b> o el clic derecho cancelan.",
        "La imagen ya está <b>copiada</b>: péguela donde quiera con <b>Ctrl+V</b>.",
        "Abajo a la derecha aparece una miniatura con el botón <b>Guardar</b>, que la guarda en "
        "PNG en <b>Imágenes\\rcordr</b>. Después el botón cambia a <b>Abrir</b>.",
    ))
    s.append(note("El panel con la miniatura se cierra solo a los 8 segundos, salvo que tenga "
                  "el ratón encima."))

    # 6. Grabación de vídeo
    s += [PageBreak(), SectionHeader(6, "Grabación de vídeo")]
    s.append(Lcd("REC 00:12", "PC  MIC"))
    s.append(Spacer(1, 6))
    s.append(numbered_steps(
        f"Pulse {d['hotkey_video'].upper()}. La pantalla se congela con un recuadro rojo.",
        "<b>Arrastre</b> para elegir la zona que quiere grabar, o haga <b>clic</b> para grabar la "
        "pantalla completa. <b>Esc</b> cancela.",
        "Empieza la grabación: la zona queda rodeada por un <b>marco rojo</b>, el icono de la "
        "bandeja parpadea y abajo a la derecha se ve el indicador <b>REC</b> con el tiempo.",
        f"Para terminar, pulse otra vez {d['hotkey_video'].upper()} o el botón <b>Detener</b>.",
        "Tras unos segundos («Procesando vídeo…») aparece «<b>Vídeo guardado</b>». El vídeo está "
        "en <b>Vídeos\\rcordr</b> y <b>copiado como archivo</b>: en WhatsApp Desktop o Web, "
        "péguelo en el chat con <b>Ctrl+V</b>.",
    ))
    s.append(p("<b>SONIDO</b>", SUB))
    s.append(p("Lo que se graba se elige en el menú del icono → <b>Configuración</b>: "
               "<b>sonido del ordenador</b> (activado de fábrica) y/o <b>micrófono</b>. Si están "
               "los dos, se mezclan en una sola pista, sincronizada con la imagen."))
    s.append(note("La zona mínima es de 32 × 32 píxeles. Los vídeos de pantallas grandes se "
                  "reducen a 1080 líneas para que ocupen poco."))

    # 7. Grabar y editar
    s += [Spacer(1, 4), CondPageBreak(200), SectionHeader(7, "Grabar y editar")]
    s.append(p(f"Con {d['hotkey_video_edit'].upper()} se graba igual que en la sección 6, pero al "
               "detener (con el mismo atajo o con «<b>Detener y editar</b>») se abre el "
               "<b>editor</b>. Vea el esquema de la sección 3."))
    s.append(table([
        ["Para…", "Haga esto"],
        ["Reproducir / pausar", "<b>Espacio</b>, el botón Reproducir o clic en la imagen"],
        ["Ir a un momento", "Clic o arrastre en la línea de tiempo"],
        ["Recortar", "Arrastre los <b>extremos azules</b> (el cursor cambia a ↔), o pulse "
                     "<b>I</b> / <b>O</b> para marcar inicio / fin donde está la reproducción"],
        ["Ajustar volúmenes", "Deslizadores <b>Ordenador</b> y <b>Micrófono</b> (0–200 %); "
                              "el cambio se oye al soltar"],
        ["Quitar el sonido", "Marque <b>Quitar audio</b>"],
        ["Guardar", "<b>Guardar</b> sustituye la grabación por la versión editada"],
        ["Borrar la grabación", "<b>Descartar</b> (pide un segundo clic para confirmar)"],
        ["Dejarla como está", "Cierre la ventana: conserva el vídeo completo"],
    ], [0.3, 0.7]))
    s.append(Spacer(1, 4))
    s.append(note("Los volúmenes que elija se recuerdan y se aplican también a las grabaciones "
                  f"con {d['hotkey_video'].upper()}. Recortar tarda unos segundos (se ve el "
                  "porcentaje); quitar el audio o cambiar volúmenes es casi instantáneo."))

    # 8. Ajustes
    s += [PageBreak(), SectionHeader(8, "Ajustes")]
    s.append(p("<b>MENÚ DEL ICONO</b> (clic derecho)", SUB))
    s.append(table([
        ["Opción", "Función"],
        ["Capturar imagen", "Igual que el atajo de captura"],
        ["Grabar vídeo / Detener", "Empieza o termina una grabación"],
        ["Grabar vídeo y editar", "Graba y abre el editor al terminar"],
        ["Abrir carpeta de…", "Abre Imágenes\\rcordr o Vídeos\\rcordr"],
        ["Configuración › Grabar sonido del ordenador", "Activa o desactiva el sonido del PC"],
        ["Configuración › Grabar micrófono", "Activa o desactiva el micrófono predeterminado "
                                              "de Windows (Configuración → Sonido → Entrada)"],
        ["Configuración › Editar atajos y carpetas", "Abre el archivo config.json"],
        ["Salir", "Cierra rcordr (si está grabando, guarda primero)"],
    ], [0.45, 0.55]))
    config_block = [p("<b>ARCHIVO config.json</b>", SUB)]
    config_block.append(p("Está en <b>%USERPROFILE%\\.rcordr\\config.json</b>. Para cambiarlo: "
                          "cierre rcordr (<b>Salir</b>), edítelo con el Bloc de notas y vuelva "
                          "a abrir rcordr."))
    config_block.append(table([
        ["Opción", "De fábrica", "Significado"],
        ["hotkey_screenshot", d["hotkey_screenshot"], "Atajo de captura de imagen"],
        ["hotkey_video", d["hotkey_video"], "Atajo de grabar / detener"],
        ["hotkey_video_edit", d["hotkey_video_edit"], "Atajo de grabar y editar"],
        ["screenshots_dir", "Imágenes\\rcordr", "Carpeta de las capturas"],
        ["videos_dir", "Vídeos\\rcordr", "Carpeta de los vídeos"],
        ["record_audio", str(d["record_audio"]).lower(), "Grabar sonido del ordenador"],
        ["record_mic", str(d["record_mic"]).lower(), "Grabar micrófono"],
        ["volume_system", str(d["volume_system"]), "Volumen del ordenador (1.0 = 100 %)"],
        ["volume_mic", str(d["volume_mic"]), "Volumen del micrófono"],
        ["fps", str(d["fps"]), "Fotogramas por segundo del vídeo"],
        ["max_video_height", str(d["max_video_height"]), "Altura máxima del vídeo (líneas)"],
    ], [0.36, 0.25, 0.39]))
    config_block.append(Spacer(1, 3))
    config_block.append(p(
        "<b>Formato de los atajos:</b> modificadores <b>ctrl</b>, <b>shift</b>, <b>alt</b>, "
        "<b>win</b> y una tecla (letra, número, <b>f1</b>…<b>f24</b>, <b>space</b>, "
        "<b>printscreen</b>, <b>pause</b>, <b>insert</b>, <b>home</b>…), separados por «+». "
        "Ejemplo: <b>ctrl+alt+f9</b>.", SMALL))
    s.append(KeepTogether(config_block))  # la tabla entera en una página

    # 9. Archivos y formatos
    s += [PageBreak(), SectionHeader(9, "Archivos y formatos")]
    s.append(table([
        ["Qué", "Dónde"],
        ["Capturas (PNG)", "Imágenes\\rcordr\\captura_AAAAMMDD_HHMMSS.png"],
        ["Vídeos (MP4)", "Vídeos\\rcordr\\video_AAAAMMDD_HHMMSS.mp4"],
        ["Ajustes", "%USERPROFILE%\\.rcordr\\config.json"],
        ["Registro de errores", "%USERPROFILE%\\.rcordr\\rcordr.log"],
        ["Temporales", "%USERPROFILE%\\.rcordr\\tmp (se vacía al abrir rcordr)"],
    ], [0.32, 0.68]))
    s.append(note("Si rcordr se cierra a mitad de una grabación, al volver a abrirlo recupera "
                  "el vídeo (sin sonido) como <b>video_recuperado_….mp4</b>."))
    s.append(p("<b>VÍDEO Y WHATSAPP</b>", SUB))
    s.append(p("Los vídeos se guardan en <b>MP4 con vídeo H.264 y audio AAC</b>, el formato "
               "nativo de WhatsApp en Android, iPhone, Web y Desktop: se envían y reproducen sin "
               "conversión. Ocupan unos <b>2–10 MB por minuto</b>, según el movimiento en "
               "pantalla. WhatsApp admite vídeos de hasta 2 GB (los recomprime al enviarlos)."))
    s.append(p("En el móvil no hay portapapeles compartido: envíe el vídeo desde WhatsApp Desktop "
               "o Web, o adjúntelo desde la carpeta <b>Vídeos\\rcordr</b>."))

    # 10. Solución de problemas
    s += [PageBreak(), SectionHeader(10, "Solución de problemas")]
    s.append(table([
        ["Síntoma", "Solución"],
        ["Aviso «Atajos no disponibles»", "Otra aplicación usa esa combinación. Cámbiela en "
                                          "config.json (sección 8)."],
        ["No veo el icono", "Pulse <b>^</b> junto al reloj (iconos ocultos)."],
        ["Al abrirlo no pasa nada", "Ya estaba abierto: busque el aviso abajo a la derecha o el "
                                    "icono junto al reloj."],
        ["El vídeo no tiene sonido", "Revise Configuración (sonido del ordenador / micrófono) y "
                                     "el dispositivo predeterminado de Windows. El aviso "
                                     "«Grabando sin…» indica que no se pudo abrir."],
        ["Sonido del PC de mala calidad", "Está usando unos auriculares Bluetooth como "
                                          "micrófono. Use otro micrófono."],
        ["Windows o el antivirus lo bloquean", "Más información → Ejecutar de todas formas. Si "
                                              "el antivirus lo pone en cuarentena, restáurelo y "
                                              "añada la carpeta como excepción."],
        ["Ctrl+V no pega el vídeo", "Use WhatsApp Desktop o Web; en el móvil, adjúntelo desde "
                                    "la carpeta."],
    ], [0.36, 0.64]))
    s.append(p("<b>DIAGNÓSTICO</b>", SUB))
    s.append(p("rcordr incluye una prueba automática que comprueba la ventana, el codificador de "
               "vídeo y el audio, grabando 2 segundos de una esquina de la pantalla (el vídeo de "
               "prueba se borra al terminar):"))
    s.append(numbered_steps(
        "Abra la carpeta de rcordr, haga clic en la barra de direcciones, escriba <b>cmd</b> y "
        "pulse Intro.",
        "Escriba <b>rcordr.exe --selftest</b> y pulse Intro.",
        "Aparece «Todo funciona correctamente» o el aviso de fallo. El detalle queda en "
        "<b>%USERPROFILE%\\.rcordr\\rcordr-selftest.log</b>.",
    ))

    # 11. Desinstalación
    s += [Spacer(1, 6), CondPageBreak(120), SectionHeader(11, "Desinstalación")]
    s.append(numbered_steps(
        "Clic derecho en el icono → <b>Salir</b>.",
        "Borre la carpeta <b>rcordr</b> y los accesos directos que haya creado (escritorio, "
        "barra de tareas, <b>shell:startup</b>).",
        "Opcional: borre <b>%USERPROFILE%\\.rcordr</b> (ajustes y registro).",
    ))
    s.append(p("Sus capturas y vídeos se conservan en Imágenes y Vídeos.", SMALL))

    # 12. Especificaciones
    s += [PageBreak(), SectionHeader(12, "Especificaciones")]
    spec = [
        ["Sistema", "Windows 10 (2004 o posterior) / Windows 11, 64 bits"],
        ["Formato de vídeo", "MP4 — H.264 High, 4:2:0"],
        ["Resolución", "La de la zona elegida, máx. 1080 líneas"],
        ["Fotogramas", f"{d['fps']} por segundo (ajustable)"],
        ["Audio", "AAC-LC estéreo, 48 kHz, 160 kbps"],
        ["Fuentes de audio", "Sonido del ordenador (WASAPI loopback) y micrófono"],
        ["Sincronización", "Automática, por marca de tiempo de cada fuente"],
        ["Formato de imagen", "PNG sin pérdida"],
        ["Edición", "Recorte al fotograma, mezcla 0–200 %, quitar audio"],
        ["Espacio en disco", "Aprox. 125 MB"],
        ["Conexión a Internet", "No necesaria"],
        ["Versión", f"{__version__} (modelo {MODEL})"],
    ]
    t = Table([[Paragraph(a, CELL_B), Paragraph(b, CELL)] for a, b in spec],
              colWidths=[0.36 * CONTENT_W, 0.64 * CONTENT_W])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, INK),
        ("LINEBELOW", (0, -1), (-1, -1), 1.2, INK),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
    ]))
    s.append(t)
    s.append(Spacer(1, 14))
    s.append(KeepTogether([
        Lcd("FIN", "rcordr", rec=False),
        Spacer(1, 8),
        Paragraph("El diseño y las especificaciones pueden cambiar sin previo aviso.",
                  ParagraphStyle("end", parent=SMALL, alignment=TA_CENTER, textColor=GREY,
                                 fontName="Body-Italic")),
    ]))
    return s


def build(path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    Manual(path).multiBuild(story())
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "manual.pdf"
    print(build(out))
