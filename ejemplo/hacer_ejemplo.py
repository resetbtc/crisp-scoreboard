# -*- coding: utf-8 -*-
"""Una partida INVENTADA (partida_inventada.jsonl) dibujada sin video ni clave:
    python ejemplo/hacer_ejemplo.py      -> ejemplo/tarjetas/*.png
Hace como si el HUD del clip se hubiera leido a 4 lecturas por segundo desde el minuto 11:40."""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from crisp_scoreboard import dibujo, partida as P  # noqa: E402

p = P.partida_lector(os.path.join(AQUI, "partida_inventada.jsonl"))
desfase = 700.0
ms = [(i / 4.0, int(700 + i / 4.0), p.kda_en(700 + i / 4.0 + 0.2), 89 + (1 if i > 40 else 0)) for i in range(80)]
print(P.cuadra(p, ms, desfase)[1])
serie, mot = P.serie_cs(p, ms, desfase)
print("subditos:", mot)
os.makedirs(os.path.join(AQUI, "tarjetas"), exist_ok=True)
for i, (a, b, e) in enumerate(P.estados(p, ms, desfase, 20.0, serie or [])):
    dibujo.dibuja_marcador(e, 864, 60).save(os.path.join(AQUI, "tarjetas", f"{i:03d}.png"))
print("tarjetas en", os.path.join(AQUI, "tarjetas"))
