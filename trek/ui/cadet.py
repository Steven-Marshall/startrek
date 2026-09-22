"""Cadet mode -- an opt-in targeting assist.

For each Klingon in the quadrant it shows the course the library computer
would give you (COM 2, which is free anyway), and then the one thing the
original never tells you: whether a torpedo on that course actually reaches
it, or runs into a star first.

Both halves come straight from the engine -- Game.bearing() is the
computer's own formula, and Game.torpedo_track() is the walk the real shot
takes -- so the preview cannot disagree with what happens when you fire.

The course is rounded to two decimals BEFORE the track is walked, because
that is what you will type.  A tick therefore means "type exactly this and
it hits", not "the ideal course would hit".

The computer does the sums, so no computer, no cadet assist.
"""

from dataclasses import dataclass, field

from ..game import EMPTY, KLINGON

LIBRARY_COMPUTER = 8


@dataclass
class Target:
    row: int
    col: int
    course: float
    distance: float
    clear: bool
    blocker: tuple = None          # (row, col, contents) if something else is hit
    cells: list = field(default_factory=list)   # sectors the torpedo passes


def available(game):
    return game.damage[LIBRARY_COMPUTER] >= 0


def targets(game):
    """One Target per live Klingon in the current quadrant."""
    if not available(game):
        return []
    found = []
    for i in range(1, game.cfg.max_klingons_per_quadrant + 1):
        if game.k[i][3] <= 0:
            continue
        row, col = game.k[i][1], game.k[i][2]
        course, distance = game.bearing(game.srow, game.scol, row, col)
        course = round(course, 2)
        if course >= 9:
            course = 1.0

        cells, hit = [], None
        for _, _, x3, y3, what in game.torpedo_track(course):
            if what is None:                    # left the quadrant
                break
            cells.append((x3, y3))
            if what != EMPTY:
                hit = (x3, y3, what)
                break

        clear = hit is not None and hit[:2] == (row, col) and hit[2] == KLINGON
        found.append(Target(row, col, course, distance, clear,
                            None if clear else hit, cells))
    return found
