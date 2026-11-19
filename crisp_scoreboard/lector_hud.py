# -*- coding: utf-8 -*-
"""Lee el marcador de arriba a la derecha del HUD de League of Legends en un fotograma: el reloj, el K/D/A y los
subditos. HUD por defecto, video 16:9 a cualquier resolucion (por encima de 1080p se baja primero).

Metodo: recorte en gris a escala 1080p, varios umbrales, columnas encendidas = caracteres, y cada digito se compara
con plantillas generadas con la letra del HUD (recursos.py, se baja la primera vez). Gana el umbral cuyo peor digito
puntua mas alto. Si nada cuadra con seguridad, devuelve None: nunca un numero a medias.
"""
import os
import re

import cv2
import numpy as np

PLANTILLAS = None          # None = las genera recursos.plantillas_dir() con la letra del HUD (primera vez)

# cajas (x0, x1, y0, y1) a 1920x1080, HUD por defecto
CAJA_RELOJ = (1853, 1907, 3, 27)
CAJA_KDA = (1664, 1758, 3, 27)
CAJA_CS = (1777, 1836, 3, 27)
CAJA_EQUIPOS = (1545, 1665, 3, 27)

UMBRALES = (160, 150, 140, 130, 120, 110, 100, 90)
DIG_W_MIN, DIG_W_MAX = 3, 9
DIG_H_MIN, DIG_H_MAX = 8, 15
COLON_W_MAX = 3
GAP_MAX = 6
TPL_W, TPL_H = 14, 20
SCORE_MIN = 0.60
BARRA_FILA_MAX = 3
BARRA_PENDIENTE_MAX = -0.25

_plantillas = None


def plantillas():
    global _plantillas
    if _plantillas is None:
        from crisp_scoreboard import recursos
        carpeta = PLANTILLAS or recursos.plantillas_dir()
        _plantillas = {}
        for n in sorted(os.listdir(carpeta)):
            m = re.match(r"^(\d)(?:_\w+)?\.png$", n)
            img = cv2.imread(os.path.join(carpeta, n), cv2.IMREAD_GRAYSCALE) if m else None
            if img is not None and img.shape == (TPL_H, TPL_W):
                _plantillas.setdefault(int(m.group(1)), []).append(img.astype(np.float32))
    return _plantillas


def recorte(frame, caja):
    x0, x1, y0, y1 = caja
    h, w = frame.shape[:2]
    if w > 1920 or h > 1080:
        f = min(1920.0 / w, 1080.0 / h)
        frame = cv2.resize(frame, (int(round(w * f)), int(round(h * f))), interpolation=cv2.INTER_LANCZOS4)
        h, w = frame.shape[:2]
    sx, sy = w / 1920.0, h / 1080.0
    roi = frame[int(round(y0 * sy)):int(round(y1 * sy)), int(round(x0 * sx)):int(round(x1 * sx))]
    if roi.size == 0:
        return None
    if roi.ndim == 3:
        roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    if abs(sx - 1) > 0.01 or abs(sy - 1) > 0.01:
        roi = cv2.resize(roi, (x1 - x0, y1 - y0), interpolation=cv2.INTER_LINEAR)
    return roi


def _segmentos(b):
    cols = np.where(b.sum(axis=0) > 0)[0]
    if len(cols) == 0:
        return []
    segs, ini, prev = [], cols[0], cols[0]
    for x in cols[1:]:
        if x - prev >= 2:
            segs.append((ini, prev))
            ini = x
        prev = x
    return segs + [(ini, prev)]


def _alto(b, x0, x1):
    f = np.where(b[:, x0:x1 + 1].sum(axis=1) > 0)[0]
    return (int(f[0]), int(f[-1])) if len(f) else None


