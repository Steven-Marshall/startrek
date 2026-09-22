"""Panels -- each a pure function from game state to something rich can draw.

Nothing here changes the game.  The panels only READ it: the quadrant string
q, the chart, the damage array and so on, exactly as the engine keeps them.

The fairness rule
-----------------
A panel may only show what the original gives you for free, and it must
break when the instrument behind it breaks.

    SRS, LRS and COM cost no time and no energy, so a panel that keeps their
    results on screen is just "auto-typing a free command".  But:

      short range sensors damaged  ->  the pixel view and the ASCII scan die
      long range sensors damaged   ->  the long range panel says so
      library computer damaged     ->  no decoding, no cadet assist
      damage control damaged       ->  no damage report

    Ship-internal readouts (energy, shields, torpedoes, the clock) stay up;
    they are not sensors.

The long range panel shows your CHART -- what you have actually scanned --
not the galaxy.  So LRS is still something you have to remember to do.
"""

import random
import textwrap

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group

from ..basic import rjust3
from ..game import EMPTY, SHIP, KLINGON, STARBASE, STAR, DEVICES
from ..names import quadrant_name
from . import cadet as cadet_mode
from .canvas import Canvas
from .sprites import PALETTE, SPRITES, torpedo, explosion

SHORT_RANGE_SENSORS, LONG_RANGE_SENSORS = 2, 3
DAMAGE_CONTROL, LIBRARY_COMPUTER = 6, 8

KIND = {SHIP: "ship", KLINGON: "klingon", STARBASE: "starbase", STAR: "star"}

CONDITION_STYLE = {
    "*RED*": "bright_red",
    "YELLOW": "bright_yellow",
    "GREEN": "bright_green",
    "DOCKED": "bright_cyan",
}

# The panel sizes the layout is built around.
SRS_WIDTH = 35                  # 33-character scan + border
LRS_WIDTH = 31
TOP_HEIGHT = 12                 # SRS / ship row
MID_HEIGHT = 10                 # LRS / damage row
RIGHT_MIN_WIDTH = 60
RIGHT_MIN_HEIGHT = TOP_HEIGHT + MID_HEIGHT + 5


def working(game, device):
    return game.damage[device] >= 0


def live_condition(game):
    """6580-6660 without the side effects.

    The engine only updates C$ when it prints a short range scan, so after a
    fight it can still say *RED* with nothing left to shoot.  The panel
    recomputes it from the same rules instead.
    """
    if game.docked:
        return "DOCKED"
    if game.k_here > 0:
        return "*RED*"
    if game.energy < game.energy0 * 0.1:
        return "YELLOW"
    return "GREEN"


# ---------------------------------------------------------------------------
# The pixel quadrant
# ---------------------------------------------------------------------------

def _centre(size, row, col):
    return (col - 1) * size + size // 2, (row - 1) * size + size // 2


def draw_quadrant(game, size, fx=(), targets=(), trail=()):
    """Render the current quadrant onto a Canvas.

    fx is a sequence of transient effects for animation frames:
        ("torpedo", row, col)
        ("explode", row, col, frame)
        ("beam", from_row, from_col, to_row, to_col, palette_letter)
        ("flash", row, col, palette_letter)
    """
    n = game.cfg.sector_size
    canvas = Canvas(n * size, n * size)
    exploding = {(f[1], f[2]) for f in fx if f[0] == "explode"}

    # 1. a faint dot in every empty sector, so you can count squares
    for row in range(1, n + 1):
        for col in range(1, n + 1):
            if game.cell(row, col) == EMPTY:
                canvas.set(*_centre(size, row, col), PALETTE["k"])

    # 2. cadet tracks: yellow if the shot gets through, red if it is blocked
    for target in targets:
        colour = PALETTE["y" if target.clear else "r"]
        for row, col in target.cells[:-1]:
            x, y = _centre(size, row, col)
            canvas.set(x, y, colour)
            if size >= 6:                        # a 2x2 marker, not a dot
                canvas.set(x - 1, y, colour)
                canvas.set(x, y - 1, colour)
                canvas.set(x - 1, y - 1, colour)

    # 3. the path of the torpedo in flight
    for row, col in trail:
        canvas.set(*_centre(size, row, col), PALETTE["r"])

    # 4. beams go under the sprites, so ships stay crisp
    for f in fx:
        if f[0] == "beam":
            x0, y0 = _centre(size, f[1], f[2])
            x1, y1 = _centre(size, f[3], f[4])
            canvas.line(x0, y0, x1, y1, PALETTE[f[5]])

    # 5. everything in the quadrant
    for row in range(1, n + 1):
        for col in range(1, n + 1):
            what = game.cell(row, col)
            if what != EMPTY and (row, col) not in exploding:
                canvas.blit(SPRITES[size][KIND[what]], (col - 1) * size, (row - 1) * size)

    # 6. flashes, torpedoes and explosions on top
    for f in fx:
        if f[0] == "beam":
            continue
        x0, y0 = (f[2] - 1) * size, (f[1] - 1) * size
        if f[0] == "flash":
            what = game.cell(f[1], f[2])
            if what != EMPTY:
                canvas.blit(SPRITES[size][KIND[what]], x0, y0, recolour=f[3])
        elif f[0] == "torpedo":
            canvas.blit(torpedo(size), x0, y0)
        elif f[0] == "explode":
            canvas.blit(explosion(size, f[3]), x0, y0)
    return canvas


