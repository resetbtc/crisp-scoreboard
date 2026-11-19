# -*- coding: utf-8 -*-
"""La partida detras de un clip y los numeros del marcador, segundo a segundo.

  - EL RELOJ sale del propio video (lector_hud): hora de partida = t + desfase, a una decima.
  - LA PARTIDA: la grabacion (grabador.py) cuyo K/D/A a esa hora es el que se lee en el HUD; si no hay grabacion, la
    timeline de match-v5 de Riot (necesita tu clave en RIOT_API_KEY). Dos candidatas que cuadran = no se dibuja.
  - K/D/A Y MUERTES POR EQUIPO: de la grabacion o de la timeline. Cada K/D/A leido en el HUD tiene que ser el de los
    datos (1,5 s de margen en los cambios).
  - SUBDITOS: la API los da de 10 en 10 y la timeline por minuto. El numero se lee del HUD y los datos lo acotan.
    Si no se lee bastante o no cuadra, la casilla no sale: nunca un numero aproximado.
"""
import glob
import json
import os
import re
import subprocess
import time

CACHE = os.environ.get("MARCADOR_CACHE", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache"))
FPS = 4.0
MARGEN_CAMBIO = 1.5
MIN_RELOJ = 0.6
MIN_CS = 0.7
MIN_EQUIPOS = 0.85
DIAS = 21


def muestras(video, ss, dur, fps=FPS, ffmpeg="ffmpeg"):
    """[(t, reloj|None, kda|None, cs|None)] del HUD del clip, t en segundos desde ss."""
    import numpy as np
    from crisp_scoreboard import lector_hud as L
    alto = 32
    r = subprocess.run([ffmpeg, "-v", "error", "-ss", f"{float(ss):.3f}", "-t", f"{float(dur):.3f}", "-i", str(video),
                        "-vf", f"fps={fps:g},scale=1920:1080:flags=lanczos,crop=1920:{alto}:0:0",
                        "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, timeout=600)
    tam = 1920 * alto * 3
    out = []
    for i in range(len(r.stdout) // tam):
        fr = np.zeros((1080, 1920, 3), dtype=np.uint8)
        fr[:alto] = np.frombuffer(r.stdout[i * tam:(i + 1) * tam], dtype=np.uint8).reshape(alto, 1920, 3)
        out.append((i / fps, L.reloj(fr), L.kda(fr), L.subditos(fr), L.equipos(fr)))
    return out


def desfase_reloj(ms):
    """(desfase, cuadran, con_reloj): hora de partida = t + desfase. None si el reloj no se lee o no cuadra.

    Cada lectura c en t dice c <= t + desfase < c + 1: se busca el desfase que cumplen mas lecturas (barrido) y se
    toma el centro del tramo."""
    lect = [(t, c) for t, c, *_ in ms if c is not None]
    if len(lect) < 4:
        return None, 0, len(lect)
    bordes = sorted([(c - t, 1) for t, c in lect] + [(c + 1 - t, -1) for t, c in lect])
    n = mejor = 0
    tramo = None
    for i, (x, d) in enumerate(bordes):
        n += d
        if n > mejor and i + 1 < len(bordes):
            mejor, tramo = n, (x, bordes[i + 1][0])
    if not tramo or mejor < max(4, MIN_RELOJ * len(lect)):
        return None, mejor, len(lect)
    return (tramo[0] + tramo[1]) / 2.0, mejor, len(lect)


# ------------------------------------------------------------------------------------------------ los datos de la partida
def _norma(n):
    return re.sub(r"[^a-z0-9]", "", str(n or "").split("#")[0].lower())


def _estructura(n):
    return bool(re.match(r"^(Turret|SRU_|Minion|Barracks|Obelisk)", str(n or "")))


class Partida:
    """Lo que hace falta de una partida, venga de la grabacion o de la timeline:
    kda [(gt, (k,d,a))], cs [(gt, n)] (paso 10 en la grabacion, por minuto en la timeline), muertes [(gt, equipo del
    que mata o None)], mi equipo, epoch(gt), de donde sale."""

    def __init__(self, fuente, ident, kda, cs, muertes, mio, t0_ms, paso_cs):
        self.fuente, self.ident = fuente, ident
        self.kda, self.cs, self.muertes, self.mio = kda, cs, muertes, mio
        self.t0_ms, self.paso_cs = t0_ms, paso_cs
        self.cs_de, self.campeon, self.cuenta, self.kda_de = fuente, None, "", ""

    @staticmethod
    def _en(serie, gt, defecto=None):
        v = defecto
        for g, x in serie:
            if g > gt:
                break
            v = x
        return v

    def kda_en(self, gt):
        return self._en(self.kda, gt, (0, 0, 0))

    def kda_cerca(self, gt, margen=MARGEN_CAMBIO):
        return {self.kda_en(gt - margen), self.kda_en(gt), self.kda_en(gt + margen)}

    def equipos_en(self, gt):
        """(los del lado azul, los del lado rojo, ¿el suyo es el azul?) como el HUD: a la izquierda SIEMPRE el lado azul
        del mapa y el color dice cual es el tuyo (azul) y cual el rival (rojo): jugando en el lado rojo, lo tuyo va a la
        derecha y en azul. None si alguna muerte no se sabe de quien es."""
        a = b = 0
        for g, eq in self.muertes:
            if g > gt:
                break
            if eq is None:
                return None
            if eq in ("ORDER", 100):
                a += 1
            else:
                b += 1
        return [a, b, self.mio in ("ORDER", 100)]

    def cs_acota(self, gt, n):
        """¿cuadra la lectura n del HUD con los datos a esa hora?"""
        if not self.paso_cs:
            return False
        if self.paso_cs == 10:
            vals = {self._en(self.cs, gt + d, 0) for d in (-MARGEN_CAMBIO, 0.0, MARGEN_CAMBIO)}
            return any(v <= n <= v + 9 for v in vals)
        # los fotogramas de la timeline que rodean gt (llegan a xx:00,6, no al minuto justo)
        lo = self._en(self.cs, gt, 0)
        hi = next((v for g, v in self.cs if g >= gt), None)
        return lo <= n <= (hi if hi is not None else lo)

    def epoch(self, gt):
        return (self.t0_ms + gt * 1000.0) / 1000.0


_LINEA = re.compile(r'"k":\s*"(m|r|e|todo|ini)"')


def _resumen_lector(fichero):
    """La grabacion en pequeno (cacheada por nombre y tamano): lo que usa Partida."""
    os.makedirs(CACHE, exist_ok=True)
    clave = os.path.join(CACHE, f"{os.path.basename(fichero)}.{os.path.getsize(fichero)}.v4.json")
    if os.path.isfile(clave):
        try:
            return json.load(open(clave, encoding="utf-8"))
        except (OSError, ValueError):
            pass
    kda, cs, evs, equipo, yo, t0, campeon, cuenta = [], [], [], {}, set(), None, None, ""
    with open(fichero, encoding="utf-8", errors="replace") as fh:
        for linea in fh:
            if not _LINEA.search(linea):
                continue
            try:
                d = json.loads(linea)
            except ValueError:
                continue
            k = d.get("k")
            if k == "ini":
                yo |= {_norma(n) for n in (d.get("nombres") or []) + [d.get("riotId")] if n}
                cuenta = d.get("riotId") or ""
            elif k == "todo":
                for p in ((d.get("d") or {}).get("allPlayers") or []):
                    # con el modo streamer los nombres llegan vacios y los eventos traen el CAMPEON
                    for c in ("riotIdGameName", "summonerName", "riotId", "championName"):
                        if p.get(c):
                            equipo[_norma(p[c])] = p.get("team")
                    if campeon is None and any(_norma(p.get(c)) in yo for c in ("riotIdGameName", "summonerName", "riotId")
                                               if p.get(c)):
                        campeon = p.get("championName")
            elif k in ("m", "r") and d.get("gt") is not None:
                g = float(d["gt"])
                if t0 is None and d.get("t") and g > 1:
                    t0 = float(d["t"]) - g * 1000.0
                if "kda" in d and (not kda or kda[-1][1] != d["kda"]):
                    kda.append((g, d["kda"]))
                if "cs" in d and (not cs or cs[-1][1] != d["cs"]):
                    cs.append((g, d["cs"]))
            elif k == "e":
                ev = d.get("ev") or {}
                if ev.get("EventName") == "ChampionKill":
                    evs.append((float(ev.get("EventTime") or d.get("gt") or 0), ev.get("KillerName"),
                                ev.get("VictimName"), ev.get("Assisters") or []))
    if campeon:
        yo.add(_norma(campeon))
    mio = next((equipo[n] for n in yo if n in equipo), None)
    # SU KDA DE LOS ChampionKill: llevan la hora exacta. playerscores llega ~2 s tarde y a veces no llega. Si hay
    # playerscores, los eventos mandan solo cuando su total es el mismo; si no, playerscores.
    k = dd = a = 0
    ev_kda = [(0.0, [0, 0, 0])]
    for g, kil, vic, asi in sorted(evs, key=lambda x: x[0]):
        k += _norma(kil) in yo
        dd += _norma(vic) in yo
        a += any(_norma(x) in yo for x in asi)
        if [k, dd, a] != ev_kda[-1][1]:
            ev_kda.append((g, [k, dd, a]))
    if not kda:
        kda, kda_de = ev_kda, "eventos"
    elif ev_kda[-1][1] == kda[-1][1]:
        kda, kda_de = ev_kda, "eventos (iguales al total de playerscores)"
    else:
        kda_de = "playerscores"
    muertes = []
    for g, killer, _v, _a in sorted(evs, key=lambda x: x[0]):
        eq = equipo.get(_norma(killer))
        if eq is None and _estructura(killer):
            continue                  # ejecutado por torre o subditos: no suma a ningun equipo en el HUD
        muertes.append((g, eq))
    r = {"kda": kda, "cs": cs, "muertes": muertes, "mio": mio, "t0_ms": t0, "campeon": campeon, "kda_de": kda_de,
         "cuenta": cuenta}
    try:
        json.dump(r, open(clave, "w", encoding="utf-8"))
    except OSError:
        pass
    return r


def partida_lector(fichero):
    r = _resumen_lector(fichero)
    if not r["kda"] or r["t0_ms"] is None:
        return None
    p = Partida("grabacion", os.path.basename(fichero), [(g, tuple(x)) for g, x in r["kda"]], r["cs"],
                [tuple(x) for x in r["muertes"]], r["mio"], r["t0_ms"], 10 if r["cs"] else None)
    p.campeon, p.kda_de, p.cuenta = r.get("campeon"), r.get("kda_de"), r.get("cuenta") or ""
    return p


def partida_timeline(tl, info, puuid):
    """Partida desde la timeline y el detalle de match-v5 (los json tal cual)."""
    parts = (tl.get("info") or {}).get("participants") or (tl.get("metadata") or {}).get("participants") or []
    pid = None
    for p in parts:
        if isinstance(p, dict) and p.get("puuid") == puuid:
            pid = p.get("participantId")
    if pid is None:
        ps = (tl.get("metadata") or {}).get("participants") or []
        pid = ps.index(puuid) + 1 if puuid in ps else None
    if pid is None:
        return None
    mio = 100 if pid <= 5 else 200
    k = d = a = 0
    kda, cs, muertes = [(0.0, (0, 0, 0))], [], []
    for fr in (tl.get("info") or {}).get("frames") or []:
        pf = (fr.get("participantFrames") or {}).get(str(pid)) or {}
        cs.append((fr.get("timestamp", 0) / 1000.0, int(pf.get("minionsKilled", 0)) + int(pf.get("jungleMinionsKilled", 0))))
        for e in fr.get("events") or []:
            if e.get("type") != "CHAMPION_KILL":
                continue
            g = e.get("timestamp", 0) / 1000.0
            kil, vic, asi = e.get("killerId", 0), e.get("victimId", 0), e.get("assistingParticipantIds") or []
            if kil and kil > 0:
                muertes.append((g, 100 if kil <= 5 else 200))
            if kil == pid:
                k += 1
            if vic == pid:
                d += 1
            if pid in asi:
                a += 1
            if (k, d, a) != kda[-1][1]:
                kda.append((g, (k, d, a)))
    t0 = (info.get("info") or {}).get("gameStartTimestamp") or (info.get("info") or {}).get("gameCreation")
    p = Partida("timeline", (info.get("metadata") or {}).get("matchId", ""), kda, cs, muertes, mio, float(t0 or 0), 60)
    yo = next((x for x in (info.get("info") or {}).get("participants") or [] if x.get("puuid") == puuid), {})
    p.campeon = yo.get("championName")
    p.cuenta = f"{yo.get('riotIdGameName')}#{yo.get('riotIdTagline')}" if yo.get("riotIdGameName") else ""
    return p


def grabaciones(carpeta, epoch=None):
    """Las grabaciones que pueden ser: las de ese dia (+-1) si se sabe la hora; si no, las de DIAS."""
    fs = glob.glob(os.path.join(carpeta, "*.jsonl"))
    if epoch == -1:
        return []
    if epoch:
        dias = {time.strftime("%Y-%m-%d", time.localtime(epoch + d * 86400)) for d in (-1, 0, 1)}
        return sorted(f for f in fs if os.path.basename(f)[:10] in dias)
    lim = time.time() - DIAS * 86400
    return sorted(f for f in fs if os.path.getmtime(f) >= lim)


def cuadra(p, ms, desfase):
    """(ok, motivo): todos los KDA leidos en el HUD son los de la partida a esa hora."""
    vistos = [(t + desfase, k) for t, _c, k, *_ in ms if k is not None]
    if len(vistos) < 3:
        return False, f"solo {len(vistos)} KDA legibles en el HUD"
    malos = [(round(g), k) for g, k in vistos if tuple(k) not in p.kda_cerca(g)]
    if malos:
        return False, f"{len(malos)} de {len(vistos)} KDA no cuadran (p. ej. {malos[0]})"
    return True, f"{len(vistos)} KDA del HUD iguales a los de {p.fuente}"


def busca_partida(ms, desfase, carpeta=None, epoch=None, candidatas_timeline=()):
    """(Partida, motivo) o (None, motivo). Primero las grabaciones; si ninguna grabacion cuadra, las de la timeline."""
    buenas = []
    for f in (grabaciones(carpeta, epoch) if carpeta else []):
        try:
            p = partida_lector(f)
        except Exception:  # noqa: BLE001
            continue
        if p and cuadra(p, ms, desfase)[0]:
            buenas.append(p)
    if len(buenas) == 1:
        return buenas[0], "grabacion " + os.path.basename(buenas[0].ident)
    if len(buenas) > 1:
        return None, f"{len(buenas)} grabaciones cuadran: no se sabe cual es"
    for p in candidatas_timeline:
        if p and cuadra(p, ms, desfase)[0]:
            buenas.append(p)
    if len(buenas) == 1:
        return buenas[0], "timeline de Riot " + buenas[0].ident
    if len(buenas) > 1:
        return None, f"{len(buenas)} partidas de la timeline cuadran: no se sabe cual es"
    return None, "ninguna grabacion ni timeline cuadra con el HUD del clip"


# ------------------------------------------------------------------------------------------------ Riot (match-v5)
def _riot(url, key):
    import urllib.request
    req = urllib.request.Request(url, headers={"X-Riot-Token": key, "User-Agent": "crisp-scoreboard"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _guarda_riot(nombre, datos):
    try:
        os.makedirs(CACHE, exist_ok=True)
        json.dump(datos, open(os.path.join(CACHE, nombre), "w", encoding="utf-8"))
    except OSError:
        pass


def _match(mid, key):
    """(detalle, timeline) de match-v5, cacheados (una partida acabada no cambia)."""
    out = []
    for que, url in (("info", f"https://europe.api.riotgames.com/lol/match/v5/matches/{mid}"),
                     ("tl", f"https://europe.api.riotgames.com/lol/match/v5/matches/{mid}/timeline")):
        ruta = os.path.join(CACHE, f"{mid}.{que}.json")
        if os.path.isfile(ruta):
            out.append(json.load(open(ruta, encoding="utf-8")))
            continue
        d = _riot(url, key)
        _guarda_riot(f"{mid}.{que}.json", d)
        out.append(d)
    return out


def cs_de_timeline(p, key):
    """Si la grabacion no trae subditos (sin playerscores), los de la timeline de esa partida, por minuto."""
    if not key or not p.campeon:
        return False
    info, tl = _match(p.ident, key)
    pid = next((x.get("participantId") for x in (info.get("info") or {}).get("participants") or []
                if _norma(x.get("championName")) == _norma(p.campeon)), None)
    if pid is None:
        return False
    p.cs = [(fr.get("timestamp", 0) / 1000.0,
             int(((fr.get("participantFrames") or {}).get(str(pid)) or {}).get("minionsKilled", 0))
             + int(((fr.get("participantFrames") or {}).get(str(pid)) or {}).get("jungleMinionsKilled", 0)))
            for fr in (tl.get("info") or {}).get("frames") or []]
    p.paso_cs, p.cs_de = 60, f"timeline de Riot {p.ident}"
    return True


def candidatas_riot(epoch_a, epoch_b, key, cuentas):
    """Las partidas de esas cuentas (Riot ID "Nombre#TAG") que se jugaban entre epoch_a y epoch_b, como Partida de la timeline."""
    import urllib.parse
    out = []
    for rid in cuentas:
        nombre, tag = rid.split("#", 1)
        try:
            acc = _riot("https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
                        f"{urllib.parse.quote(nombre)}/{urllib.parse.quote(tag)}", key)
            puuid = acc["puuid"]
            ids = _riot(f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?"
                        f"startTime={int(epoch_a - 3 * 3600)}&endTime={int(epoch_b + 3 * 3600)}&count=20", key)
        except Exception:  # noqa: BLE001
            continue
        for mid in ids:
            try:
                info, tl = _match(mid, key)
            except Exception:  # noqa: BLE001
                continue
            i = info.get("info") or {}
            ini = (i.get("gameStartTimestamp") or 0) / 1000.0
            fin = (i.get("gameEndTimestamp") or 0) / 1000.0 or ini + float(i.get("gameDuration") or 0)
            if fin < epoch_a - 600 or ini > epoch_b + 600:
                continue
            p = partida_timeline(tl, info, puuid)
            if p:
                p.cs_de = f"timeline de Riot {mid}"
                out.append(p)
    return out


# ------------------------------------------------------------------------------------------------ los numeros del clip
def comprueba_equipos(p, ms, desfase):
    """(ok, motivo): las muertes por equipo de los datos son las que marca el HUD del clip donde se leen."""
    vistos = [(t + desfase, x[1]) for t, _c, _k, *x in ms if len(x) > 1 and x[1] is not None]
    if len(vistos) < 3:
        return False, f"solo {len(vistos)} lecturas de las muertes por equipo en el HUD"
    malos = [(_mmss(g), e) for g, e in vistos
             if list(e) not in [p.equipos_en(g + d) for d in (-MARGEN_CAMBIO, 0.0, MARGEN_CAMBIO)]]
    # el HUD parpadea cuando cae una muerte y el lector lee mal un segundo («36» como «30»); un dato equivocado (el lado al reves, otra partida) no cuadra en NINGUNA. Basta con el 85 %.
    if len(malos) > (1 - MIN_EQUIPOS) * len(vistos):
        return False, f"{len(malos)} de {len(vistos)} lecturas del HUD no cuadran (p. ej. {malos[0]})"
    return True, f"{len(vistos) - len(malos)} de {len(vistos)} lecturas del HUD iguales" + (
        f" (las otras, el HUD parpadeando: p. ej. {malos[0]})" if malos else "")


def serie_cs(p, ms, desfase):
    """[(t, n)] con el CS del HUD donde cambia, o (None, motivo) si la casilla no debe salir."""
    con = [(t, x[0]) for t, _c, _k, *x in ms]
    legibles = [(t, s) for t, s in con if s is not None]
    if len(legibles) < MIN_CS * len(con):
        return None, f"subditos legibles en {len(legibles)} de {len(con)} muestras"
    if not p.paso_cs:
        return None, "ni la grabacion ni la timeline dan subditos para acotar la lectura"
    prev = -1
    serie = []
    for t, s in legibles:
        if not p.cs_acota(t + desfase, s):
            return None, f"la lectura {s} a las {_mmss(t + desfase)} no cuadra con {p.cs_de}"
        if s < prev:
            return None, f"los subditos bajan ({prev} -> {s})"
        if s != prev:
            serie.append((t, s))
            prev = s
    return serie, f"leidos del HUD en {len(legibles)} de {len(con)} muestras, acotados por {p.cs_de}"


def _mmss(gt):
    gt = max(0, int(gt))
    return f"{gt // 60:02d}:{gt % 60:02d}"


def estados(p, ms, desfase, dur, cs_serie):
    """[(a, b, estado)] con estado = {reloj, kda, equipos, cs}; un tramo por cada cambio (el reloj, cada segundo)."""
    cortes = {0.0, float(dur)}
    g0 = desfase
    s = int(g0) + 1
    while s - g0 < dur:
        cortes.add(s - g0)
        s += 1
    for g, _x in p.kda:
        if 0 < g - g0 < dur:
            cortes.add(g - g0)
    for g, _x in p.muertes:
        if 0 < g - g0 < dur:
            cortes.add(g - g0)
    for t, _n in (cs_serie or []):
        if 0 < t < dur:
            cortes.add(t)
    cortes = sorted(cortes)
    out = []
    for a, b in zip(cortes, cortes[1:]):
        if b - a < 0.01:
            continue
        g = a + g0 + 0.001
        cs = None
        if cs_serie:
            cs = cs_serie[0][1]
            for t, n in cs_serie:
                if t <= a + 0.001:
                    cs = n
        e = {"reloj": _mmss(g), "kda": list(p.kda_en(g)), "equipos": p.equipos_en(g), "cs": cs}
        if out and out[-1][2] == e:
            out[-1] = (out[-1][0], b, e)
        else:
            out.append((a, b, e))
    return out
