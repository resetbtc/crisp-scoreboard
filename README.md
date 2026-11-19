# crisp-scoreboard

**English** · [Español](#español)

The League of Legends top-right scoreboard (team kills, K/D/A, creep score and game clock), redrawn crisp with the real numbers, for vertical videos or any edit.

In a 1080p video that scoreboard is 375x26 pixels. Blown up for a vertical video it turns into mush. crisp-scoreboard redraws it at the size you need: same order, same colors, the game's own icons (scaled by whole pixels, never smoothed) and every number checked against the video.

## Where each number comes from

| Number | Source | If it fails |
|---|---|---|
| Clock | Read from the video itself (game time = t + offset, to a tenth of a second) | Nothing is drawn |
| Match | Your recording (see `grabador`) whose K/D/A at that time matches the HUD; otherwise Riot's match-v5 timeline | Two matches fit: nothing is drawn |
| K/D/A and team kills | The recording or the timeline. Every K/D/A and team score read from the HUD has to agree | It doesn't agree: not drawn |
| Creep score | Read from the HUD. The live API gives it in steps of 10 and the timeline per minute, so they only bound the reading | Unreadable or out of bounds: the box is left out. Never an approximate number |

The left team score is always the blue side of the map; the color tells which one is yours (blue) and which is the enemy (red), exactly like the game.

## Usage

```bash
pip install -r requirements.txt
python -m crisp_scoreboard.grabador partidas/            # while you play: records the game's local API
python -m crisp_scoreboard clip.mp4 --grabaciones partidas/ --salida salida/
```

Without a recording, using your Riot developer key and your Riot ID:

```bash
RIOT_API_KEY=... python -m crisp_scoreboard clip.mp4 --cuenta "Name#TAG" --hora 1789000000
```

You get `salida/marcador.mov` (with transparency), every card as PNG, and `origen.json` saying where each number came from.

`ejemplo/` has a made-up match and a script that draws its cards with no video and no key. `python pruebas/test_basico.py` runs the checks.

The first run downloads from CommunityDragon, into `.cache/`, what belongs to Riot: the HUD atlas (icons), the scoreboard font (used to build the digit templates the reader needs) and the rank emblems. None of it is in this repository.

## Licenses

- Code: MIT, see `LICENSE`.
- `fuentes/`: Overused Grotesk, SIL Open Font License 1.1.
- Riot Games' assets (icons, font, emblems) are not included and are not covered by the MIT license: they are downloaded on first run and used under Riot's "Legal Jibber Jabber" policy.

---

## Español

El marcador de arriba a la derecha de League of Legends (muertes de cada equipo, K/D/A, súbditos y reloj), redibujado nítido y con los números de verdad, para vídeos verticales o cualquier edición.

En un vídeo a 1080p ese marcador mide 375x26 píxeles, y al ampliarlo para un vertical se ve pixelado. crisp-scoreboard lo redibuja al tamaño que necesites: el mismo orden, los mismos colores y los iconos del propio juego, ampliados a píxel entero y sin suavizar. Cada número se comprueba contra el vídeo.

### De dónde sale cada número

| Número | Fuente | Si falla |
|---|---|---|
| Reloj | Se lee del propio vídeo (hora de partida = t + desfase, a una décima) | No se dibuja nada |
| Partida | Tu grabación (ver `grabador`) cuyo K/D/A a esa hora es el del HUD; si no hay grabación, la timeline de match-v5 de Riot | Si cuadran dos, no se dibuja |
| K/D/A y muertes por equipo | La grabación o la timeline. Cada K/D/A y cada marcador de equipos que se lee en el HUD tiene que coincidir | Si no coincide, no se dibuja |
| Súbditos | Se leen del HUD. La API los da de 10 en 10 y la timeline por minuto, así que solo sirven para acotar la lectura | Si no se leen o no cuadran, la casilla no sale. Nunca un número aproximado |

A la izquierda va siempre el lado azul del mapa, y el color dice cuál es tu equipo (azul) y cuál el rival (rojo), igual que en el juego.

### Uso

Los comandos están arriba. Sin grabación, con tu clave de desarrollador de Riot en `RIOT_API_KEY`, tu Riot ID en `--cuenta` y la hora del clip en `--hora`.

La primera vez se baja de CommunityDragon a `.cache/` lo que es de Riot: los iconos del HUD, la letra del marcador (con ella se generan las plantillas de los dígitos) y los emblemas. Nada de eso va en el repositorio.

### Licencias

- El código es MIT.
- La letra de `fuentes/` es OFL 1.1.
- Lo de Riot no va incluido: se baja al usarlo, bajo su política «Legal Jibber Jabber».

## Riot Games

crisp-scoreboard was created under Riot Games' "Legal Jibber Jabber" policy using assets owned by Riot Games. Riot Games does not endorse or sponsor this project.
