"""The hint bar -- one line of help that changes with the prompt.

The command names are the easy part; typing anything the game doesn't
recognise already lists them, exactly as in 1978.  What stops beginners is
the prompts: "COURSE (0-9)?" means nothing until you know 1 is east and the
numbers run counterclockwise, and "NUMBER OF UNITS TO SHIELDS?" never says
it wants the new total rather than an amount to add.

So the bar shows the commands while the game is waiting for one, and switches
to a hint for whatever it is asking otherwise.  Every hint states a rule of
the 1978 game, and each is checked against trek/game.py -- the line numbers
are beside them.  Nothing here reveals game state; it is the instructions,
not the sensors.

Each entry has a full form and a short form for narrow terminals.
"""

from rich.text import Text

K = "bold bright_cyan"          # a thing you type
D = "white"                     # what it means

WELCOME = ("» New to this?  The commands are along the bottom; lower case is "
           "fine.  Try LRS to look around, then NAV to move.")


def _keys(*pairs):
    """[("NAV", "move"), ...] -> markup, keys highlighted."""
    return "  ".join(f"[{K}]{key}[/] [{D}]{meaning}[/]" for key, meaning in pairs)


COMMANDS = (
    _keys(("NAV", "move"), ("SRS", "short scan"), ("LRS", "long scan"),
          ("PHA", "phasers"), ("TOR", "torpedo"), ("SHE", "shields"),
          ("DAM", "damage"), ("COM", "computer"), ("XXX", "resign")),
    f"[{K}]NAV SRS LRS PHA TOR SHE DAM COM XXX[/]  [{D}]· anything else lists them[/]",
)

COMPASS = _keys(("1", "east"), ("2", "NE"), ("3", "north"), ("4", "NW"),
                ("5", "west"), ("6", "SW"), ("7", "south"), ("8", "SE"))
COMPASS_SHORT = f"[{K}]1[/]E [{K}]2[/]NE [{K}]3[/]N [{K}]4[/]NW [{K}]5[/]W [{K}]6[/]SW [{K}]7[/]S [{K}]8[/]SE"

SEP = f" [bright_black]·[/] "

# (prompt prefix, full, short) -- checked in order, so the more specific
# prefixes come first ("PHOTON TORPEDO COURSE" before "COURSE",
# "COMPUTER ACTIVE" before "COMMAND").
HINTS = [
    # 4760-4780: 0 is rejected before a torpedo or any energy is spent.
    # 5060-5110: no strength check on a hit.  5210: stars absorb it.
    ("PHOTON TORPEDO COURSE",
     f"[{D}]same compass as NAV[/]{SEP}[{D}]a hit always kills[/]{SEP}"
     f"[{D}]stars block it[/]{SEP}[{K}]COM 2[/] [{D}]gives exact courses[/]{SEP}"
     f"[{K}]0[/] [{D}]cancels[/]",
     f"{COMPASS_SHORT}{SEP}[{D}]a hit always kills[/]"),

    # 2300-2330: 9 means 1; anything outside 1..<9 is refused, costing nothing.
    ("COURSE",
     f"{COMPASS}{SEP}[{D}]see the numbers round your ship[/]{SEP}[{K}]0[/] [{D}]cancels[/]",
     f"{COMPASS_SHORT}{SEP}[{K}]0[/] [{D}]cancels[/]"),

    # 2490: N=INT(W1*8+.5) sectors.  3910: energy N+10.  3870: a new
    # quadrant costs exactly 1 stardate whatever the warp.  2590-2700:
    # klingons in the quadrant reposition and fire before you move.
    ("WARP FACTOR",
     f"[{K}]1[/] [{D}]= one quadrant[/]{SEP}[{D}]any new quadrant costs 1 stardate[/]{SEP}"
     f"[{D}]energy = 8×warp + 10[/]{SEP}[{D}]Klingons here shoot first[/]",
     f"[{K}]1[/] [{D}]= one quadrant, 1 stardate[/]{SEP}[{K}]0[/] [{D}]cancels[/]"),

    # 4450: H1=INT(X/K3), split evenly.  4480: divided by distance.
    # 4480-4500: under 15% of the target's strength registers nothing.
    # 4370: 0 or less returns before any energy is spent.
    ("NUMBER OF UNITS TO FIRE",
     f"[{D}]split between all Klingons here, weaker with distance[/]{SEP}"
     f"[{D}]under 15% of a ship's strength does nothing[/]{SEP}[{K}]0[/] [{D}]cancels[/]",
     f"[{D}]splits across all Klingons here[/]{SEP}[{K}]0[/] [{D}]cancels[/]"),

    # 5630: S=X -- the new total, with E=E+S-X moving energy either way.
    # 6060-6090: a hit is taken off shields; at zero or below you are destroyed.
    ("NUMBER OF UNITS TO SHIELDS",
     f"[{D}]the new[/] [{K}]TOTAL[/][{D}], not an amount to add[/]{SEP}"
     f"[{D}]lower it to take energy back[/]{SEP}[{D}]a hit that empties them destroys you[/]",
     f"[{D}]the new[/] [{K}]TOTAL[/][{D}], not an amount to add[/]"),

    # 7350-7380
    ("COMPUTER ACTIVE",
     _keys(("0", "galaxy record"), ("1", "status"), ("2", "torpedo courses"),
           ("3", "course to starbase"), ("4", "calculator"), ("5", "region names")),
     _keys(("0", "record"), ("1", "status"), ("2", "torpedo"), ("3", "base"),
           ("4", "calc"), ("5", "names"))),

    # 5840-5890: repairs everything, T=T+D3+.1.  2770-2880: damage also
    # mends by up to 1 per move at warp.
    ("WILL YOU AUTHORIZE THE REPAIR",
     f"[{K}]Y[/] [{D}]repairs everything now, for the stardates shown[/]{SEP}"
     f"[{K}]N[/] [{D}]leaves it -- damage also mends slowly as you travel[/]",
     f"[{K}]Y[/] [{D}]repairs now, costing stardates[/]"),

    # 8170-8200: the listing says (X,Y), but it is row then column.
    ("INITIAL COORDINATES",
     f"[{D}]a sector as[/] [{K}]row,col[/][{D}] -- 3,5 is row 3 from the top, column 5[/]",
     f"[{K}]row,col[/]"),
    ("FINAL COORDINATES",
     f"[{D}]a sector as[/] [{K}]row,col[/][{D}] -- 3,5 is row 3 from the top, column 5[/]",
     f"[{K}]row,col[/]"),

    # 6330
    ("LET HIM STEP FORWARD",
     f"[{K}]AYE[/] [{D}]for a new galaxy[/]{SEP}[{D}]anything else to stop[/]",
     f"[{K}]AYE[/] [{D}]to play again[/]"),

    ("COMMAND", COMMANDS[0], COMMANDS[1]),
]


def asks_for_course(prompt):
    """True for NAV's and TOR's course prompts -- time to draw the compass."""
    return "COURSE (" in prompt


def for_prompt(prompt, width):
    """The hint for a prompt, in the widest form that fits.

    Returns an empty Text during animation frames, when nothing is asked.
    """
    if not prompt:
        return Text("")
    key = prompt.strip().rstrip("?").strip()
    for prefix, full, short in HINTS:
        if key.startswith(prefix):
            break
    else:
        full, short = COMMANDS
    for markup in (full, short):
        text = Text.from_markup(" " + markup)
        if text.cell_len <= width:
            return text
    text.truncate(width, overflow="ellipsis")
    return text
