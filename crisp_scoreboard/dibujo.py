# -*- coding: utf-8 -*-
"""El marcador redibujado en el orden del juego (9 VS 9, espada K/D/A, subdito CS, reloj) a la resolucion que se pida,
y la fila del elo. Los numeros van con una letra libre (fuentes/); los iconos son los del juego tal cual, ampliados a
pixel entero sin suavizar, y como los emblemas se bajan de CommunityDragon a la cache: no van en el repositorio.
"""
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.environ.get("MARCADOR_CACHE", os.path.join(RAIZ, ".cache"))
EMBLEMAS = "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/images/ranked-emblem/emblem-{}.png"

ORO = (200, 170, 110)          # el dorado de los iconos del juego (C8AA6E)
CS_AMARILLO = (232, 205, 120)  # los subditos del HUD van en amarillo
AZUL, ROJO, BL, GR = (88, 170, 255), (255, 84, 84), (244, 244, 248), (190, 186, 210)
VE, CI = (80, 225, 130), (64, 242, 254)
FONDO = (10, 12, 24)
S4 = 4
LETRA = os.path.join(RAIZ, "fuentes", "OverusedGrotesk-Medium.ttf")


def _f(px):
    from PIL import ImageFont
    return ImageFont.truetype(LETRA, max(1, int(px)))


def _tarjeta(w, h):
    """Lienzo a 4x con la tarjeta de la franja (fondo y borde de oro, como _franja_morada)."""
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", ((w + 4) * S4, (h + 4) * S4), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, (w + 4) * S4 - 1, (h + 4) * S4 - 1), radius=9 * S4, fill=FONDO + (255,),
                        outline=ORO + (255,), width=2 * S4)
    return im, d


