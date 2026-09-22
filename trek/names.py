"""Quadrant region names.  Lines 9030-9260.

The galaxy's left half (columns 1-4) is named from one list of eight stars,
the right half (columns 5-8) from another, indexed by row.  The column then
adds a roman numeral I-IV, repeating across both halves.

So quadrant (1,1) is "ANTARES I" and (1,5) is "SIRIUS I".
"""

# 9040-9110 -- used when Z5 (the column) is 1..4
WEST = [
    None,
    "ANTARES",      # 9040
    "RIGEL",        # 9050
    "PROCYON",      # 9060
    "VEGA",         # 9070
    "CANOPUS",      # 9080
    "ALTAIR",       # 9090
    "SAGITTARIUS",  # 9100
    "POLLUX",       # 9110
]

# 9130-9200 -- used when Z5 is 5..8
EAST = [
    None,
    "SIRIUS",       # 9130
    "DENEB",        # 9140
    "CAPELLA",      # 9150
    "BETELGEUSE",   # 9160
    "ALDEBARAN",    # 9170
    "REGULUS",      # 9180
    "ARCTURUS",     # 9190
    "SPICA",        # 9200
]

# 9210 -- ON Z5 GOTO 9230,9240,9250,9260,9230,9240,9250,9260
SUFFIX = [None, " I", " II", " III", " IV", " I", " II", " III", " IV"]


def quadrant_name(row: int, col: int, region_only: bool = False) -> str:
    """9030: quadrant name from Z4,Z5.  region_only is BASIC's G5=1."""
    row = max(1, min(8, int(row)))
    col = max(1, min(8, int(col)))
    name = WEST[row] if col <= 4 else EAST[row]
    if region_only:
        return name
    return name + SUFFIX[col]
