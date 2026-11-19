# -*- coding: utf-8 -*-
"""Lo que es de Riot no va en el repositorio: se baja de CommunityDragon la primera vez, a .cache/.

  - el atlas del HUD (game/assets/ux/lol/clarity_hudatlas.png): los iconos del marcador tal cual, VS, espada, subdito
    y reloj;
  - la letra del marcador (Beaufort for LoL Bold): con ella se generan las plantillas de los digitos que usa
    lector_hud. Medido contra plantillas recortadas de video real: 200 de 200 fotogramas leidos igual (reloj, K/D/A y
    subditos);
  - los emblemas de rango (dibujo.emblema).
"""
import os

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get("MARCADOR_CACHE", os.path.join(RAIZ, ".cache"))
CDRAGON = "https://raw.communitydragon.org/latest/game/assets/ux"
ATLAS = CDRAGON + "/lol/clarity_hudatlas.png"
LETRA_HUD = CDRAGON + "/fonts/beaufortforlol-bold.otf"
ICONOS = {"vs": (913, 309, 934, 324), "espada": (934, 305, 955, 323), "subdito": (978, 302, 999, 327),
          "reloj": (897, 448, 916, 466)}
TPL_W, TPL_H = 14, 20


def baja(url, nombre):
    """La ruta en la cache del fichero, bajandolo si no esta."""
    import urllib.request
    os.makedirs(CACHE, exist_ok=True)
    ruta = os.path.join(CACHE, nombre)
    if not os.path.isfile(ruta):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})   # sin el, CommunityDragon da 403
        with urllib.request.urlopen(req, timeout=30) as r:
            datos = r.read()
        with open(ruta + ".tmp", "wb") as f:
            f.write(datos)
        os.replace(ruta + ".tmp", ruta)
    return ruta


def iconos():
    """{nombre: imagen RGBA} recortados del atlas del juego, sin tocar."""
    from PIL import Image
    at = Image.open(baja(ATLAS, "clarity_hudatlas.png")).convert("RGBA")
    if at.size != (1024, 1024):
        raise RuntimeError("el atlas del juego ha cambiado de tamano: revisa las cajas de ICONOS")
    return {n: at.crop(c) for n, c in ICONOS.items()}


def plantillas_dir():
    """La carpeta con las plantillas de los digitos (0-9, varias por digito), generadas con la letra del HUD."""
    import cv2
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    sal = os.path.join(CACHE, "plantillas")
    if os.path.isdir(sal) and len(os.listdir(sal)) >= 60:
        return sal
    letra = baja(LETRA_HUD, "beaufortforlol-bold.otf")
    os.makedirs(sal, exist_ok=True)
    for d in range(10):
        for j, blur in enumerate((0.0, 0.6, 1.0)):
            for k, px in enumerate((11, 12)):          # alto de un digito del HUD a 1080p
                big = 8
                fnt = ImageFont.truetype(letra, px * big * 13 // 10)
                im = Image.new("L", (px * big * 2, px * big * 2), 0)
                ImageDraw.Draw(im).text((px * big // 2, px * big // 3), str(d), font=fnt, fill=255)
                im = im.crop(im.getbbox())
                w = max(1, round(im.width * px / im.height))
                im = im.resize((w, px), Image.LANCZOS)
                if blur:
                    im = im.filter(ImageFilter.GaussianBlur(blur))
                lien = Image.new("L", (w + 2, px + 2), 0)
                lien.paste(im, (1, 1))
                a = cv2.resize(np.array(lien), (TPL_W, TPL_H), interpolation=cv2.INTER_LINEAR)
                cv2.imwrite(os.path.join(sal, f"{d}_f{j}{k}.png"), a)
    return sal
