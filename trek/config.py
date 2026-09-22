"""Tunable constants for Super Star Trek.

Every magic number from SUPERSTARTREK.BAS (1978) lives here, named, with its
original BASIC line number.  The defaults ARE canon -- changing them changes
the game.

A note on what is actually safe to change
-----------------------------------------
Free:       initial_energy, initial_torpedoes, klingon_base_strength,
            mission_days_*, and the density thresholds.  Tune away.

Coupled:    galaxy_size and sector_size.  In the original these were the SAME
            constant -- line 475's FNR() picked a random 1-8 and was used for
            BOTH quadrant coordinates and sector coordinates.  Splitting them
            is the main thing this module buys you.

Welded in:  the quadrant-contents encoding at line 1040,

                G(I,J) = K3*100 + B3*10 + S3

            is base 10, so it structurally caps each quadrant at 9 klingons,
            9 starbases and 9 stars.  max_klingons_per_quadrant is capped at 3
            anyway by the K(3,3) array.  Raising either means changing the
            storage format, not a constant.

Balance:    the klingon count and the stardate clock are tuned for 8x8.  The
            original knew it -- line 1040 ends with a hand-rolled safety net
            ("if we rolled more klingons than there are days, extend the
            clock").  Change the grid and you want to derive the clock from
            the klingon count rather than roll it independently.

Phase 1 ships and tests canon (8x8) only.  Anything else is untested.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # --- geometry -------------------------------------------------------
    galaxy_size: int = 8          # 330  DIM G(8,8)   -- quadrants per side
    sector_size: int = 8          # 475  FNR()        -- sectors per side
    cell_width: int = 3           # 8670 "<*>" etc.   -- chars per sector
    max_klingons_per_quadrant: int = 3   # 330  DIM K(3,3)

    # --- the Enterprise -------------------------------------------------
    initial_energy: float = 3000.0        # 370  E=3000
    initial_torpedoes: int = 10           # 440  P=10
    device_count: int = 8                 # 330  DIM D(8)
    max_warp: float = 8.0                 # 2380 IF W1>0 AND W1<=8
    damaged_warp: float = 0.2             # 2360 IF D(1)<0 AND W1>.2
    warp_energy_per_unit: int = 8         # 2490 N=INT(W1*8+.5)
    maneuver_overhead: int = 10           # 3910 E=E-N-10
    torpedo_energy_cost: int = 2          # 4850 E=E-2

    # --- the opposition -------------------------------------------------
    klingon_base_strength: float = 200.0  # 440  S9=200
    # 1780  K(I,3) = S9 * (0.5 + RND(1))  -> 100..300 per ship
    klingon_strength_min: float = 0.5
    klingon_strength_spread: float = 1.0

    # --- galaxy generation (820-1040) -----------------------------------
    klingon_3_threshold: float = 0.98     # 850  2% of quadrants
    klingon_2_threshold: float = 0.95     # 860  3%
    klingon_1_threshold: float = 0.80     # 870  15%  (so 80% are empty)
    starbase_threshold: float = 0.96      # 980  4%

    # --- the mission clock (370) ----------------------------------------
    stardate_min_hundreds: int = 20       # T=INT(RND(1)*20+20)*100
    stardate_spread_hundreds: int = 20
    mission_days_base: int = 25           # T9=25+INT(RND(1)*10)
    mission_days_spread: int = 10

    # --- preserved bug (440) --------------------------------------------
    # B9=2.  The starbase counter starts at TWO and is never zeroed before
    # the counting loop at 980, so the briefing overstates the count by 2 and
    # the "no starbases exist, force one" fallback at 1150-1160 is dead code.
    # Set to 0 to fix.  Canon is 2.  See BUGS.md #1.
    starbase_count_start: int = 2

    # --- derived --------------------------------------------------------
    @property
    def row_stride(self) -> int:
        """Characters per row of the quadrant string (24 in canon)."""
        return self.sector_size * self.cell_width

    @property
    def quadrant_chars(self) -> int:
        """Total length of Q$ (192 in canon)."""
        return self.sector_size * self.row_stride


CANON = Config()