def _digito(gris, b, seg):
    bb = _alto(b, *seg)
    if bb is None:
        return None, 0.0
    h, w = gris.shape
    x0, x1 = max(0, seg[0] - 1), min(w - 1, seg[1] + 1)
    y0, y1 = max(0, bb[0] - 1), min(h - 1, bb[1] + 1)
    img = cv2.resize(gris[y0:y1 + 1, x0:x1 + 1], (TPL_W, TPL_H), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    mejor = (None, -1.0)
    for d, vs in plantillas().items():
        for t in vs:
            s = float(cv2.matchTemplate(img, t, cv2.TM_CCOEFF_NORMED)[0, 0])
            if s > mejor[1]:
                mejor = (d, s)
    return mejor


def _es_colon(b, seg):
    if seg[1] - seg[0] + 1 > COLON_W_MAX:
        return False
    filas = b[:, seg[0]:seg[1] + 1].sum(axis=1)
    on = np.where(filas > 0)[0]
    return len(on) >= 2 and bool((filas[on[0]:on[-1] + 1] == 0).any())


def _es_barra(b, seg):
    sub = b[:, seg[0]:seg[1] + 1]
    filas = [y for y in range(sub.shape[0]) if sub[y].any()]
    if len(filas) < DIG_H_MIN:
        return False
    anchos, centros = [], []
    for y in filas:
        xs = np.where(sub[y] > 0)[0]
        anchos.append(int(xs[-1] - xs[0] + 1))
        centros.append(float(xs.mean()))
    if max(anchos) > BARRA_FILA_MAX:
        return False
    return float(np.polyfit(np.array(filas, float), np.array(centros), 1)[0]) <= BARRA_PENDIENTE_MAX


def _texto(gris, umbral, con_colon=False):
    """(texto, peor puntuacion) con un umbral: digitos, '/' y ':'."""
    b = (gris > umbral).astype(np.uint8)
    segs = _segmentos(b)
    if not segs:
        return None, 0.0
    txt, peor = [], 1.0
    for a, c in zip(segs, segs[1:]):
        if not (0 < c[0] - a[1] <= GAP_MAX + 6):
            return None, 0.0
    for seg in segs:
        if con_colon and _es_colon(b, seg):
            txt.append(":")
            continue
        bb = _alto(b, *seg)
        if bb is None or not (DIG_H_MIN <= bb[1] - bb[0] + 1 <= DIG_H_MAX):
            return None, 0.0
        if not con_colon and _es_barra(b, seg):
            txt.append("/")
            continue
        if not (DIG_W_MIN <= seg[1] - seg[0] + 1 <= DIG_W_MAX):
            return None, 0.0
        d, s = _digito(gris, b, seg)
        if d is None or s < SCORE_MIN:
            return None, 0.0
        txt.append(str(d))
        peor = min(peor, s)
    return "".join(txt), peor


def _mejor(frame, caja, patron, con_colon=False):
    gris = recorte(frame, caja)
    if gris is None:
        return None
    mejor, ms = None, 0.0
    for u in UMBRALES:
        t, s = _texto(gris, u, con_colon)
        m = re.fullmatch(patron, t or "")
        if m and s > ms:
            mejor, ms = m, s
    return mejor


def reloj(frame):
    """Segundos de partida o None."""
    m = _mejor(frame, CAJA_RELOJ, r"(\d\d):([0-5]\d)", con_colon=True)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def kda(frame):
    m = _mejor(frame, CAJA_KDA, r"(\d{1,2})/(\d{1,2})/(\d{1,2})")
    return tuple(int(x) for x in m.groups()) if m else None


def subditos(frame):
    m = _mejor(frame, CAJA_CS, r"\d{1,4}")
    return int(m.group(0)) if m else None


def equipos(frame):
    """[izquierda, derecha, ¿el azul esta a la izquierda?] o None. Los dos numeros de colores (azul el tuyo, rojo el
    rival) se separan por color: el «VS» es dorado y no pasa ninguna mascara."""
    h, w = frame.shape[:2]
    if w != 1920:
        frame = cv2.resize(frame, (1920, int(round(h * 1920 / w))), interpolation=cv2.INTER_LANCZOS4)
    x0, x1, y0, y1 = CAJA_EQUIPOS
    roi = frame[y0:y1, x0:x1].astype(np.int32)
    b, g, r = roi[..., 0], roi[..., 1], roi[..., 2]
    gris = roi.max(axis=2).astype(np.uint8)
    out = {}
    for nombre, m in (("azul", (b > r + 25) & (b > 90)), ("rojo", (r > g + 45) & (r > b + 45) & (r > 110))):
        bi = m.astype(np.uint8)
        txt, xs = "", []
        for sg in _segmentos(bi):
            if sg[1] - sg[0] < 1:
                continue
            bb = _alto(bi, *sg)
            if bb is None or bb[1] - bb[0] + 1 < 4:
                continue
            if not (DIG_H_MIN <= bb[1] - bb[0] + 1 <= DIG_H_MAX + 2) or not (DIG_W_MIN <= sg[1] - sg[0] + 1 <= DIG_W_MAX + 1):
                return None
            d, sc = _digito(gris, bi, sg)
            if d is None or sc < 0.5:
                return None
            txt += str(d)
            xs.append(sg[0])
        if not txt or len(txt) > 2:
            return None
        out[nombre] = (int(txt), min(xs))
    izq, der = sorted(out.values(), key=lambda v: v[1])
    return [izq[0], der[0], bool(out["azul"][1] < out["rojo"][1])]