def _static(game, size):
    """Short range sensors damaged: nothing but noise."""
    n = game.cfg.sector_size
    canvas = Canvas(n * size, n * size)
    rng = random.Random()
    for y in range(canvas.height):
        for x in range(canvas.width):
            roll = rng.random()
            if roll < 0.10:
                canvas.set(x, y, PALETTE["k"])
            elif roll < 0.12:
                canvas.set(x, y, PALETTE["w"])
    return canvas


def _draw_compass(game, lines, size, label_row):
    """Number the eight sectors around the ship with their course digits.

    Shown whenever the game asks for a course.  The directions come from the
    engine's own compass table (530-600), so they cannot disagree with where
    NAV and TOR actually go.  Sectors off the edge of the quadrant are left
    unnumbered -- that way lies the galactic rim anyway.
    """
    n = game.cfg.sector_size
    row, col = int(game.srow), int(game.scol)
    for course in range(1, 9):
        r = row + game.course[course][1]
        c = col + game.course[course][2]
        if not (1 <= r <= n and 1 <= c <= n):
            continue
        line_no = 1 + (r - 1) * (size // 2) + label_row      # +1: column header
        x = 2 + (c - 1) * size + size // 2                    # +2: row labels
        line = lines[line_no]
        # a solid badge, so it stays legible on top of a sprite
        lines[line_no] = (line[:x] + Text(str(course), style="bold bright_white on magenta")
                          + line[x + 1:])


def pixel_panel(game, size, fx=(), cadet=False, trail=(), height=None, compass=False):
    n = game.cfg.sector_size
    sensors = working(game, SHORT_RANGE_SENSORS)
    targets = cadet_mode.targets(game) if (cadet and sensors) else []
    canvas = draw_quadrant(game, size, fx, targets, trail) if sensors else _static(game, size)

    lines = []
    header = Text("  ", style="bright_black")
    for col in range(1, n + 1):
        header.append(str(col).center(size), style="bright_black")
    lines.append(header)

    label_row = (size // 2) // 2              # the text row holding the sector's centre
    for i, row_text in enumerate(canvas.rows()):
        sector_row, offset = divmod(i, size // 2)
        label = f"{sector_row + 1} " if offset == label_row else "  "
        line = Text(label, style="bright_black")
        line.append_text(row_text)
        lines.append(line)

    if compass and sensors:
        _draw_compass(game, lines, size, label_row)

    if not sensors:
        middle = len(lines) // 2
        msg = " SHORT RANGE SENSORS DAMAGED "
        lines[middle] = Text("  " + msg.center(n * size), style="bold bright_red")

    if cadet:
        cadet_lines = _cadet_lines(game, targets, n * size + 2)
        room = (height - 2 - len(lines)) if height else len(cadet_lines) + 1
        if room > len(cadet_lines):              # a spacer only if it fits
            lines.append(Text(""))
        lines.extend(cadet_lines)

    condition = live_condition(game)
    name = quadrant_name(game.qrow, game.qcol)
    return Panel(
        Group(*lines),
        title=f"[bold] {name} [/]· QUADRANT {game.qrow},{game.qcol} ",
        subtitle=f" {condition} ",
        border_style=CONDITION_STYLE.get(condition, "white"),
        padding=0,
        height=height,
    )


def _cadet_lines(game, targets, width):
    label = Text("CADET ", style="bold bright_magenta")
    if not cadet_mode.available(game):
        return [label + Text("computer damaged", style="bright_black")]
    if not working(game, SHORT_RANGE_SENSORS):
        return [label + Text("no sensor data", style="bright_black")]
    if not targets:
        return [label + Text("no targets", style="bright_black")]

    def part(t, where):
        text = Text(f"{t.row},{t.col}→{t.course:.2f}", style="white")
        if t.clear:
            text.append(" ✓", style="bold bright_green")
        elif t.blocker:
            glyph = {STAR: "★", STARBASE: "B", KLINGON: "K"}.get(t.blocker[2], "?")
            spot = f"{t.blocker[0]},{t.blocker[1]}" if where else ""
            text.append(f" ✗{glyph}{spot}", style="bold bright_red")
        else:
            text.append(" ✗", style="bold bright_red")
        return text

    # Three Klingons must fit on ONE line -- at 6x6 in a 120x30 terminal
    # there is no room for a second.  So try progressively terser forms: the
    # blocker's position can go (the red track already shows where it is),
    # then the label shrinks to a marker.  Wrap only if even that fails.
    forms = [(label, True, "  "), (label, False, "  "),
             (Text("▸ ", style="bold bright_magenta"), False, " ")]
    for prefix, where, gap in forms:
        line = prefix.copy()
        for i, t in enumerate(targets):
            if i:
                line.append(gap)
            line.append_text(part(t, where))
        if line.cell_len <= width:
            return [line]

    lines, current = [], forms[-1][0].copy()
    for t in targets:
        piece = part(t, False)
        if current.cell_len + piece.cell_len + 1 > width and current.cell_len > 2:
            lines.append(current)
            current = Text("  ")
        current.append_text(piece)
        current.append(" ")
    lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# The ASCII scan -- the original, as is
# ---------------------------------------------------------------------------

def srs_panel(game):
    n = game.cfg.sector_size
    w = game.cfg.cell_width
    if not working(game, SHORT_RANGE_SENSORS):
        body = Text("\n\n***\nSHORT RANGE SENSORS ARE OUT\n***",
                    style="bright_red", justify="center")
    else:
        rule = "-" * 33
        rows = [rule]
        for i in range(n):
            base = i * n * w
            rows.append("".join(" " + game.q[base + j * w: base + j * w + w] for j in range(n)))
        rows.append(rule)
        body = Text("\n".join(rows))
    return Panel(body, title="SHORT RANGE SCAN", padding=0, border_style="white")


# ---------------------------------------------------------------------------
# Ship status
# ---------------------------------------------------------------------------

def _bar(value, maximum, width=7, style="white"):
    filled = max(0, min(width, round(width * value / maximum))) if maximum else 0
    return Text("█" * filled, style=style) + Text("░" * (width - filled), style="bright_black")


def ship_panel(game):
    condition = live_condition(game)
    grid = Table.grid(expand=True)
    grid.add_column(style="bright_black")
    grid.add_column(justify="right")

    days_left = game.stardate0 + game.mission_days - game.stardate
    days = (Text(f"{days_left:.1f}", style="bright_red" if days_left < 5 else "white")
            if days_left >= 0 else Text("OVERTIME", style="bold bright_red"))

    grid.add_row("STARDATE", f"{int(game.stardate * 10) * 0.1:.1f}")
    grid.add_row("CONDITION", Text(condition, style=CONDITION_STYLE.get(condition, "white")))
    grid.add_row("QUADRANT", f"{game.qrow},{game.qcol}")
    grid.add_row("SECTOR", f"{int(game.srow)},{int(game.scol)}")
    grid.add_row("ENERGY", _bar(game.energy, game.energy0, style="bright_yellow")
                 + Text(f" {int(game.energy):4d}"))
    grid.add_row("SHIELDS", _bar(game.shields, game.energy0, style="bright_cyan")
                 + Text(f" {int(game.shields):4d}"))
    torps = int(game.torpedoes)
    grid.add_row("TORPEDOES", Text("●" * torps, style="bright_red")
                 + Text("○" * max(0, game.torpedoes0 - torps), style="bright_black"))
    grid.add_row("KLINGONS", str(int(game.klingons_left)))
    grid.add_row("DAYS LEFT", days)
    return Panel(grid, title="ENTERPRISE", border_style=CONDITION_STYLE.get(condition, "white"))


# ---------------------------------------------------------------------------
# Long range -- your chart, decoded
# ---------------------------------------------------------------------------

def _decode(value):
    """The base-10 quadrant code, spelled out: 107 -> 1K 0B 7*."""
    k, b, s = value // 100, (value // 10) % 10, value % 10
    text = Text()
    text.append(f"{k}K", style="bold bright_green" if k else "bright_black")
    text.append(" ")
    text.append(f"{b}B", style="bold bright_cyan" if b else "bright_black")
    text.append(" ")
    text.append(f"{s}★", style="bright_yellow" if s else "bright_black")
    return text


def lrs_panel(game):
    n = game.cfg.galaxy_size
    computer = working(game, LIBRARY_COMPUTER)
    lines = []
    for i in range(game.qrow - 1, game.qrow + 2):
        codes, decoded = Text(), Text()
        for j in range(game.qcol - 1, game.qcol + 2):
            here = (i, j) == (game.qrow, game.qcol)
            if not (1 <= i <= n and 1 <= j <= n):
                codes.append(" " * 9)
                decoded.append(" " * 9)
                continue
            value = game.chart[i][j]
            if value == 0:              # never scanned (every quadrant has >= 1 star)
                codes.append("   ···   ", style="bright_black")
                decoded.append(" " * 9)
                continue
            code = rjust3(value)
            if here:
                codes.append("  [", style="bright_white")
                codes.append(code, style="bold bright_white")
                codes.append("]  ", style="bright_white")
            else:
                codes.append(f"   {code}   ")
            if computer:
                decoded.append(" ")
                decoded.append_text(_decode(value))
            else:
                decoded.append(" " * 9)
        lines.extend([codes, decoded])

    if computer:
        lines.append(Text(""))
        legend = Text(" ")
        legend.append("K", style="bright_green"); legend.append(" klingons ", style="bright_black")
        legend.append("B", style="bright_cyan"); legend.append(" base ", style="bright_black")
        legend.append("★", style="bright_yellow"); legend.append(" stars", style="bright_black")
        lines.append(legend)

    title = "LONG RANGE"
    border = "white"
    if not working(game, LONG_RANGE_SENSORS):
        title += " · [bright_red]SENSORS DAMAGED[/]"
        border = "red"
    subtitle = None if computer else "[bright_black] computer damaged [/]"
    return Panel(Group(*lines), title=title, subtitle=subtitle, border_style=border)


# ---------------------------------------------------------------------------
# Damage control
# ---------------------------------------------------------------------------

def damage_panel(game):
    if not working(game, DAMAGE_CONTROL):
        body = Text("\nDAMAGE CONTROL REPORT\nNOT AVAILABLE", style="yellow", justify="center")
        return Panel(body, title="DAMAGE CONTROL", border_style="red")

    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_column(justify="right")
    any_damage = False
    for i in range(1, game.cfg.device_count + 1):
        state = game.damage[i]
        if state < 0:
            any_damage = True
            grid.add_row(Text(DEVICES[i], style="bright_red"),
                         Text(f"{int(state * 100) * 0.01:.2f}", style="bright_red"))
        else:
            grid.add_row(Text(DEVICES[i], style="bright_black"), Text("ok", style="green"))
    return Panel(grid, title="DAMAGE CONTROL",
                 border_style="yellow" if any_damage else "white")


# ---------------------------------------------------------------------------
# The log -- the canon teletype output, scrolling
# ---------------------------------------------------------------------------

def _log_style(line):
    if line.startswith("»"):            # the UI talking, not the 1978 game
        return "bright_magenta"
    if "DESTROYED" in line:
        return "bold bright_yellow"
    if "UNIT HIT ON ENTERPRISE" in line or "SHIELDS DOWN" in line:
        return "bright_red"
    if any(word in line for word in ("DAMAGED", "INOPERA", "NOT OPERATIONAL",
                                     "DISABLED", "NOT AVAILABLE", "DANGEROUSLY")):
        return "yellow"
    if "? " in line:                     # a prompt, and what you typed
        return "bright_cyan"
    return "white"


def log_panel(lines, width, height):
    width = max(10, width)
    wrapped = []
    for line in lines:
        style = _log_style(line)
        if not line:
            wrapped.append(Text(""))
            continue
        indent = " " * min(len(line) - len(line.lstrip(" ")), width // 2)
        for chunk in textwrap.wrap(line, width, subsequent_indent=indent + "  ",
                                   break_long_words=True) or [line[:width]]:
            wrapped.append(Text(chunk, style=style))
    tail = wrapped[-max(1, height):]
    return Panel(Text("\n").join(tail), title="LOG", border_style="bright_black")


def overlay_panel(title, lines):
    """COM 0 and COM 5 print big tables -- shown here until your next command."""
    body = Text("\n".join(lines).strip("\n"))
    return Panel(body, title=title, subtitle=" shown until your next command ",
                 border_style="bright_cyan")
