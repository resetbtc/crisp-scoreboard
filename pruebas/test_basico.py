# -*- coding: utf-8 -*-
"""python pruebas/test_basico.py: la partida inventada del ejemplo, sin video ni clave."""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from crisp_scoreboard import dibujo, partida as P  # noqa: E402

fallos = 0


def check(n, c):
    global fallos
    print(("  ok    " if c else "  FALLO ") + n)
    fallos += 0 if c else 1


p = P.partida_lector(os.path.join(RAIZ, "ejemplo", "partida_inventada.jsonl"))
check("se lee la partida", p is not None)
check("K/D/A a las 11:53: 3/0/1", p.kda_en(713) == (3, 0, 1))
check("muertes por equipo: lado azul a la izquierda, el tuyo", p.equipos_en(713) == [4, 1, True])
ms = [(i / 4.0, int(700 + i / 4.0), p.kda_en(700 + i / 4.0 + 0.2), 89 + (1 if i > 40 else 0), None) for i in range(80)]
check("el HUD inventado cuadra", P.cuadra(p, ms, 700.0)[0])
check("sin lecturas de equipos no se dibujan", not P.comprueba_equipos(p, ms, 700.0)[0])
mal = [(t, c, k, 95, e) for t, c, k, s, e in ms]
check("subditos que no cuadran: la casilla no sale", P.serie_cs(p, mal, 700.0)[0] is None)
im = dibujo.dibuja_marcador({"reloj": "11:48", "kda": [2, 0, 1], "equipos": [9, 9, True], "cs": 89}, 864, 60)
check("la tarjeta mide lo pedido (+4 del borde)", im.size == (868, 64))
print("TODO OK" if not fallos else f"{fallos} FALLO(S)")
sys.exit(1 if fallos else 0)
