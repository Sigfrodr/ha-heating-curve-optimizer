"""Génère brand/icon.png et icon@2x.png (flamme + courbe de chauffe)."""
import math
from pathlib import Path

from PIL import Image, ImageDraw

S = 2048  # dessin sur-échantillonné puis réduit (anticrénelage)
OUT = Path(__file__).resolve().parent.parent / "custom_components" / "heating_curve_optimizer" / "brand"
BLUE = (42, 120, 214, 255)
ORANGE = (235, 104, 52, 255)
YELLOW = (247, 170, 40, 255)


def flame(cx, cy, w, h, m=1.6, n=240):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = math.sin(t) * abs(math.sin(t / 2)) ** m
        y = math.cos(t)
        pts.append((cx + x * w, cy - y * h))
    return pts


def curve_term(d):
    return d * (1.4347 + 0.021 * d + 247.9e-6 * d * d)


img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Flamme (extérieure orange, cœur jaune)
d.polygon(flame(S * 0.46, S * 0.68, S * 0.26, S * 0.31), fill=ORANGE)
d.polygon(flame(S * 0.46, S * 0.81, S * 0.13, S * 0.17), fill=YELLOW)

# Courbe de chauffe stylisée (concave, monte vers la droite) au-dessus de la flamme
def disc(draw, x, y, r, fill):
    draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)


pts = []
for i in range(600):
    u = i / 599
    pts.append((S * (0.06 + 0.86 * u), S * (0.31 - 0.17 * u ** 1.9)))
r_line = S * 0.042
ring = S * 0.035
dot = pts[-1]
r_dot = S * 0.085

# anneau transparent pour détacher la courbe de la flamme
mask = Image.new("L", (S, S), 0)
md = ImageDraw.Draw(mask)
for x, y in pts:
    disc(md, x, y, r_line + ring, 255)
disc(md, *dot, r_dot + ring, 255)
img.putalpha(Image.composite(Image.new("L", (S, S), 0), img.getchannel("A"), mask))
d = ImageDraw.Draw(img)
for x, y in pts:
    disc(d, x, y, r_line, BLUE)
disc(d, *dot, r_dot, BLUE)

img = img.crop(img.getbbox())
side = max(img.size)
square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))

OUT.mkdir(parents=True, exist_ok=True)
square.resize((256, 256), Image.LANCZOS).save(OUT / "icon.png", optimize=True)
square.resize((512, 512), Image.LANCZOS).save(OUT / "icon@2x.png", optimize=True)
print("ok", sorted(p.name for p in OUT.iterdir()))
