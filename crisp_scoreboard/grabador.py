# -*- coding: utf-8 -*-
"""Graba tus partidas de League of Legends desde la API local del juego (Live Client Data, https://127.0.0.1:2999),
que el propio juego abre mientras juegas. No toca el juego ni lee su memoria: solo pregunta a esa API.

Una linea JSON por cosa, en <carpeta>/<fecha>_<gameId o hora>.jsonl:
  {"k": "ini",  "t": ms, "riotId": "Nombre#TAG"}
  {"k": "todo", "t": ms, "gt": s, "d": <allgamedata al empezar: equipos y campeones>}
  {"k": "m",    "t": ms, "gt": s, "kda": [k, d, a], "cs": n}      (solo cuando algo cambia)
  {"k": "e",    "t": ms, "gt": s, "ev": <evento: ChampionKill, Multikill...>}

Pesa poco: 4 preguntas por segundo a localhost y escribir lo que cambia. Sin partida, mira el puerto cada 5 s.
    python -m crisp_scoreboard.grabador partidas/
"""
import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://127.0.0.1:2999/liveclientdata"
TICK = 0.25
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE        # la API del juego usa un certificado propio de Riot en localhost


def pide(ruta, timeout=1.0):
    with urllib.request.urlopen(BASE + ruta, context=_ctx, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def ms():
    return int(time.time() * 1000)


def graba_partida(carpeta):
    todo = pide("/allgamedata", timeout=3)
    ap = todo.get("activePlayer") or {}
    riot = ap.get("riotId") or ap.get("summonerName") or ""
    nombre = time.strftime("%Y-%m-%d_%H%M%S") + ".jsonl"
    ruta = os.path.join(carpeta, nombre)
    vistos, ultimo = set(), None
    with open(ruta, "a", encoding="utf-8") as f:
        def linea(d):
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
            f.flush()
        linea({"k": "ini", "t": ms(), "riotId": riot})
        linea({"k": "todo", "t": ms(), "gt": (todo.get("gameData") or {}).get("gameTime"),
               "d": {"allPlayers": todo.get("allPlayers"), "gameData": todo.get("gameData")}})
        ruta_scores = "/playerscores?riotId=" + urllib.parse.quote(riot, safe="")
        fallos = 0
        while True:
            t0 = time.time()
            try:
                gt = pide("/gamestats").get("gameTime")
                sc = pide(ruta_scores)
                m = {"kda": [sc.get("kills", 0), sc.get("deaths", 0), sc.get("assists", 0)],
                     "cs": sc.get("creepScore", 0)}
                if m != ultimo:
                    linea(dict({"k": "m", "t": ms(), "gt": gt}, **m))
                    ultimo = m
                for ev in (pide("/eventdata").get("Events") or []):
                    if ev.get("EventID") not in vistos:
                        vistos.add(ev.get("EventID"))
                        linea({"k": "e", "t": ms(), "gt": gt, "ev": ev})
                fallos = 0
            except Exception:  # noqa: BLE001
                fallos += 1
                if fallos > 20:          # 5 s sin contestar: la partida se ha acabado
                    return ruta
            time.sleep(max(0.0, TICK - (time.time() - t0)))


def main(argv=None):
    carpeta = (argv or sys.argv[1:] or ["partidas"])[0]
    os.makedirs(carpeta, exist_ok=True)
    print(f"grabando en {carpeta} (Ctrl+C para parar)")
    while True:
        try:
            pide("/gamestats")
        except Exception:  # noqa: BLE001
            time.sleep(5)
            continue
        print("partida:", graba_partida(carpeta))


if __name__ == "__main__":
    main()
