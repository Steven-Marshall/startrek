"""Super Star Trek (1978) -- engine.

A transliteration of SUPERSTARTREK.BAS, the listing published in David Ahl's
BASIC Computer Games (Microcomputer Edition, 1978).  Original by Mike Mayfield
(1971), reworked by Bob Leedom (1974), converted to Microsoft 8K BASIC by
John Gorders (1978).

The point of this file is fidelity, not elegance.  Formulas are copied across
verbatim with the originating BASIC line number in a comment beside them, so
any behaviour can be traced back to the listing.  Where the original is odd,
it stays odd; see BUGS.md for what was preserved deliberately.

Two things are deliberately NOT modernised:

  * the quadrant stays a flat 192-character string (Q$), sliced three
    characters at a time, exactly as line 8670 did it.  It is the single most
    characterful thing in the program, and the Phase 2 renderer can read it
    directly without the engine needing to know it exists.

  * all arrays are 1-based, with index 0 left unused, so K(I,3) in the
    listing is self.k[i][3] here.

BASIC -> Python name map
------------------------
  Q1,Q2  qrow,qcol       quadrant coordinates     S1,S2  srow,scol   sector
  E,E0   energy,energy0   T,T0  stardate,stardate0   T9   mission_days
  S      shields          S9    cfg.klingon_base_strength
  P,P0   torpedoes,torpedoes0   D()  damage[1..8]    D0   docked
  D4     repair_fudge     G()   galaxy[r][c]         Z()  chart[r][c]
  Q$     q                C()   course[dir][1..2]    C$   condition
  K()    k[i][1..3]       K3    k_here    K9  klingons_left   K7 klingons_start
  B3     bases_here       B9    bases_total    B4,B5  base_row,base_col
  S3     stars_here       A1$   COMMANDS
"""

import math
import random

from .basic import bn, tab, rjust3, input_str, input_num, input_two_num
from .config import CANON
from .names import quadrant_name

EMPTY = "   "
SHIP = "<*>"
KLINGON = "+K+"
STARBASE = ">!<"
STAR = " * "

# 710  A1$="NAVSRSLRSPHATORSHEDAMCOMXXX"
COMMANDS = ["NAV", "SRS", "LRS", "PHA", "TOR", "SHE", "DAM", "COM", "XXX"]

# 8792-8806
DEVICES = [
    None,
    "WARP ENGINES",
    "SHORT RANGE SENSORS",
    "LONG RANGE SENSORS",
    "PHASER CONTROL",
    "PHOTON TUBES",
    "DAMAGE CONTROL",
    "SHIELD CONTROL",
    "LIBRARY-COMPUTER",
]


class MissionEnd(Exception):
    """Jump to the end-of-game block (6210-6400)."""

    def __init__(self, kind):
        super().__init__(kind)
        self.kind = kind          # stardate | destroyed | won | resign | relieved


