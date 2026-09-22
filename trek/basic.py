"""Microsoft BASIC emulation: number formatting and INPUT.

The 1978 listing's screen layout depends entirely on how MS BASIC's PRINT
formatted numbers.  If you use Python's str() you get output that is subtly
but visibly wrong -- columns don't line up and the spacing around every
number is missing.

MS BASIC PRINT rules for a numeric value:
  * one leading character, reserved for the sign: "-" or a space
  * one trailing space (the column separator)
  * integers print with no decimal point at all
  * a leading zero before the point is dropped:  0.5 prints as  .5
  * roughly 6 significant digits

So  PRINT "SECTOR";S1;",";S2  with S1=3, S2=2 gives

    SECTOR 3 , 2

...and that stray space before the comma is canon.
"""

import sys

TAB_STOP = " "


def bn(value) -> str:
    """Format a number the way MS BASIC's PRINT did.  Sign slot + trailing space."""
    if isinstance(value, bool):          # guard: bool is an int in Python
        value = int(value)

    if isinstance(value, float) and value == int(value):
        value = int(value)

    if isinstance(value, int):
        body = str(abs(value))
    else:
        body = f"{abs(value):.6g}"
        if body.startswith("0."):        # BASIC drops the leading zero
            body = body[1:]

    sign = "-" if value < 0 else " "
    return f"{sign}{body} "


def tab(column: int) -> str:
    """TAB(n) at the start of a print -- n spaces, near enough for our use."""
    return " " * max(0, column)


def rjust3(value: int) -> str:
    """RIGHT$(STR$(n+1000),3) -- zero-padding to 3 digits, 1974 style.

    Line 4210 and 7700.  There was no PRINT USING in 8K BASIC, so you added
    1000 and took the last three characters.  7 -> 1007 -> "007".
    """
    return str(int(value) + 1000)[-3:]


class Resigned(Exception):
    """Raised when input hits EOF or the player interrupts."""


def _readline(prompt: str) -> str:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    try:
        line = sys.stdin.readline()
    except KeyboardInterrupt:
        raise Resigned from None
    if line == "":
        raise Resigned
    return line.strip()


def input_str(prompt: str, reader=None) -> str:
    """INPUT"PROMPT";A$ -- BASIC appended "? " to the prompt.

    reader, if given, replaces the keyboard: it receives the full prompt and
    returns the line typed.  The screen UI passes its own, which redraws the
    display before reading.
    """
    return (reader or _readline)(f"{prompt}? ").upper()


def input_num(prompt: str, reader=None, say=print) -> float:
    """INPUT"PROMPT";X with BASIC's ?REDO FROM START on bad input."""
    read = reader or _readline
    while True:
        raw = read(f"{prompt}? ")
        try:
            return float(raw.replace(",", " ").split()[0]) if raw.strip() else 0.0
        except (ValueError, IndexError):
            say("?REDO FROM START")


def input_two_num(prompt: str, reader=None, say=print) -> tuple:
    """INPUT"PROMPT";A,B -- two values, comma or space separated."""
    read = reader or _readline
    while True:
        raw = read(f"{prompt}? ")
        parts = raw.replace(",", " ").split()
        try:
            return float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            say("?REDO FROM START")