def dibuja_marcador(e, w, h):
    """La tarjeta del marcador (RGBA, w+4 x h+4) en el orden del juego: 9 VS 9, espada K/D/A, subdito CS, reloj.
    Los numeros, con nuestra letra; los iconos, los del juego ampliados a pixel entero (x k, vecino mas cercano)."""
    from PIL import Image
    from crisp_scoreboard import recursos
    ic = recursos.iconos()
    k = max(1, round(0.62 * h / 18.0))            # 18 px de alto en el juego -> a pixel entero
    im, d = _tarjeta(w, h)
    W4, H4 = (w + 4) * S4, (h + 4) * S4
    cy = H4 // 2
    big = 0.8 * h * S4
    pegar = []                                     # (icono, x en px finales, y centrada)

    def txt(x, t, col, size=big, dy=0):
        d.text((x, cy + dy), t, font=_f(size), fill=col, anchor="lm")
        return x + d.textlength(t, font=_f(size))

    def icono(x, nombre, hueco=0.08):
        i = ic[nombre]
        pegar.append((nombre, int(round(x / S4))))
        return x + (i.width * k + hueco * h) * S4
    cu = [W4 * i // 4 for i in range(5)]
    if e.get("equipos"):
        a, b, azul_es_mio = e["equipos"]
        x = cu[0] + 0.55 * h * S4
        x = txt(x, str(a), AZUL if azul_es_mio else ROJO)
        x = icono(x + 0.12 * h * S4, "vs", 0.12)
        txt(x, str(b), ROJO if azul_es_mio else AZUL)
    kk, dd, aa = e["kda"]
    x = icono(cu[1] + 0.45 * h * S4, "espada")
    txt(x, f"{kk}/{dd}/{aa}", BL)
    if e.get("cs") is not None:
        x = icono(cu[2] + 0.9 * h * S4, "subdito")
        txt(x, str(e["cs"]), CS_AMARILLO)
    x = icono(cu[3] + 0.55 * h * S4, "reloj")
    txt(x, e["reloj"], BL)
    out = im.resize((w + 4, h + 4), Image.LANCZOS)
    for nombre, x in pegar:
        i = ic[nombre].resize((ic[nombre].width * k, ic[nombre].height * k), Image.NEAREST)
        out.alpha_composite(i, (x, (h + 4 - i.height) // 2))
    return out


TIERS_ES = {"IRON": "HIERRO", "BRONZE": "BRONCE", "SILVER": "PLATA", "GOLD": "ORO", "PLATINUM": "PLATINO",
            "EMERALD": "ESMERALDA", "DIAMOND": "DIAMANTE", "MASTER": "MAESTRO", "GRANDMASTER": "GRAN MAESTRO",
            "CHALLENGER": "RETADOR"}


def emblema(tier):
    """El emblema del rango (de CommunityDragon, en la cache: nada de Riot va en el repositorio) o None."""
    t = str(tier or "").lower()
    if not re.fullmatch(r"[a-z]+", t):
        return None
    os.makedirs(CACHE, exist_ok=True)
    ruta = os.path.join(CACHE, f"emblem-{t}.png")
    if not os.path.isfile(ruta):
        try:
            import urllib.request
            # sin User-Agent de navegador CommunityDragon contesta 403
            req = urllib.request.Request(EMBLEMAS.format(t), headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                datos = r.read()
            if datos[:8] != b"\x89PNG\r\n\x1a\n":
                return None
            open(ruta + ".tmp", "wb").write(datos)
            os.replace(ruta + ".tmp", ruta)
        except Exception:  # noqa: BLE001
            return None
    from PIL import Image
    im = Image.open(ruta).convert("RGBA")
    return im.crop(im.getbbox())


def dibuja_elo(elo, w, h, w2, h2):
    """(tarjeta del elo, tarjeta de HOY) o None si falta el emblema."""
    from PIL import Image
    emb = emblema(elo.get("tier"))
    if emb is None:
        return None
    im, d = _tarjeta(w, h)
    H4 = (h + 4) * S4
    cy = H4 // 2
    eh = int(H4 * 0.86)
    ew = int(emb.width * eh / emb.height)
    e2 = emb.resize((ew, eh), Image.LANCZOS)
    im.alpha_composite(e2, (int(0.25 * h * S4), (H4 - eh) // 2))
    x = int(0.25 * h * S4) + ew + int(0.22 * h * S4)
    cola = "SOLOQ" if elo.get("cola") == "RANKED_SOLO_5x5" else "FLEX"
    if elo.get("cuenta"):
        cola += " · " + str(elo["cuenta"])
    d.text((x, cy - 0.3 * h * S4), cola, font=_f(0.24 * h * S4), fill=GR, anchor="lm")
    xr = (w + 4) * S4 - int(0.3 * h * S4)
    if elo.get("region"):
        pw = d.textlength(elo["region"], font=_f(0.27 * h * S4)) + 0.36 * h * S4
        d.rounded_rectangle((xr - pw, cy - 0.02 * h * S4, xr, cy + 0.4 * h * S4), radius=int(0.1 * h * S4),
                            outline=CI, width=max(2, int(0.04 * h * S4)))
        d.text((xr - pw / 2, cy + 0.19 * h * S4), elo["region"], font=_f(0.27 * h * S4), fill=CI, anchor="mm")
        xr -= pw + 0.15 * h * S4
    nombre = TIERS_ES.get(elo.get("tier"), str(elo.get("tier") or ""))
    alto = elo.get("tier") in ("MASTER", "GRANDMASTER", "CHALLENGER")
    if not alto and elo.get("division") and elo.get("division") != "NA":
        nombre += " " + str(elo["division"])
    fs = 0.5 * h * S4
    while d.textlength(f"{nombre} {elo.get('lp')} LP", font=_f(fs)) > xr - x and fs > 10:
        fs *= 0.94
    d.text((x, cy + 0.18 * h * S4), nombre + " ", font=_f(fs), fill=BL, anchor="lm")
    xl = x + d.textlength(nombre + " ", font=_f(fs))
    d.text((xl, cy + 0.18 * h * S4), str(elo.get("lp")), font=_f(fs), fill=CI, anchor="lm")
    xl += d.textlength(str(elo.get("lp")), font=_f(fs))
    d.text((xl + 0.06 * h * S4, cy + 0.26 * h * S4), "LP", font=_f(0.27 * h * S4), fill=GR, anchor="lm")
    a = im.resize((w + 4, h + 4), Image.LANCZOS)
    im, d = _tarjeta(w2, h2)
    H4 = (h2 + 4) * S4
    cy = H4 // 2
    x = 0.22 * h2 * S4
    d.text((x, cy - 0.3 * h2 * S4), "HOY", font=_f(0.24 * h2 * S4), fill=GR, anchor="lm")
    v, dd = int(elo.get("v") or 0), int(elo.get("d") or 0)
    x = x
    for t, c in ((f"{v}V ", VE), (f"{dd}D", ROJO)):
        d.text((x, cy + 0.16 * h2 * S4), t, font=_f(0.46 * h2 * S4), fill=c, anchor="lm")
        x += d.textlength(t, font=_f(0.46 * h2 * S4))
    return a, im.resize((w2 + 4, h2 + 4), Image.LANCZOS)
