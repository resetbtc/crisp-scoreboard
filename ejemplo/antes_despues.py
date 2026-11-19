# -*- coding: utf-8 -*-
"""La imagen del README (docs/antes-despues.png) con la partida INVENTADA del ejemplo, sin video de nadie:
  - arriba, «antes»: el marcador al tamano que tiene en un video a 1080p (375x26 px, con la letra y los iconos del juego)
    estirado al ancho de un vertical, como lo hace un editor;
  - abajo, «despues»: el mismo instante con crisp-scoreboard.
    python ejemplo/antes_despues.py
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from crisp_scoreboard import dibujo, recursos, partida as P  # noqa: E402

p = P.partida_lector(os.path.join(AQUI, "partida_inventada.jsonl"))
gt = 713.0
e = {"reloj": "11:53", "kda": list(p.kda_en(gt)), "equipos": p.equipos_en(gt), "cs": 90}
ANCHO = 864                                       # el ancho util de un vertical de 1080


def marcador_del_juego(e):
    """El marcador como sale en el juego a 1080p: 375x26, letra Beaufort, iconos a su tamano."""
    W, H, S = 375, 26, 4
    im = Image.new("RGBA", (W * S, H * S), (16, 24, 28, 255))
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(recursos.baja(recursos.LETRA_HUD, "beaufortforlol-bold.otf"), 15 * S)
    cy = H * S // 2
    ic = recursos.iconos()
    pegar = []

    def txt(x, t, col):
        d.text((x * S, cy), t, font=f, fill=col, anchor="lm")
        return x + d.textlength(t, font=f) / S

    def icono(x, n):
        pegar.append((n, int(x)))
        return x + ic[n].width * 0.8 + 3
    a, b, azul = e["equipos"]
    x = txt(22, str(a), (110, 160, 210) if azul else (200, 60, 60))
    x = icono(x + 3, "vs")
    txt(x, str(b), (200, 60, 60) if azul else (110, 160, 210))
    x = icono(135, "espada")
    txt(x, "{}/{}/{}".format(*e["kda"]), (220, 215, 200))
    x = icono(240, "subdito")
    txt(x, str(e["cs"]), (230, 205, 120))
    x = icono(300, "reloj")
    txt(x, e["reloj"], (220, 215, 200))
    im = im.resize((W, H), Image.LANCZOS)
    for n, x in pegar:
        i = ic[n].resize((round(ic[n].width * 0.8), round(ic[n].height * 0.8)), Image.LANCZOS)
        im.alpha_composite(i, (x, (H - i.height) // 2))
    return im


# la compresion de un video de directo (unos 7 Mbps a 1080p) antes de estirarlo, como le llega a un editor
import io  # noqa: E402
_b = io.BytesIO()
marcador_del_juego(e).convert("RGB").save(_b, "JPEG", quality=45)
antes = Image.open(_b).convert("RGBA").resize((ANCHO, round(26 * ANCHO / 375)), Image.BILINEAR)
despues = dibujo.dibuja_marcador(e, ANCHO, 60)
M = 28
rot = ImageFont.truetype(os.path.join(RAIZ, "fuentes", "OverusedGrotesk-Medium.ttf"), 26)
lienzo = Image.new("RGBA", (ANCHO + 2 * M, antes.height + despues.height + 4 * M + 40), (12, 14, 22, 255))
d = ImageDraw.Draw(lienzo)
d.text((M, M - 4), "Before: the game's scoreboard stretched for a vertical video / Antes", font=rot, fill=(170, 170, 185))
lienzo.alpha_composite(antes, (M, M + 30))
y = M + 30 + antes.height + M
d.text((M, y - 4), "After: crisp-scoreboard / Después", font=rot, fill=(170, 170, 185))
lienzo.alpha_composite(despues, (M - 2, y + 30))
os.makedirs(os.path.join(RAIZ, "docs"), exist_ok=True)
sal = os.path.join(RAIZ, "docs", "antes-despues.png")
lienzo.convert("RGB").save(sal, optimize=True)
print(sal)