class Game:
    def __init__(self, cfg=CANON, seed=None, out=print,
                 ask_str=None, ask_num=None, ask_two=None, event=None):
        self.cfg = cfg
        self.rng = random.Random(seed)
        # I/O seams.  The engine never calls print() or input() directly, so a
        # front end (Phase 2, or a test) can drive it without touching stdio.
        self.out = out
        self.ask_str = ask_str or input_str
        self.ask_num = ask_num or input_num
        self.ask_two = ask_two or input_two_num
        # Events are annotations for a front end: moments worth animating,
        # and markers around blocks of output that a screen UI shows in a
        # panel instead of the log.  They never change behaviour, and the
        # Phase 1 teletype ignores them entirely.
        self.event = event or (lambda name, **info: None)
        self.new_game()

    # =================================================================
    # Setup  (270-1280)
    # =================================================================
    def new_game(self):
        cfg = self.cfg
        n = cfg.galaxy_size

        # 370
        self.stardate = int(self.rng.random() * cfg.stardate_spread_hundreds
                            + cfg.stardate_min_hundreds) * 100
        self.stardate0 = self.stardate
        self.mission_days = cfg.mission_days_base + int(
            self.rng.random() * cfg.mission_days_spread)
        self.docked = 0
        self.energy = cfg.initial_energy
        self.energy0 = self.energy

        # 440
        self.torpedoes = cfg.initial_torpedoes
        self.torpedoes0 = self.torpedoes
        self.shields = 0.0
        self.bases_total = cfg.starbase_count_start      # BUG #1: canon is 2
        self.klingons_left = 0

        # 530-600  the compass.  Direction 1 is east, going counterclockwise;
        # 9 wraps back round to 1 so fractional courses can interpolate.
        self.course = [[0, 0, 0] for _ in range(10)]
        self.course[3][1] = -1
        self.course[2][1] = -1
        self.course[4][1] = -1
        self.course[4][2] = -1
        self.course[5][2] = -1
        self.course[6][2] = -1
        self.course[1][2] = 1
        self.course[2][2] = 1
        self.course[6][1] = 1
        self.course[7][1] = 1
        self.course[8][1] = 1
        self.course[8][2] = 1
        self.course[9][2] = 1

        # 670
        self.damage = [0.0] * (cfg.device_count + 1)

        # 490  initial position
        self.qrow, self.qcol = self.fnr(), self.fnr()
        self.srow, self.scol = self.fnr(), self.fnr()

        # 330  K(3,3), G(8,8), Z(8,8)
        self.k = [[0, 0, 0, 0] for _ in range(cfg.max_klingons_per_quadrant + 1)]
        self.galaxy = [[0] * (n + 1) for _ in range(n + 1)]
        self.chart = [[0] * (n + 1) for _ in range(n + 1)]

        self.q = EMPTY * (cfg.sector_size ** 2)
        self.condition = "GREEN"
        self.k_here = 0
        self.bases_here = 0
        self.stars_here = 0
        self.base_row = 0
        self.base_col = 0
        self.repair_fudge = 0.0
        self.klingons_start = 0

        self._build_galaxy()

    def _build_galaxy(self):
        """820-1200.  Sprinkle klingons, starbases and stars across the grid."""
        cfg = self.cfg
        n = cfg.galaxy_size

        for i in range(1, n + 1):
            for j in range(1, n + 1):
                k3 = 0
                self.chart[i][j] = 0
                r1 = self.rng.random()
                if r1 > cfg.klingon_3_threshold:            # 850
                    k3 = 3
                elif r1 > cfg.klingon_2_threshold:          # 860
                    k3 = 2
                elif r1 > cfg.klingon_1_threshold:          # 870
                    k3 = 1
                self.klingons_left += k3

                b3 = 0                                       # 980
                if self.rng.random() > cfg.starbase_threshold:
                    b3 = 1
                    self.bases_total += 1

                # 1040  the base-10 encoding: one integer per quadrant
                self.galaxy[i][j] = k3 * 100 + b3 * 10 + self.fnr()

        # 1040  balance patch: never fewer days than klingons
        if self.klingons_left > self.mission_days:
            self.mission_days = self.klingons_left + 1

        # 1100-1160  dead code in canon (bases_total starts at 2, never 0).
        # Preserved verbatim; it only runs if starbase_count_start is 0.
        if self.bases_total == 0:
            if self.galaxy[self.qrow][self.qcol] < 200:      # 1150
                self.galaxy[self.qrow][self.qcol] += 120
                self.klingons_left += 1
            self.bases_total = 1                             # 1160
            self.galaxy[self.qrow][self.qcol] += 10
            self.qrow, self.qcol = self.fnr(), self.fnr()

        self.klingons_start = self.klingons_left             # 1200

    def print_orders(self):
        """1230-1280  the mission briefing."""
        plural = "S" if self.bases_total != 1 else ""
        verb = " ARE " if self.bases_total != 1 else " IS "
        self.out("YOUR ORDERS ARE AS FOLLOWS:")
        self.out(f"     DESTROY THE{bn(self.klingons_left)}KLINGON WARSHIPS WHICH HAVE INVADED")
        self.out("   THE GALAXY BEFORE THEY CAN ATTACK FEDERATION HEADQUARTERS")
        self.out(f"   ON STARDATE{bn(self.stardate0 + self.mission_days)}  THIS GIVES YOU"
                 f"{bn(self.mission_days)}DAYS.  THERE{verb}")
        self.out(f"  {bn(self.bases_total)}STARBASE{plural} IN THE GALAXY FOR RESUPPLYING YOUR SHIP")
        self.out("")

    # =================================================================
    # Small subroutines
    # =================================================================
    def fnr(self):
        """475  DEF FNR(R)=INT(RND(R)*7.98+1.01) -- a random 1..8.

        Why 7.98 and 1.01 rather than 8 and 1?  Some BASICs could return
        exactly 1.0 from RND, which would yield 9 and index off the array.
        That is a 1974 programmer who had been burned.
        """
        n = self.cfg.sector_size
        return int(self.rng.random() * (n - 0.02) + 1.01)

    def distance_to(self, i):
        """470  DEF FND(D)=SQR((K(I,1)-S1)^2+(K(I,2)-S2)^2)

        The original ignored its argument entirely and read the global I,
        which worked only because it was always called inside FOR I=1 TO 3.
        Here it takes a real index.
        """
        return math.sqrt((self.k[i][1] - self.srow) ** 2
                         + (self.k[i][2] - self.scol) ** 2)

    def cell(self, row, col):
        """8830  MID$(Q$,S8,3) -- read a sector, rounding the coordinates."""
        w = self.cfg.cell_width
        row = math.floor(row + 0.5)
        col = math.floor(col + 0.5)
        s8 = (col - 1) * w + (row - 1) * self.cfg.row_stride + 1
        if s8 < 1 or s8 + w - 1 > len(self.q):
            return EMPTY
        return self.q[s8 - 1:s8 - 1 + w]

    def put(self, row, col, what):
        """8670  rebuild Q$ around a three-character insert.

        Strings were immutable, so placing one object reallocated the whole
        192-character quadrant.  The S8=1 and S8=190 special cases in the
        original exist because LEFT$(x,0) was an error in some dialects;
        Python slicing handles those ends without help.
        """
        assert len(what) == self.cfg.cell_width, "ERROR"     # 8675
        w = self.cfg.cell_width
        s8 = (math.floor(col - 0.5) * w
              + math.floor(row - 0.5) * self.cfg.row_stride + 1)
        self.q = self.q[:s8 - 1] + what + self.q[s8 - 1 + w:]

    def find_empty(self):
        """8590  keep rolling coordinates until one lands on blank space."""
        while True:
            r1, r2 = self.fnr(), self.fnr()
            if self.cell(r1, r2) == EMPTY:
                return r1, r2

    def device_name(self, i):
        return DEVICES[i]                                    # 8790

    def _interpolate(self, c1):
        """3110/3140/4850  fractional courses blend two compass entries."""
        base = int(c1)
        frac = c1 - base
        x1 = (self.course[base][1]
              + (self.course[base + 1][1] - self.course[base][1]) * frac)
        x2 = (self.course[base][2]
              + (self.course[base + 1][2] - self.course[base][2]) * frac)
        return x1, x2

    # =================================================================
    # Entering a quadrant  (1310-1980)
    # =================================================================
    def enter_quadrant(self):
        cfg = self.cfg
        n = cfg.galaxy_size

        # 1320
        self.k_here = 0
        self.bases_here = 0
        self.stars_here = 0
        self.repair_fudge = 0.5 * self.rng.random()
        self.chart[self.qrow][self.qcol] = self.galaxy[self.qrow][self.qcol]

        in_bounds = 1 <= self.qrow <= n and 1 <= self.qcol <= n     # 1390
        if in_bounds:
            name = quadrant_name(self.qrow, self.qcol)              # 1430
            self.out("")
            if self.stardate0 == self.stardate:
                self.out("YOUR MISSION BEGINS WITH YOUR STARSHIP LOCATED")
                self.out(f"IN THE GALACTIC QUADRANT, '{name}'.")
            else:
                self.out(f"NOW ENTERING {name} QUADRANT . . .")
            self.out("")

            # 1500-1540  decode the base-10 quadrant value back out
            g = self.galaxy[self.qrow][self.qcol]
            self.k_here = int(g * 0.01)
            self.bases_here = int(g * 0.1) - 10 * self.k_here
            self.stars_here = g - 100 * self.k_here - 10 * self.bases_here

            if self.k_here != 0:                                    # 1560
                self.out("COMBAT AREA      CONDITION RED")
                if self.shields <= 200:
                    self.out("   SHIELDS DANGEROUSLY LOW")

            for i in range(1, cfg.max_klingons_per_quadrant + 1):   # 1590
                self.k[i][1] = 0
                self.k[i][2] = 0

        for i in range(1, cfg.max_klingons_per_quadrant + 1):       # 1600
            self.k[i][3] = 0
        self.q = EMPTY * (cfg.sector_size ** 2)

        # 1660-1910  place the Enterprise, then everything else around it
        self.put(self.srow, self.scol, SHIP)                        # 1680
        for i in range(1, self.k_here + 1):                         # 1720
            r1, r2 = self.find_empty()
            self.put(r1, r2, KLINGON)
            self.k[i][1] = r1
            self.k[i][2] = r2
            self.k[i][3] = cfg.klingon_base_strength * (
                cfg.klingon_strength_min
                + self.rng.random() * cfg.klingon_strength_spread)  # 1780
        if self.bases_here >= 1:                                    # 1880
            r1, r2 = self.find_empty()
            self.put(r1, r2, STARBASE)
            self.base_row, self.base_col = r1, r2
        for _ in range(int(self.stars_here)):                       # 1910
            r1, r2 = self.find_empty()
            self.put(r1, r2, STAR)

        self.short_range_scan()                                     # 1980

    def check_stranded(self):
        """1990-2050  out of energy with no way to get any back."""
        if self.shields + self.energy > 10 and (self.energy > 10 or self.damage[7] == 0):
            return
        self.out("")
        self.out("** FATAL ERROR **   YOU'VE JUST STRANDED YOUR SHIP IN ")
        self.out("SPACE")
        self.out("YOU HAVE INSUFFICIENT MANEUVERING ENERGY, AND SHIELD CONTROL")
        self.out("IS PRESENTLY INCAPABLE OF CROSS-CIRCUITING TO ENGINE ROOM!!")
        raise MissionEnd("stardate")                                # 6220

    # =================================================================
    # Main loop  (2060-2260)
    # =================================================================
    def command_loop(self):
        dispatch = {                                                # 2140
            "NAV": self.navigate,
            "SRS": self.short_range_scan,
            "LRS": self.long_range_scan,
            "PHA": self.phasers,
            "TOR": self.torpedo,
            "SHE": self.shield_control,
            "DAM": self.damage_control,
            "COM": self.library_computer,
            "XXX": self.resign,
        }
        while True:
            self.check_stranded()                                   # 1990
            verb = self.ask_str("COMMAND")[:3]                         # 2060, 2080
            if verb in dispatch:
                dispatch[verb]()
            else:
                self.out("ENTER ONE OF THE FOLLOWING:")             # 2160
                self.out("  NAV  (TO SET COURSE)")
                self.out("  SRS  (FOR SHORT RANGE SENSOR SCAN)")
                self.out("  LRS  (FOR LONG RANGE SENSOR SCAN)")
                self.out("  PHA  (TO FIRE PHASERS)")
                self.out("  TOR  (TO FIRE PHOTON TORPEDOES)")
                self.out("  SHE  (TO RAISE OR LOWER SHIELDS)")
                self.out("  DAM  (FOR DAMAGE CONTROL REPORTS)")
                self.out("  COM  (TO CALL ON LIBRARY-COMPUTER)")
                self.out("  XXX  (TO RESIGN YOUR COMMAND)")
                self.out("")

    def resign(self):
        raise MissionEnd("resign")                                  # 6270

    # =================================================================
    # NAV  (2290-3870)
    # =================================================================
    def navigate(self):
        c1 = self.ask_num("COURSE (0-9)")                              # 2300
        if c1 == 9:
            c1 = 1
        if not (1 <= c1 < 9):                                       # 2310
            self.out("   LT. SULU REPORTS, 'INCORRECT COURSE DATA, SIR!'")
            return

        limit = "0.2" if self.damage[1] < 0 else "8"                # 2350
        w1 = self.ask_num(f"WARP FACTOR (0-{limit})")               # 2360
        if self.damage[1] < 0 and w1 > self.cfg.damaged_warp:
            self.out("WARP ENGINES ARE DAMAGED.  MAXIUM SPEED = WARP 0.2")   # 2470
            return
        if not (0 < w1 <= self.cfg.max_warp):                       # 2380
            if w1 == 0:                                             # 2390
                return
            self.out(f"   CHIEF ENGINEER SCOTT REPORTS 'THE ENGINES WON'T TAKE"
                     f" WARP{bn(w1)}!'")                            # 2420
            return

        n = int(w1 * self.cfg.warp_energy_per_unit + 0.5)           # 2490
        if self.energy - n < 0:
            self.out("ENGINEERING REPORTS   'INSUFFICIENT ENERGY AVAILABLE")  # 2500
            self.out(f"                       FOR MANEUVERING AT WARP{bn(w1)}!'")
            if self.shields < n - self.energy or self.damage[7] < 0:   # 2530
                return
            self.out(f"DEFLECTOR CONTROL ROOM ACKNOWLEDGES{bn(self.shields)}UNITS OF ENERGY")
            self.out("                         PRESENTLY DEPLOYED TO SHIELDS.")
            return

        # 2590  klingons reposition themselves, then fire on the moving ship
        for i in range(1, self.k_here + 1):
            if self.k[i][3] == 0:
                continue
            self.put(self.k[i][1], self.k[i][2], EMPTY)             # 2610
            z1, z2 = self.find_empty()
            self.k[i][1], self.k[i][2] = z1, z2                     # 2660
            self.put(z1, z2, KLINGON)
        self.klingons_fire()                                        # 2700

        # 2700-3030  repairs accrue with time spent at warp, then a random
        # device either degrades or spontaneously improves
        d1 = 0
        d6 = 1 if w1 >= 1 else w1
        for i in range(1, self.cfg.device_count + 1):                # 2770
            if self.damage[i] >= 0:
                continue
            self.damage[i] += d6                                     # 2790
            if -0.1 < self.damage[i] < 0:
                self.damage[i] = -0.1
                continue
            if self.damage[i] < 0:                                   # 2800
                continue
            if d1 != 1:                                              # 2810
                d1 = 1
                self.out("DAMAGE CONTROL REPORT:  ")
            self.out(f"{tab(8)}{self.device_name(i)} REPAIR COMPLETED.")   # 2840

        if self.rng.random() <= 0.2:                                 # 2880
            r1 = self.fnr()                                          # 2910
            if self.rng.random() < 0.6:
                self.damage[r1] -= self.rng.random() * 5 + 1         # 2930
                self.out("DAMAGE CONTROL REPORT:  ")
                self.out(f"{self.device_name(r1)} DAMAGED")
                self.out("")
            else:
                self.damage[r1] += self.rng.random() * 3 + 1         # 3000
                self.out("DAMAGE CONTROL REPORT:  ")
                self.out(f"{self.device_name(r1)} STATE OF REPAIR IMPROVED")
                self.out("")

        # 3070  lift off
        self.put(int(self.srow), int(self.scol), EMPTY)
        x1, x2 = self._interpolate(c1)                               # 3110/3140
        x, y = self.srow, self.scol
        q4, q5 = self.qrow, self.qcol

        left_quadrant = False
        for _ in range(n):                                           # 3170
            self.srow += x1
            self.scol += x2
            if (self.srow < 1 or self.srow >= self.cfg.sector_size + 1
                    or self.scol < 1 or self.scol >= self.cfg.sector_size + 1):
                left_quadrant = True                                 # 3500
                break
            # 3240  note this reads only TWO characters, not three: a star
            # is " * " so its first two chars differ from "  ".  Economy.
            s8 = (int(self.srow) * self.cfg.row_stride
                  + int(self.scol) * self.cfg.cell_width
                  - (self.cfg.row_stride + self.cfg.cell_width - 1))
            if self.q[s8 - 1:s8 + 1] == "  ":
                continue
            self.srow = int(self.srow - x1)                          # 3320
            self.scol = int(self.scol - x2)
            self.out("WARP ENGINES SHUT DOWN AT ")
            self.out(f"SECTOR{bn(self.srow)},{bn(self.scol)}DUE TO BAD NAVAGATION")
            break
        else:
            self.srow = int(self.srow)                               # 3360
            self.scol = int(self.scol)

        if left_quadrant:
            self._exceeded_quadrant_limits(x, y, n, w1, x1, x2, q4, q5)
            return

        self._arrive(n, w1)                                          # 3370

    def _arrive(self, n, w1):
        """3370-3480  set down in the current quadrant and burn the clock."""
        self.put(int(self.srow), int(self.scol), SHIP)
        self.maneuver_energy(n)                                      # 3910
        t8 = 1 if w1 >= 1 else 0.1 * int(10 * w1)                    # 3430
        self.stardate += t8                                          # 3450
        if self.stardate > self.stardate0 + self.mission_days:
            raise MissionEnd("stardate")                             # 6220
        self.short_range_scan()                                      # 3480 -> 1980

    def _exceeded_quadrant_limits(self, x, y, n, w1, x1, x2, q4, q5):
        """3500-3870  crossing into a new quadrant, or bouncing off the rim."""
        size = self.cfg.sector_size
        x = size * self.qrow + x + n * x1                            # 3500
        y = size * self.qcol + y + n * x2
        self.qrow = int(x / size)
        self.qcol = int(y / size)
        self.srow = int(x - self.qrow * size)
        self.scol = int(y - self.qcol * size)                        # 3550
        if self.srow == 0:
            self.qrow -= 1
            self.srow = size
        if self.scol == 0:                                           # 3590
            self.qcol -= 1
            self.scol = size

        hit_rim = False                                              # 3620
        if self.qrow < 1:
            hit_rim, self.qrow, self.srow = True, 1, 1
        if self.qrow > self.cfg.galaxy_size:                         # 3670
            hit_rim, self.qrow, self.srow = True, self.cfg.galaxy_size, size
        if self.qcol < 1:                                            # 3710
            hit_rim, self.qcol, self.scol = True, 1, 1
        if self.qcol > self.cfg.galaxy_size:                         # 3750
            hit_rim, self.qcol, self.scol = True, self.cfg.galaxy_size, size

        if hit_rim:                                                  # 3790
            self.out("LT. UHURA REPORTS MESSAGE FROM STARFLEET COMMAND:")
            self.out("  'PERMISSION TO ATTEMPT CROSSING OF GALACTIC PERIMETER")
            self.out("  IS HEREBY *DENIED*.  SHUT DOWN YOUR ENGINES.'")
            self.out("CHIEF ENGINEER SCOTT REPORTS  'WARP ENGINES SHUT DOWN")
            self.out(f"  AT SECTOR{bn(self.srow)},{bn(self.scol)}OF QUADRANT"
                     f"{bn(self.qrow)},{bn(self.qcol)}.'")
            if self.stardate > self.stardate0 + self.mission_days:   # 3850
                raise MissionEnd("stardate")

        # 3860  did we actually change quadrant?  If not -- typically after
        # bouncing off the rim back into the quadrant we started in -- the
        # original GOTOs 3370, which charges stardates exactly like any other
        # in-quadrant move.  (An earlier version of this port inlined 3370
        # here and forgot 3430-3450, making rim bounces free.)
        if (size * self.qrow + self.qcol) == (size * q4 + q5):
            self._arrive(n, w1)                                      # -> 3370
            return

        self.stardate += 1                                           # 3870
        self.maneuver_energy(n)
        self.enter_quadrant()                                        # -> 1320

    def maneuver_energy(self, n):
        """3910-3980  warp costs N+10, and shields will cover the shortfall."""
        self.energy = self.energy - n - self.cfg.maneuver_overhead
        if self.energy >= 0:
            return
        self.out("SHIELD CONTROL SUPPLIES ENERGY TO COMPLETE THE MANEUVER.")
        self.shields += self.energy                                  # 3940
        self.energy = 0
        if self.shields <= 0:
            self.shields = 0

    # =================================================================
    # LRS  (3990-4230)
    # =================================================================
    def long_range_scan(self):
        if self.damage[3] < 0:                                       # 4000
            self.out("LONG RANGE SENSORS ARE INOPERABLE")
            return
        n = self.cfg.galaxy_size
        self.event("begin", kind="lrs")
        self.out(f"LONG RANGE SCAN FOR QUADRANT{bn(self.qrow)},{bn(self.qcol)}")
        rule = "-" * 19                                              # 4040
        self.out(rule)
        for i in range(self.qrow - 1, self.qrow + 2):                # 4060
            vals = [None, -1, -2, -3]
            for j in range(self.qcol - 1, self.qcol + 2):
                if 1 <= i <= n and 1 <= j <= n:                      # 4120
                    vals[j - self.qcol + 2] = self.galaxy[i][j]
                    self.chart[i][j] = self.galaxy[i][j]
            row = ""
            for l in range(1, 4):                                    # 4180
                row += ": "
                # 4210  RIGHT$(STR$(n+1000),3) -- zero-pad, 1974 style
                row += "*** " if vals[l] < 0 else rjust3(vals[l]) + " "
            self.out(row + ":")                                      # 4230
            self.out(rule)
        self.event("end", kind="lrs")

    # =================================================================
    # PHA  (4250-4670)
    # =================================================================
    def phasers(self):
        if self.damage[4] < 0:                                       # 4260
            self.out("PHASERS INOPERATIVE")
            return
        if self.k_here <= 0:                                         # 4265
            self.out("SCIENCE OFFICER SPOCK REPORTS  'SENSORS SHOW NO ENEMY SHIPS")
            self.out("                                IN THIS QUADRANT'")
            return
        if self.damage[8] < 0:                                       # 4330
            self.out("COMPUTER FAILURE HAMPERS ACCURACY")
        self.out("PHASERS LOCKED ON TARGET;  ")

        while True:                                                  # 4360
            self.out(f"ENERGY AVAILABLE ={bn(self.energy)}UNITS")
            x = self.ask_num("NUMBER OF UNITS TO FIRE")                 # 4370
            if x <= 0:
                return
            if self.energy - x >= 0:                                 # 4400
                break

        self.energy -= x                                             # 4410
        if self.damage[7] < 0:
            # BUG #8, preserved: the penalty keys off D(7), SHIELD CONTROL,
            # while the warning at 4330 keys off D(8), the COMPUTER.  So a
            # damaged computer warns you and costs nothing, and damaged
            # shield control costs you up to 100% of the volley silently.
            x = x * self.rng.random()

        h1 = int(x / self.k_here)                                    # 4450
        for i in range(1, self.cfg.max_klingons_per_quadrant + 1):
            if self.k[i][3] <= 0:
                continue
            h = int((h1 / self.distance_to(i)) * (self.rng.random() + 2))   # 4480
            self.event("phaser", row=self.k[i][1], col=self.k[i][2],
                       hit=h if h > 0.15 * self.k[i][3] else 0)
            if h <= 0.15 * self.k[i][3]:
                self.out(f"SENSORS SHOW NO DAMAGE TO ENEMY AT {bn(self.k[i][1])},"
                         f"{bn(self.k[i][2])}")                      # 4500
                continue
            self.k[i][3] -= h                                        # 4530
            self.out(f"{bn(h)}UNIT HIT ON KLINGON AT SECTOR{bn(self.k[i][1])},"
                     f"{bn(self.k[i][2])}")
            if self.k[i][3] > 0:                                     # 4560
                self.out(f"   (SENSORS SHOW{bn(self.k[i][3])}UNITS REMAINING)")
                continue
            self.event("explode", row=self.k[i][1], col=self.k[i][2], what=KLINGON)
            self.out("*** KLINGON DESTROYED ***")                    # 4550
            self.k_here -= 1                                         # 4580
            self.klingons_left -= 1
            self.put(self.k[i][1], self.k[i][2], EMPTY)
            self.k[i][3] = 0                                         # 4650
            self.galaxy[self.qrow][self.qcol] -= 100
            self.chart[self.qrow][self.qcol] = self.galaxy[self.qrow][self.qcol]
            if self.klingons_left <= 0:
                raise MissionEnd("won")                              # 6370
        self.klingons_fire()                                         # 4670

    # =================================================================
    # TOR  (4690-5490)
    # =================================================================
    def torpedo_track(self, c1):
        """4850-4960 as a pure walk.  No output, no state changes.

        Yields (x, y, x3, y3, what) for each sector the torpedo enters, where
        x,y are the exact float position, x3,y3 the rounded sector, and what
        is its contents.  Stops after the first non-empty sector.  If the
        torpedo leaves the quadrant, yields a final entry with what=None.

        torpedo() drives the real shot from this, and the Phase 2 cadet
        overlay previews with it, so the preview cannot lie.
        """
        x1, x2 = self._interpolate(c1)                               # 4850
        x, y = self.srow, self.scol                                  # 4860
        size = self.cfg.sector_size
        while True:
            x += x1                                                  # 4920
            y += x2
            x3, y3 = int(x + 0.5), int(y + 0.5)
            if not (1 <= x3 <= size and 1 <= y3 <= size):            # 4960
                yield x, y, x3, y3, None
                return
            what = self.cell(x, y)                                   # 5000-5060
            yield x, y, x3, y3, what
            if what != EMPTY:
                return

    def torpedo(self):
        if self.torpedoes <= 0:                                      # 4700
            self.out("ALL PHOTON TORPEDOES EXPENDED")
            return
        if self.damage[5] < 0:                                       # 4730
            self.out("PHOTON TUBES ARE NOT OPERATIONAL")
            return

        while True:
            c1 = self.ask_num("PHOTON TORPEDO COURSE (1-9)")            # 4760
            if c1 == 9:
                c1 = 1
            if not (1 <= c1 < 9):                                    # 4780
                self.out("ENSIGN CHEKOV REPORTS,  'INCORRECT COURSE DATA, SIR!'")
                return

            self.energy -= self.cfg.torpedo_energy_cost              # 4850
            self.torpedoes -= 1
            self.out("TORPEDO TRACK:")                               # 4910

            retry_course = False
            for x, y, x3, y3, what in self.torpedo_track(c1):
                if what is None:                                     # 4960
                    self.event("torpedo_missed")
                    self.out("TORPEDO MISSED")                       # 5490
                    self.klingons_fire()
                    return
                self.out(f"               {bn(x3)},{bn(y3)}")        # 5000
                self.event("torpedo_step", row=x3, col=y3)
                if what == EMPTY:                                    # 5050
                    continue
                if what == KLINGON:                                  # 5060
                    # No strength check: a hit is a kill.  See README.
                    self.event("explode", row=x3, col=y3, what=KLINGON)
                    self.out("*** KLINGON DESTROYED ***")            # 5110
                    self.k_here -= 1
                    self.klingons_left -= 1
                    if self.klingons_left <= 0:
                        raise MissionEnd("won")                      # 6370
                    hit = self.cfg.max_klingons_per_quadrant         # 5150/5180
                    for i in range(1, self.cfg.max_klingons_per_quadrant + 1):
                        if x3 == self.k[i][1] and y3 == self.k[i][2]:
                            hit = i
                            break
                    self.k[hit][3] = 0                               # 5190
                    break                                            # -> 5430
                if what == STAR:                                     # 5210
                    self.event("absorbed", row=x3, col=y3)
                    self.out(f"STAR AT{bn(x3)},{bn(y3)}ABSORBED TORPEDO ENERGY.")
                    self.klingons_fire()                             # 5260
                    return
                if what == STARBASE:                                 # 5280
                    self.event("explode", row=x3, col=y3, what=STARBASE)
                    self.out("*** STARBASE DESTROYED ***")           # 5330
                    self.bases_here -= 1
                    self.bases_total -= 1
                    if self.bases_total <= 0 and \
                            self.klingons_left <= (self.stardate - self.stardate0
                                                   - self.mission_days):   # 5360
                        self.out("THAT DOES IT, CAPTAIN!!  YOU ARE HEREBY RELIEVED OF COMMAND")
                        self.out("AND SENTENCED TO 99 STARDATES AT HARD LABOR ON CYGNUS 12!!")
                        raise MissionEnd("relieved")                 # 5390 -> 6270
                    self.out("STARFLEET COMMAND REVIEWING YOUR RECORD TO CONSIDER")
                    self.out("COURT MARTIAL!")                       # 5400
                    self.docked = 0
                    break                                            # -> 5430
                # 5280 fall-through: not empty, klingon, star or base.
                # Unreachable in canon; the original looped back to 4760.
                retry_course = True
                break

            if retry_course:
                continue

            self.put(x, y, EMPTY)                                    # 5430
            self.galaxy[self.qrow][self.qcol] = (self.k_here * 100      # 5470
                                                 + self.bases_here * 10
                                                 + self.stars_here)
            self.chart[self.qrow][self.qcol] = self.galaxy[self.qrow][self.qcol]
            self.klingons_fire()
            return

    # =================================================================
    # SHE  (5520-5660)
    # =================================================================
    def shield_control(self):
        if self.damage[7] < 0:                                       # 5530
            self.out("SHIELD CONTROL INOPERABLE")
            return
        self.out(f"ENERGY AVAILABLE ={bn(self.energy + self.shields)}")   # 5560
        x = self.ask_num("NUMBER OF UNITS TO SHIELDS")
        if x < 0 or self.shields == x:                               # 5580
            self.out("<SHIELDS UNCHANGED>")
            return
        if x > self.energy + self.shields:                           # 5590
            self.out("SHIELD CONTROL REPORTS  'THIS IS NOT THE FEDERATION TREASURY.'")
            self.out("<SHIELDS UNCHANGED>")
            return
        self.energy = self.energy + self.shields - x                 # 5630
        self.shields = x
        self.out("DEFLECTOR CONTROL ROOM REPORT:")
        self.out(f"  'SHIELDS NOW AT{bn(int(self.shields))}UNITS PER YOUR COMMAND.'")

    # =================================================================
    # DAM  (5680-5980)
    # =================================================================
    def damage_control(self):
        if self.damage[6] < 0:                                       # 5690
            self.out("DAMAGE CONTROL REPORT NOT AVAILABLE")          # 5700
            if self.docked == 0:
                return
        else:
            self._print_damage_table()                               # 5910
            if self.docked == 0:
                return

        while True:                                                  # 5720
            d3 = 0.0
            for i in range(1, self.cfg.device_count + 1):
                if self.damage[i] < 0:
                    d3 += 0.1
            if d3 == 0:                                              # 5760
                return
            self.out("")
            d3 += self.repair_fudge                                  # 5780
            if d3 >= 1:
                d3 = 0.9
            self.out("TECHNICIANS STANDING BY TO EFFECT REPAIRS TO YOUR SHIP;")
            self.out(f"ESTIMATED TIME TO REPAIR:{bn(0.01 * int(100 * d3))}STARDATES")
            if self.ask_str("WILL YOU AUTHORIZE THE REPAIR ORDER (Y/N)") != "Y":   # 5840
                return
            for i in range(1, self.cfg.device_count + 1):            # 5870
                if self.damage[i] < 0:
                    self.damage[i] = 0
            self.stardate += d3 + 0.1                                # 5890
            self._print_damage_table()                               # 5910

    def _print_damage_table(self):
        """5910-5950  device name padded to 25 columns, then its state."""
        self.event("begin", kind="damage")
        self.out("")
        self.out("DEVICE             STATE OF REPAIR")
        for r1 in range(1, self.cfg.device_count + 1):
            name = self.device_name(r1)
            self.out(f"{name}{' ' * (25 - len(name))}{bn(int(self.damage[r1] * 100) * 0.01)}")
        self.out("")
        self.event("end", kind="damage")

    # =================================================================
    # Klingons shooting  (5990-6200)
    # =================================================================
    def klingons_fire(self):
        if self.k_here <= 0:                                         # 6000
            return
        if self.docked != 0:                                         # 6010
            self.out("STARBASE SHIELDS PROTECT THE ENTERPRISE")
            return
        for i in range(1, self.cfg.max_klingons_per_quadrant + 1):   # 6040
            if self.k[i][3] <= 0:
                continue
            # 6060  damage falls off with distance, times a random 2..3
            h = int((self.k[i][3] / self.distance_to(i)) * (2 + self.rng.random()))
            self.event("enterprise_hit", row=self.k[i][1], col=self.k[i][2], hit=h)
            self.shields -= h
            # firing costs the klingon strength too -- they wear themselves down
            self.k[i][3] = self.k[i][3] / (3 + self.rng.random())
            self.out(f"{bn(h)}UNIT HIT ON ENTERPRISE FROM SECTOR{bn(self.k[i][1])},"
                     f"{bn(self.k[i][2])}")
            if self.shields <= 0:                                    # 6090
                raise MissionEnd("destroyed")                        # 6240
            self.out(f"      <SHIELDS DOWN TO{bn(self.shields)}UNITS>")
            if h < 20:                                               # 6100
                continue
            if self.rng.random() > 0.6 or h / self.shields <= 0.02:  # 6120
                continue
            r1 = self.fnr()                                          # 6140
            self.damage[r1] -= h / self.shields + 0.5 * self.rng.random()
            self.out(f"DAMAGE CONTROL REPORTS {self.device_name(r1)} DAMAGED BY THE HIT'")

    # =================================================================
    # SRS  (6420-7260)
    # =================================================================
    def short_range_scan(self):
        size = self.cfg.sector_size

        # 6430-6620  docked if any adjacent sector holds a starbase
        docked_now = False
        for i in range(int(self.srow) - 1, int(self.srow) + 2):
            for j in range(int(self.scol) - 1, int(self.scol) + 2):
                if not (1 <= math.floor(i + 0.5) <= size
                        and 1 <= math.floor(j + 0.5) <= size):       # 6450
                    continue
                if self.cell(i, j) == STARBASE:                      # 6490
                    docked_now = True

        if docked_now:                                               # 6580
            self.docked = 1
            self.condition = "DOCKED"
            self.energy = self.energy0       # resupply -- but NOT repairs
            self.torpedoes = self.torpedoes0
            self.out("SHIELDS DROPPED FOR DOCKING PURPOSES")         # 6620
            self.shields = 0
        else:
            self.docked = 0
            if self.k_here > 0:                                      # 6650
                self.condition = "*RED*"
            else:                                                    # 6660
                self.condition = "YELLOW" if self.energy < self.energy0 * 0.1 else "GREEN"

        if self.damage[2] < 0:                                       # 6720
            self.out("")
            self.out("*** SHORT RANGE SENSORS ARE OUT ***")
            self.out("")
            return

        rule = "-" * 33                                              # 6770
        self.event("begin", kind="srs")
        self.out(rule)
        stride = self.cfg.row_stride
        for i in range(1, size + 1):
            row = ""
            for j in range((i - 1) * stride + 1,
                           (i - 1) * stride + stride - 1, self.cfg.cell_width):
                row += " " + self.q[j - 1:j - 1 + self.cfg.cell_width]   # 6820
            self.out(row + self._status_line(i))                     # 6830
        self.out(rule)                                               # 7260
        self.event("end", kind="srs")

    def _status_line(self, i):
        """6850-7240  the panel down the right-hand side, one row at a time."""
        pad = " " * 8
        if i == 1:
            return f"{pad}STARDATE          {bn(int(self.stardate * 10) * 0.1)}"
        if i == 2:
            return f"{pad}CONDITION          {self.condition}"
        if i == 3:
            return f"{pad}QUADRANT          {bn(self.qrow)},{bn(self.qcol)}"
        if i == 4:
            return f"{pad}SECTOR            {bn(self.srow)},{bn(self.scol)}"
        if i == 5:
            return f"{pad}PHOTON TORPEDOES  {bn(int(self.torpedoes))}"
        if i == 6:
            return f"{pad}TOTAL ENERGY      {bn(int(self.energy + self.shields))}"
        if i == 7:
            return f"{pad}SHIELDS           {bn(int(self.shields))}"
        return f"{pad}KLINGONS REMAINING{bn(int(self.klingons_left))}"

    # =================================================================
    # COM  (7280-8520)
    # =================================================================
    def library_computer(self):
        if self.damage[8] < 0:                                       # 7290
            self.out("COMPUTER DISABLED")
            return
        while True:
            a = self.ask_num("COMPUTER ACTIVE AND AWAITING COMMAND")    # 7320
            if a < 0:
                return
            self.out("")
            a = int(a)
            if a == 0:
                self._galactic_record()                              # 7540
                return
            if a == 1:
                self._status_report()                                # 7900
                return
            if a == 2:
                self._torpedo_data()                                 # 8070
                return
            if a == 3:
                self._starbase_data()                                # 8500
                return
            if a == 4:
                self._direction_calculator()                         # 8150
                return
            if a == 5:
                self._region_map()                                   # 7400
                return
            self.out("FUNCTIONS AVAILABLE FROM LIBRARY-COMPUTER:")   # 7360
            self.out("   0 = CUMULATIVE GALACTIC RECORD")
            self.out("   1 = STATUS REPORT")
            self.out("   2 = PHOTON TORPEDO DATA")
            self.out("   3 = STARBASE NAV DATA")
            self.out("   4 = DIRECTION/DISTANCE CALCULATOR")
            self.out("   5 = GALAXY 'REGION NAME' MAP")
            self.out("")

    def _grid_header(self):
        """7550-7560

        Original, character for character:
          7550 PRINT "       1     2     3     4     5     6     7     8"
          7560 O1$="     ----- ----- ----- ----- ----- ----- ----- -----"
        """
        n = self.cfg.galaxy_size
        self.out("  " + "".join(f"{i:>6}" for i in range(1, n + 1)))
        return "     " + "-----" + " -----" * (n - 1)

    def _galactic_record(self):
        """7543-7850 with H8=1 -- what you have actually scanned."""
        self.event("begin", kind="record")
        self.out("")
        self.out(f"        COMPUTER RECORD OF GALAXY FOR QUADRANT"
                 f"{bn(self.qrow)},{bn(self.qcol)}")
        self.out("")
        rule = self._grid_header()
        self.out(rule)
        for i in range(1, self.cfg.galaxy_size + 1):
            row = bn(i)
            for j in range(1, self.cfg.galaxy_size + 1):             # 7630
                row += "   " + ("***" if self.chart[i][j] == 0
                                else rjust3(self.chart[i][j]))       # 7700
            self.out(row)
            self.out(rule)                                           # 7850
        self.out("")
        self.event("end", kind="record")

    def _region_map(self):
        """7400 + 7740-7800 with H8=0 -- the same grid, but named."""
        self.event("begin", kind="regionmap")
        self.out("                        THE GALAXY")
        rule = self._grid_header()
        self.out(rule)
        for i in range(1, self.cfg.galaxy_size + 1):
            west = quadrant_name(i, 1, region_only=True)             # 7740
            east = quadrant_name(i, 5, region_only=True)             # 7800
            line = bn(i)
            # TAB(n) moves to column n, i.e. pads to n-1 characters
            line += " " * max(0, int(15 - 0.5 * len(west)) - 1 - len(line)) + west
            line += " " * max(0, int(39 - 0.5 * len(east)) - 1 - len(line)) + east
            self.out(line)
            self.out(rule)
        self.out("")
        self.event("end", kind="regionmap")

    def _status_report(self):
        """7900-8020"""
        self.out("   STATUS REPORT:")
        plural = "S" if self.klingons_left > 1 else ""
        self.out(f"KLINGON{plural} LEFT: {bn(self.klingons_left)}")
        remaining = 0.1 * int((self.stardate0 + self.mission_days - self.stardate) * 10)
        self.out(f"MISSION MUST BE COMPLETED IN{bn(remaining)}STARDATES")
        if self.bases_total < 1:                                     # 7970
            self.out("YOUR STUPIDITY HAS LEFT YOU ON YOUR ON IN")     # 8010
            self.out("  THE GALAXY -- YOU HAVE NO STARBASES LEFT!")
        else:
            plural = "S" if self.bases_total >= 2 else ""
            self.out(f"THE FEDERATION IS MAINTAINING{bn(self.bases_total)}"
                     f"STARBASE{plural} IN THE GALAXY")
        self.damage_control()                                        # 7990 -> 5690

    def _torpedo_data(self):
        """8070-8120  bearing and range to every klingon in the quadrant."""
        if self.k_here <= 0:                                         # 8070
            self.out("SCIENCE OFFICER SPOCK REPORTS  'SENSORS SHOW NO ENEMY SHIPS")
            self.out("                                IN THIS QUADRANT'")
            return
        plural = "S" if self.k_here > 1 else ""                      # 8080
        self.out(f"FROM ENTERPRISE TO KLINGON BATTLE CRUSER{plural}")
        for i in range(1, self.cfg.max_klingons_per_quadrant + 1):   # 8100
            if self.k[i][3] <= 0:
                continue
            self._direction_distance(self.srow, self.scol,           # 8110-8120
                                     self.k[i][1], self.k[i][2])

    def _starbase_data(self):
        """8500-8520"""
        if self.bases_here != 0:
            self.out("FROM ENTERPRISE TO STARBASE:")
            self._direction_distance(self.srow, self.scol,
                                     self.base_row, self.base_col)
            return
        self.out("MR. SPOCK REPORTS,  'SENSORS SHOW NO STARBASES IN THIS QUADRANT.'")

    def _direction_calculator(self):
        """8150-8200"""
        self.out("DIRECTION/DISTANCE CALCULATOR:")
        self.out(f"YOU ARE AT QUADRANT {bn(self.qrow)},{bn(self.qcol)} SECTOR "
                 f"{bn(self.srow)},{bn(self.scol)}")
        self.out("PLEASE ENTER")
        c1, a = self.ask_two("  INITIAL COORDINATES (X,Y)")         # 8170
        w1, x = self.ask_two("  FINAL COORDINATES (X,Y)")           # 8200
        self._direction_distance(c1, a, w1, x)

    def bearing(self, from_row, from_col, to_row, to_col):
        """8220-8450  course on the 1-9 compass, and range, between sectors.

        Pure: no output, no state.  Shared by COM 2/3/4 and the Phase 2
        cadet overlay, so the computer and the cadet display cannot disagree.

        This is the exact inverse of the torpedo's course interpolation at
        3110/4850.  The listing's direction formula is linear in the RATIO of
        the deltas, not in the angle -- and so is the interpolation it has to
        undo.  An atan2 bearing is close, but it is not the same, and it
        misses.

        If both deltas are zero the original divided by zero at 8330 and
        halted.  We return course 5 instead.  See BUGS.md #3.
        """
        c1, a, w1, x = from_row, from_col, to_row, to_col
        x = x - a                                                    # 8220
        a = c1 - w1
        if x < 0:
            if a > 0:                                                # 8350
                return self._bearing_b(3, a, x)
            return self._bearing_a(5, a, x)                          # 8360
        if a < 0:                                                    # 8250
            return self._bearing_b(7, a, x)                          # 8410
        if x > 0:                                                    # 8260
            return self._bearing_a(1, a, x)                          # 8280
        if a == 0:                                                   # 8270
            return self._bearing_a(5, a, x)
        return self._bearing_a(1, a, x)                              # 8280

    @staticmethod
    def _bearing_a(c1, a, x):
        """8290-8330"""
        distance = math.sqrt(x ** 2 + a ** 2)                        # 8460
        if abs(a) > abs(x):
            return c1 + ((abs(a) - abs(x)) + abs(a)) / abs(a), distance   # 8310
        if abs(x) == 0:
            return c1, distance                   # guarded: 8330 would be 0/0
        return c1 + abs(a) / abs(x), distance                        # 8330

    @staticmethod
    def _bearing_b(c1, a, x):
        """8420-8450.  Always entered with a != 0, so 8450 is safe."""
        distance = math.sqrt(x ** 2 + a ** 2)
        if abs(a) < abs(x):
            return c1 + ((abs(x) - abs(a)) + abs(x)) / abs(x), distance   # 8430
        return c1 + abs(x) / abs(a), distance                        # 8450

    def _direction_distance(self, c1, a, w1, x):
        """8220-8460  print the bearing and range."""
        direction, distance = self.bearing(c1, a, w1, x)
        self.out(f"DIRECTION ={bn(direction)}")
        self.out(f"DISTANCE ={bn(distance)}")                        # 8460

    # =================================================================
    # End of game  (6210-6400)
    # =================================================================
    def end_of_game(self, kind):
        """Returns True if the player volunteers for another mission."""
        if kind == "destroyed":                                      # 6240
            self.out("")
            self.out("THE ENTERPRISE HAS BEEN DESTROYED.  THEN FEDERATION ")
            self.out("WILL BE CONQUERED")
            kind = "stardate"
        if kind == "stardate":                                       # 6220
            self.out(f"IT IS STARDATE{bn(int(self.stardate * 10) * 0.1)}")
            kind = "resign"

        if kind == "won":                                            # 6370
            self.out("CONGRULATION, CAPTAIN!  THEN LAST KLINGON BATTLE CRUISER")
            self.out("MENACING THE FDERATION HAS BEEN DESTROYED.")
            self.out("")
            elapsed = self.stardate - self.stardate0
            rating = 1000 * (self.klingons_start / elapsed) ** 2 if elapsed else 0
            self.out(f"YOUR EFFICIENCY RATING IS{bn(rating)}")       # 6400
        else:                                                        # 6270
            self.out(f"THERE WERE{bn(self.klingons_left)}KLINGON BATTLE CRUISERS LEFT AT")
            self.out("THE END OF YOUR MISSION.")

        self.out("")                                                 # 6290
        self.out("")
        if self.bases_total == 0:
            return False                                             # 6360 END
        self.out("THE FEDERATION IS IN NEED OF A NEW STARSHIP COMMANDER")
        self.out("FOR A SIMILAR MISSION -- IF THERE IS A VOLUNTEER,")
        return self.ask_str("LET HIM STEP FORWARD AND ENTER 'AYE'") == "AYE"   # 6330
