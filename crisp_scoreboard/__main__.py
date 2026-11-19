# -*- coding: utf-8 -*-
"""Uso:
  python -m crisp_scoreboard VIDEO [--desde S] [--dura S] (--grabaciones CARPETA | --cuenta "Nombre#TAG" --hora EPOCH)
                            [--ancho 864] [--salida carpeta]

Lee el reloj, el K/D/A y los subditos del HUD del VIDEO, busca su partida (en tus grabaciones del grabador, o en
match-v5 con RIOT_API_KEY) y deja en --salida:
  - marcador.mov: el marcador redibujado con transparencia, un fotograma por cambio, para ponerlo encima en tu editor;
  - tarjetas/ con cada estado en PNG;
  - origen.json: de donde sale cada numero.
"""
import argparse
import json
import os
import subprocess
import sys


def main(argv=None):
    from crisp_scoreboard import dibujo, partida as P
    a = argparse.ArgumentParser(prog="crisp_scoreboard")
    a.add_argument("video")
    a.add_argument("--desde", type=float, default=0.0)
    a.add_argument("--dura", type=float, default=None)
    a.add_argument("--grabaciones", default=None)
    a.add_argument("--cuenta", action="append", default=[], help='Riot ID "Nombre#TAG" (puede repetirse)')
    a.add_argument("--hora", type=float, default=None, help="epoch del segundo --desde (para buscar en match-v5)")
    a.add_argument("--ancho", type=int, default=864)
    a.add_argument("--salida", default="salida")
    o = a.parse_args(argv)
    dur = o.dura
    if dur is None:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", o.video],
                           capture_output=True, text=True)
        dur = float(r.stdout) - o.desde
    ms = P.muestras(o.video, o.desde, dur)
    desfase, n_ok, n = P.desfase_reloj(ms)
    if desfase is None:
        sys.exit(f"no se lee el reloj del HUD ({n_ok} de {n} lecturas cuadran)")
    cands = ()
    key = os.environ.get("RIOT_API_KEY", "")
    if o.cuenta and o.hora and key:
        cands = P.candidatas_riot(o.hora - desfase - 300, o.hora + dur, key, o.cuenta)
    p, mot = P.busca_partida(ms, desfase, o.grabaciones, o.hora, cands)
    if p is None:
        sys.exit(mot)
    if not p.paso_cs and key:
        P.cs_de_timeline(p, key)
    serie, mot_cs = P.serie_cs(p, ms, desfase)
    es = P.estados(p, ms, desfase, dur, serie or [])
    eq_ok, mot_eq = P.comprueba_equipos(p, ms, desfase)
    if not eq_ok:
        es = [(a_, b_, dict(e, equipos=None)) for a_, b_, e in es]
    h = round(o.ancho * 26 / 375)               # la proporcion del marcador del juego
    os.makedirs(os.path.join(o.salida, "tarjetas"), exist_ok=True)
    lista, hechas = [], {}
    for a_, b_, e in es:
        clave = json.dumps(e, sort_keys=True)
        if clave not in hechas:
            ruta = os.path.join(o.salida, "tarjetas", f"{len(hechas):04d}.png")
            dibujo.dibuja_marcador(e, o.ancho, h).save(ruta)
            hechas[clave] = ruta
        lista.append((hechas[clave], b_ - a_))
    concat = os.path.join(o.salida, "tarjetas.txt")
    with open(concat, "w", encoding="utf-8") as f:
        for ruta, d in lista:
            f.write(f"file '{os.path.abspath(ruta)}'\nduration {d:.3f}\n")
        f.write(f"file '{os.path.abspath(lista[-1][0])}'\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", concat, "-vf", "fps=60",
                    "-c:v", "qtrle", os.path.join(o.salida, "marcador.mov")], check=True)
    origen = {"partida": mot, "reloj": f"{n_ok} de {n} lecturas del HUD cuadran (hora = t + {desfase:.2f})",
              "kda": P.cuadra(p, ms, desfase)[1], "subditos": mot_cs if serie else "NO SALEN: " + mot_cs,
              "equipos": mot_eq if eq_ok else "NO SALEN: " + mot_eq}
    json.dump(origen, open(os.path.join(o.salida, "origen.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k, v in origen.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
