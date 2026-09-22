"""Sprites -- first pass.  Edit freely.

Every sprite is a list of strings, one per pixel row, drawn top-down with
north at the top.  Each character is a palette letter, and "." is
transparent.  Sizes are 4x4, 6x6 and 8x8 pixels; the screen picks the largest
that fits the terminal.

Pixels are drawn with half-block characters (see canvas.py), so each text
cell holds two pixels stacked vertically -- and because terminal cells are
roughly twice as tall as they are wide, the pixels come out close to square.
An 8x8 sprite therefore occupies 8 columns by 4 rows of text.

The palette is the 16 standard ANSI colours and nothing else.  That keeps it
CGA-era, and it works in every terminal.
"""

PALETTE = {
    "W": "bright_white",
    "w": "white",           # light grey in most terminal schemes
    "k": "bright_black",    # dark grey
    "R": "bright_red",
    "r": "red",
    "G": "bright_green",
    "g": "green",
    "Y": "bright_yellow",
    "y": "yellow",
    "C": "bright_cyan",
    "c": "cyan",
    "B": "bright_blue",
    "b": "blue",
    "M": "bright_magenta",
    "m": "magenta",
}

TRANSPARENT = "."

# ---------------------------------------------------------------------------
# The four things that can occupy a sector
# ---------------------------------------------------------------------------
#
# Enterprise: a solid saucer, the neck, then the engineering hull with the
# two nacelles standing clear of it on either side -- red bussard collectors
# at their forward ends.  (A first draft joined the nacelles with a crossbar,
# which made the back half look like a table.)
#
# Klingon D7: command pod on its long boom, main hull, wings sweeping down
# to the nacelles.  Green, as the ships were on screen.
#
# Starbase: a ring station with docking spurs and a blue core.
#
# Star: white-hot core in a yellow glow.

SPRITES = {
    8: {
        "ship": [
            "..WWWW..",
            ".WWWWWW.",
            ".WWWWWW.",
            "..WWWW..",
            "R..ww..R",
            "W.wwww.W",
            "W..ww..W",
            "W......W",
        ],
        "klingon": [
            "...GG...",
            "...gg...",
            "...gg...",
            "..GGGG..",
            ".GGGGGG.",
            "GG.GG.GG",
            "G..gg..G",
            "G......G",
        ],
        "starbase": [
            "...CC...",
            ".CCccCC.",
            ".Cc..cC.",
            "CC.bb.CC",
            "CC.bb.CC",
            ".Cc..cC.",
            ".CCccCC.",
            "...CC...",
        ],
        "star": [
            "........",
            "...yy...",
            "...YY...",
            ".yYWWYy.",
            ".yYWWYy.",
            "...YY...",
            "...yy...",
            "........",
        ],
    },
    6: {
        "ship": [
            ".WWWW.",
            "WWWWWW",
            ".WWWW.",
            "R.ww.R",
            "W.ww.W",
            "W....W",
        ],
        "klingon": [
            "..GG..",
            "..gg..",
            ".GGGG.",
            "GGGGGG",
            "G.gg.G",
            "G....G",
        ],
        "starbase": [
            "..CC..",
            ".CccC.",
            "CcbbcC",
            "CcbbcC",
            ".CccC.",
            "..CC..",
        ],
        "star": [
            "......",
            "..yy..",
            ".yWWy.",
            ".yWWy.",
            "..yy..",
            "......",
        ],
    },
    4: {
        "ship": [
            ".WW.",
            "WWWW",
            "RwwR",
            "W..W",
        ],
        "klingon": [
            ".GG.",
            ".gg.",
            "GGGG",
            "G..G",
        ],
        "starbase": [
            ".CC.",
            "CbbC",
            "CbbC",
            ".CC.",
        ],
        "star": [
            "....",
            ".YY.",
            ".YY.",
            "....",
        ],
    },
}

SIZES = sorted(SPRITES, reverse=True)       # largest first: 8, 6, 4


# ---------------------------------------------------------------------------
# Effects -- generated rather than drawn, so they work at every size
# ---------------------------------------------------------------------------

def _blank(size):
    return [[TRANSPARENT] * size for _ in range(size)]


def _rows(grid):
    return ["".join(row) for row in grid]


def torpedo(size):
    """A photon torpedo: a hot red core with a faint halo at larger sizes."""
    grid = _blank(size)
    lo, hi = size // 2 - 1, size // 2
    for y in (lo, hi):
        for x in (lo, hi):
            grid[y][x] = "R"
    if size >= 6:
        for y, x in ((lo - 1, lo), (lo - 1, hi), (hi + 1, lo), (hi + 1, hi),
                     (lo, lo - 1), (hi, lo - 1), (lo, hi + 1), (hi, hi + 1)):
            grid[y][x] = "r"
    return _rows(grid)


EXPLOSION_FRAMES = 3


def explosion(size, frame):
    """Three frames: a white-hot flash, a banded fireball, then drifting debris.

    Colours run hot to cool from the centre -- white, cream, gold, red -- and
    the radii scale with the sprite so the small sizes still read as a bang.
    """
    grid = _blank(size)
    centre = (size - 1) / 2
    reach = size / 2 + 0.3
    for y in range(size):
        for x in range(size):
            d = ((x - centre) ** 2 + (y - centre) ** 2) ** 0.5 / reach
            if frame == 0:
                colour = "W" if d <= 0.40 else "Y" if d <= 0.62 else "y" if d <= 0.78 else None
            elif frame == 1:
                colour = ("Y" if d <= 0.30 else "y" if d <= 0.58 else "R" if d <= 0.86
                          else "r" if d <= 1.0 and (x + y) % 2 == 0 else None)
            else:
                colour = None
                if 0.62 <= d <= 1.05 and (x * 3 + y * 5) % 4 == 0:
                    colour = "r" if (x + y) % 3 else "k"
            if colour:
                grid[y][x] = colour
    return _rows(grid)
