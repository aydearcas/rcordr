"""Icono de la app: una "r" minúscula blanca con un punto rojo abajo a la derecha."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WHITE = (255, 255, 255, 255)
OUTLINE = (20, 20, 24, 255)  # contorno fino para que se vea en barras claras
RED = (229, 56, 59, 255)

_FONTS = ["segoeuib.ttf", "arialbd.ttf", "seguisb.ttf"]


def _font(size: int):
    for name in _FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def make(size: int = 64, dot: bool = True) -> Image.Image:
    """Dibuja el icono a `size` px (se dibuja a 4x y se reduce para suavizar)."""
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    stroke = max(4, s // 26)
    # Ajusta el tamaño de letra para que la "r" ocupe ~90% del alto
    probe = _font(s)
    l, t, r, b = d.textbbox((0, 0), "r", font=probe)
    font = _font(int(s * (s * 0.90 - 2 * stroke) / (b - t)))
    l, t, r, b = d.textbbox((0, 0), "r", font=font, stroke_width=stroke)
    x = s * 0.40 - (l + r) / 2  # algo a la izquierda para dejar sitio al punto
    y = s * 0.48 - (t + b) / 2
    d.text((x, y), "r", font=font, fill=WHITE, stroke_width=stroke, stroke_fill=OUTLINE)

    if dot:
        rad = s * 0.16
        cx, cy = s * 0.80, s * 0.80
        d.ellipse((cx - rad - stroke, cy - rad - stroke, cx + rad + stroke, cy + rad + stroke),
                  fill=OUTLINE)
        d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=RED)

    return img.resize((size, size), Image.LANCZOS)


def save_ico(path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    make(256).save(path, format="ICO", sizes=[(n, n) for n in sizes],
                   append_images=[make(n) for n in sizes])
    return path


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "assets"
    save_ico(out / "rcordr.ico")
    make(256).save(out / "rcordr.png")
    print("Icono generado en", out)
