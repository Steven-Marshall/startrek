"""Render the sprites to a PNG, for editing them without launching the game.

    python tools/sprite_sheet.py            -> sprites.png

Draws every sprite at every size, the torpedo and explosion frames, and a
sample quadrant through the real renderer (trek/ui/panels.py), so what you
see here is what the game draws.  Colours are Windows Terminal's default
"Campbell" scheme; other terminals will differ a little.

Needs Pillow (pip install pillow).  The game itself does not.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from PIL import Image, ImageDraw                                    # noqa: E402

from trek.game import Game, EMPTY, SHIP, KLINGON, STARBASE, STAR    # noqa: E402
from trek.ui.panels import draw_quadrant                            # noqa: E402
from trek.ui.sprites import (PALETTE, SPRITES, SIZES, torpedo,     # noqa: E402
                             explosion, EXPLOSION_FRAMES)

CAMPBELL = {
    "black": "#0C0C0C", "red": "#C50F1F", "green": "#13A10E",
    "yellow": "#C19C00", "blue": "#0037DA", "magenta": "#881798",
    "cyan": "#3A96DD", "white": "#CCCCCC",
    "bright_black": "#767676", "bright_red": "#E74856",
    "bright_green": "#16C60C", "bright_yellow": "#F9F1A5",
    "bright_blue": "#3B78FF", "bright_magenta": "#B4009E",
    "bright_cyan": "#61D6D6", "bright_white": "#F2F2F2",
}
BACKGROUND = CAMPBELL["black"]
LABEL = "#9A9A9A"


def paint_sprite(draw, rows, x0, y0, scale):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != ".":
                colour = CAMPBELL[PALETTE[ch]]
                draw.rectangle([x0 + x * scale, y0 + y * scale,
                                x0 + (x + 1) * scale - 1, y0 + (y + 1) * scale - 1],
                               fill=colour)


def paint_canvas(draw, canvas, x0, y0, scale):
    for y in range(canvas.height):
        for x in range(canvas.width):
            colour = canvas.px[y][x]
            if colour:
                draw.rectangle([x0 + x * scale, y0 + y * scale,
                                x0 + (x + 1) * scale - 1, y0 + (y + 1) * scale - 1],
                               fill=CAMPBELL[colour])


def sample_quadrant():
    """A fixed, hand-placed quadrant that shows every kind of object."""
    g = Game(seed=1, out=lambda *a: None)
    g.q = EMPTY * 64
    g.srow, g.scol = 6, 2
    placements = {(6, 2): SHIP, (2, 6): KLINGON, (3, 3): KLINGON,
                  (7, 7): STARBASE, (4, 5): STAR, (1, 2): STAR, (8, 4): STAR}
    for (r, c), what in placements.items():
        g.put(r, c, what)
    g.k_here = 2
    g.k[1][1:4] = [2, 6, 200]
    g.k[2][1:4] = [3, 3, 150]
    return g


def main(path="sprites.png"):
    scale = 12
    names = ["ship", "klingon", "starbase", "star"]
    gap = 24

    # sprite grid: one row per size, one column per sprite + fx
    cell = 8 * scale + gap
    sheet_w = gap + cell * (len(names) + 1 + EXPLOSION_FRAMES)
    sheet_h = gap + cell * len(SIZES)

    # sample quadrants below, at each size, with a cadet-style track
    quad_scale = 3
    quad_w = [8 * s * quad_scale for s in SIZES]
    quads_h = max(quad_w) + gap * 2
    image = Image.new("RGB", (max(sheet_w, sum(quad_w) + gap * (len(SIZES) + 1)),
                              sheet_h + quads_h), BACKGROUND)
    draw = ImageDraw.Draw(image)

    for row, size in enumerate(SIZES):
        y = gap + row * cell
        draw.text((4, y), f"{size}x{size}", fill=LABEL)
        sprites = [SPRITES[size][n] for n in names]
        sprites += [torpedo(size)] + [explosion(size, f) for f in range(EXPLOSION_FRAMES)]
        labels = names + ["torpedo"] + [f"boom {f + 1}" for f in range(EXPLOSION_FRAMES)]
        for col, (rows, label) in enumerate(zip(sprites, labels)):
            x = gap + col * cell + 30
            if row == 0:
                draw.text((x, 4), label, fill=LABEL)
            paint_sprite(draw, rows, x, y + 8, scale)

    g = sample_quadrant()
    x = gap
    for size, width in zip(SIZES, quad_w):
        canvas = draw_quadrant(g, size, fx=[("beam", 6, 2, 2, 6, "R")])
        draw.text((x, sheet_h + 4), f"quadrant at {size}x{size}, with a phaser beam",
                  fill=LABEL)
        paint_canvas(draw, canvas, x, sheet_h + gap, quad_scale)
        x += width + gap

    image.save(path)
    print(f"wrote {path}  ({image.width}x{image.height})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sprites.png")
