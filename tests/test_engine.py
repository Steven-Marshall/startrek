"""Engine tests.

These check structure and rules, not exact numbers.  Per the project's "rough
dynamics" rule we do not try to reproduce Microsoft BASIC's RND, so golden
transcripts are impossible -- a TRS-80 and an Apple II running the same 1978
listing did not agree either.  What we can test is that the formulas are the
listing's formulas and that every ending is reachable.

    pytest -q          (or just: python tests/test_engine.py)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trek.basic import bn, rjust3                                    # noqa: E402
from trek.config import CANON                                        # noqa: E402
from trek.game import (Game, MissionEnd, EMPTY, SHIP, KLINGON,       # noqa: E402
                       STARBASE, STAR)
from trek.names import quadrant_name                                 # noqa: E402


class Cap:
    """Collects engine output so tests can assert on it."""

    def __init__(self):
        self.lines = []

    def __call__(self, s=""):
        self.lines.append(str(s))

    def has(self, text):
        return any(text in line for line in self.lines)


def mk(seed, **io_):
    cap = Cap()
    return Game(seed=seed, out=cap, **io_), cap


def run(fn):
    """Call fn, returning the MissionEnd kind if one was raised."""
    try:
        fn()
        return None
    except MissionEnd as end:
        return end.kind


# ---------------------------------------------------------------- formatting

def test_basic_number_formatting():
    # MS BASIC: sign slot, trailing space, no decimal point on integers
    assert bn(3) == " 3 "
    assert bn(-3) == "-3 "
    assert bn(3.0) == " 3 "
    assert bn(0.5) == " .5 "          # leading zero dropped
    assert f"SECTOR{bn(3)},{bn(2)}" == "SECTOR 3 , 2 "


def test_zero_padding_hack():
    # 4210  RIGHT$(STR$(n+1000),3)
    assert rjust3(7) == "007"
    assert rjust3(107) == "107"
    assert rjust3(0) == "000"


def test_region_names():
    # 9030-9260: columns 1-4 from one star list, 5-8 from the other
    assert quadrant_name(1, 1) == "ANTARES I"
    assert quadrant_name(1, 5) == "SIRIUS I"
    assert quadrant_name(8, 8) == "SPICA IV"
    assert quadrant_name(3, 5, region_only=True) == "CAPELLA"


# ------------------------------------------------------------------ geometry

def test_quadrant_string_is_192_chars():
    # 1600  Q$ = 8 rows x 8 cells x 3 chars
    g, _ = mk(1)
    assert len(g.q) == 192
    assert CANON.row_stride == 24
    assert CANON.quadrant_chars == 192


def test_base10_encoding_round_trips():
    """1040/1500  G(I,J)=K3*100+B3*10+S3, decoded with INT(G*.01).

    The decode uses a float multiply rather than integer division, so verify
    it is exact across the whole range the encoding can produce.
    """
    for g in range(1000):
        k = int(g * 0.01)
        b = int(g * 0.1) - 10 * k
        s = g - 100 * k - 10 * b
        assert (k, b, s) == (g // 100, (g // 10) % 10, g % 10), g


def test_quadrant_contents_match_encoding():
    g, _ = mk(1)
    g.enter_quadrant()
    encoded = g.galaxy[g.qrow][g.qcol]
    assert g.k_here == encoded // 100
    assert g.bases_here == (encoded // 10) % 10
    assert g.stars_here == encoded % 10
    assert g.q.count(KLINGON) == g.k_here
    assert g.q.count(STARBASE) == g.bases_here
    assert g.q.count(STAR) == g.stars_here
    assert g.q.count(SHIP) == 1


def test_compass_table():
    """530-600  direction 1 is east, counterclockwise, 9 wraps to 1."""
    g, _ = mk(1)
    assert tuple(g.course[1][1:]) == (0, 1)      # east
    assert tuple(g.course[3][1:]) == (-1, 0)     # north
    assert tuple(g.course[5][1:]) == (0, -1)     # west
    assert tuple(g.course[7][1:]) == (1, 0)      # south
    assert g.course[9][1:] == g.course[1][1:]    # wraps, so 8->9 interpolates


def test_put_and_cell_round_trip():
    g, _ = mk(1)
    g.q = EMPTY * 64
    for row in range(1, 9):
        for col in range(1, 9):
            g.put(row, col, KLINGON)
            assert g.cell(row, col) == KLINGON, (row, col)
            g.put(row, col, EMPTY)
    assert g.q == EMPTY * 64


# ------------------------------------------------------------------- endings

def test_win_by_phasers():
    g, cap = mk(3, ask_num=lambda p: 1000)
    run(g.enter_quadrant)
    g.klingons_left, g.k_here = 1, 1
    g.k[1][1], g.k[1][2], g.k[1][3] = 1, 5, 50
    g.put(1, 5, KLINGON)
    g.energy = 3000
    assert run(g.phasers) == "won"


def test_win_by_torpedo():
    g, cap = mk(3, ask_num=lambda p: 1)
    run(g.enter_quadrant)
    g.klingons_left, g.k_here = 1, 1
    g.q = EMPTY * 64
    g.srow, g.scol = 4, 4
    g.put(4, 4, SHIP)
    g.put(4, 5, KLINGON)
    g.k[1][1], g.k[1][2], g.k[1][3] = 4, 5, 100
    assert run(g.torpedo) == "won"


def test_stranded_in_space():
    # 1990  no energy, no shields, and shield control cannot cross-circuit
    g, cap = mk(5)
    g.energy, g.shields, g.damage[7] = 5, 0, -1
    assert run(g.check_stranded) == "stardate"
    assert cap.has("FATAL ERROR")


def test_destroying_last_starbase_ends_the_mission():
    # 5360-5390
    g, cap = mk(7, ask_num=lambda p: 1)
    run(g.enter_quadrant)
    g.bases_total, g.bases_here, g.klingons_left = 1, 1, 0
    g.stardate = g.stardate0 + g.mission_days + 10
    g.torpedoes, g.srow, g.scol = 5, 4, 4
    g.q = EMPTY * 64
    g.put(4, 4, SHIP)
    g.put(4, 5, STARBASE)
    assert run(g.torpedo) == "relieved"
    assert cap.has("CYGNUS 12")


def test_destroying_a_starbase_with_others_left_is_survivable():
    # 5400  a court-martial warning, but the mission continues
    g, cap = mk(7, ask_num=lambda p: 1)
    run(g.enter_quadrant)
    g.bases_total, g.bases_here = 3, 1
    g.torpedoes, g.srow, g.scol = 5, 4, 4
    g.q = EMPTY * 64
    g.put(4, 4, SHIP)
    g.put(4, 5, STARBASE)
    assert run(g.torpedo) is None
    assert cap.has("COURT MARTIAL")
    assert g.bases_total == 2


def test_efficiency_rating():
    # 6400  1000*(K7/(T-T0))^2
    g, cap = mk(3, ask_str=lambda p: "NO")
    g.klingons_start = 17
    g.stardate = g.stardate0 + 20
    g.end_of_game("won")
    assert cap.has("EFFICIENCY RATING")
    assert any("722.5" in line for line in cap.lines)


# ------------------------------------------------------------------ mechanics

def test_docking_resupplies_but_does_not_repair():
    """6580  docking restores energy and torpedoes and drops shields.

    It does NOT repair damage -- that costs stardates via DAM.  Players
    misremember this one constantly.
    """
    g, cap = mk(3)
    run(g.enter_quadrant)
    assert g.docked == 1, "seed 3 is expected to start adjacent to a starbase"
    g.energy, g.torpedoes, g.shields = 100, 2, 500
    g.damage[1] = -2.0
    run(g.short_range_scan)
    assert g.energy == g.energy0
    assert g.torpedoes == g.torpedoes0
    assert g.shields == 0
    assert g.damage[1] == -2.0          # still broken


def test_docked_repair_costs_stardates():
    g, cap = mk(11, ask_str=lambda p: "Y")
    run(g.enter_quadrant)
    g.docked = 1
    g.damage[1], g.damage[4] = -3.0, -1.5
    before = g.stardate
    run(g.damage_control)
    assert g.damage[1] == 0 and g.damage[4] == 0
    assert g.stardate > before
    assert cap.has("TECHNICIANS STANDING BY")


def test_declining_repair_changes_nothing():
    g, cap = mk(11, ask_str=lambda p: "N")
    run(g.enter_quadrant)
    g.docked = 1
    g.damage[1] = -3.0
    before = g.stardate
    run(g.damage_control)
    assert g.damage[1] == -3.0
    assert g.stardate == before


def test_navigation_is_blocked_by_objects():
    # 3240/3320  you stop one sector short of whatever you ran into
    g, cap = mk(3, ask_num=lambda p: 1)
    run(g.enter_quadrant)
    cap.lines.clear()
    g.q = EMPTY * 64
    g.srow, g.scol, g.k_here = 4, 1, 0
    g.put(4, 1, SHIP)
    g.put(4, 4, STAR)
    run(g.navigate)
    assert (g.srow, g.scol) == (4, 3)
    assert cap.has("BAD NAVAGATION")


def test_torpedo_is_absorbed_by_a_star():
    # 5260
    g, cap = mk(3, ask_num=lambda p: 1)
    run(g.enter_quadrant)
    cap.lines.clear()
    g.q = EMPTY * 64
    g.srow, g.scol, g.k_here = 4, 1, 0
    g.torpedoes = 5
    g.put(4, 1, SHIP)
    g.put(4, 3, STAR)
    run(g.torpedo)
    assert cap.has("ABSORBED TORPEDO ENERGY")
    assert g.torpedoes == 4


def test_phasers_refuse_when_no_enemy_present():
    g, cap = mk(1)
    run(g.enter_quadrant)
    g.k_here = 0
    cap.lines.clear()
    run(g.phasers)
    assert cap.has("NO ENEMY SHIPS")


def test_maneuver_energy_falls_back_to_shields():
    # 3910-3940
    g, cap = mk(1)
    g.energy, g.shields = 5, 500
    g.maneuver_energy(8)
    assert g.energy == 0
    assert g.shields == 500 - 13        # 8 + 10 overhead, minus the 5 we had
    assert cap.has("SHIELD CONTROL SUPPLIES ENERGY")


def test_quadrant_crossing_always_costs_one_stardate():
    """3870, versus 3430/3450.

    Moving WITHIN a quadrant costs 1 stardate at warp >= 1, or 0.1*int(10*w)
    below it.  Crossing INTO a new quadrant costs a flat 1 stardate however
    fast you went -- a warp 8 hop across the galaxy costs exactly the same day
    as a warp 1 hop next door.  Only the energy differs: 74 units against 18.

    Probably the most important strategic fact in the game, and it appears
    nowhere in the instructions.
    """
    for warp in (1, 2, 4, 8):
        g, _ = mk(3, ask_num=lambda p, w=warp: 1 if "COURSE" in p else w)
        run(g.enter_quadrant)
        g.q = EMPTY * 64                      # clear the path of obstacles
        g.srow, g.scol, g.k_here = 4, 4, 0
        g.put(4, 4, SHIP)
        before_q = (g.qrow, g.qcol)
        before_t = g.stardate
        run(g.navigate)
        assert (g.qrow, g.qcol) != before_q, f"warp {warp} should leave the quadrant"
        assert abs((g.stardate - before_t) - 1) < 1e-9, \
            f"warp {warp} cost {g.stardate - before_t} stardates, expected 1"


def test_bouncing_off_the_rim_still_costs_time():
    """3860 -> 3370 -> 3450.

    Hitting the galactic rim and being clamped back into the quadrant you
    started in is treated as an in-quadrant move and charged accordingly.
    An earlier version of this port inlined 3370 and forgot 3430-3450,
    which made rim bounces free.
    """
    g, _ = mk(3, ask_num=lambda p: 3 if "COURSE" in p else 1)   # north, warp 1
    run(g.enter_quadrant)
    g.qrow = 1                                  # top edge of the galaxy
    g.q = EMPTY * 64
    g.srow, g.scol, g.k_here = 4, 4, 0
    g.put(4, 4, SHIP)
    before_q, before_t = (g.qrow, g.qcol), g.stardate
    run(g.navigate)
    assert (g.qrow, g.qcol) == before_q          # bounced back
    assert g.stardate - before_t == 1


def test_preserved_overtime_loophole():
    """BUGS.md #8 -- 3870 advances the clock without checking the deadline.

    Crossing into a new quadrant can take you past the deadline without
    ending the game, and since phasers and torpedoes never check the clock
    either, you can still win in overtime.
    """
    g, _ = mk(3, ask_num=lambda p: 1)           # course 1 (east), warp 1
    run(g.enter_quadrant)
    g.stardate = g.stardate0 + g.mission_days - 0.5
    g.q = EMPTY * 64
    g.srow, g.scol, g.k_here = 4, 4, 0
    g.put(4, 4, SHIP)
    g.galaxy[g.qrow][g.qcol + 1] = 101          # one klingon next door
    g.klingons_left = 1
    assert run(g.navigate) is None               # no MissionEnd: still playing
    assert g.stardate > g.stardate0 + g.mission_days
    g.shields, g.energy = 5000, 3000
    g.ask_num = lambda p: 3000
    assert run(g.phasers) == "won"               # ...and you can win overtime


def test_preserved_phaser_penalty_on_wrong_device():
    """BUGS.md #8 -- 4330 warns on D(8), but 4410 penalises on D(7).

    Forcing every random roll to zero makes the penalty visible: if it
    applies, the volley is multiplied by RND = 0 and nothing lands.
    """
    def fight(broken):
        g, cap = mk(3, ask_num=lambda p: 1000)
        run(g.enter_quadrant)
        g.q = EMPTY * 64
        g.srow, g.scol = 4, 1
        g.put(4, 1, SHIP)
        g.put(4, 3, KLINGON)
        g.k_here, g.klingons_left = 1, 5
        g.k[1][1], g.k[1][2], g.k[1][3] = 4, 3, 100
        g.energy, g.shields = 3000, 5000
        g.damage[broken] = -1
        g.rng.random = lambda: 0.0
        cap.lines.clear()
        run(g.phasers)
        return cap

    computer = fight(8)                         # D(8) LIBRARY-COMPUTER
    assert computer.has("COMPUTER FAILURE HAMPERS ACCURACY")
    assert computer.has("KLINGON DESTROYED")    # warned, but no penalty

    shields = fight(7)                          # D(7) SHIELD CONTROL
    assert not shields.has("HAMPERS ACCURACY")  # no warning...
    assert shields.has("NO DAMAGE")             # ...but the volley fizzles


def test_a_torpedo_hit_always_destroys():
    """5060-5110  there is no strength check on a torpedo hit.

    One torpedo, one dead klingon, whatever its strength or range.  Phaser
    damage meanwhile is (x/k3/distance)*(rand+2), so a distant klingon at full
    strength can cost more energy than the ship even carries.  Torpedoes are
    the primary weapon -- which is not at all how it feels while playing.
    """
    g, cap = mk(3, ask_num=lambda p: 1)
    run(g.enter_quadrant)
    g.q = EMPTY * 64
    g.srow, g.scol = 4, 1
    g.put(4, 1, SHIP)
    g.put(4, 6, KLINGON)                      # far away...
    g.k_here, g.klingons_left = 1, 5
    g.k[1][1], g.k[1][2], g.k[1][3] = 4, 6, 300    # ...and at maximum strength
    g.torpedoes, g.shields = 10, 5000
    cap.lines.clear()
    run(g.torpedo)
    assert cap.has("KLINGON DESTROYED")
    assert g.klingons_left == 4


def test_preserved_starbase_count_bug():
    """BUGS.md #1 -- B9 starts at 2, so the briefing overstates by exactly 2."""
    g, _ = mk(4)
    actual = sum(1 for i in range(1, 9) for j in range(1, 9)
                 if (g.galaxy[i][j] // 10) % 10 == 1)
    assert g.bases_total == actual + 2


def test_starbase_count_bug_can_be_fixed():
    from dataclasses import replace
    cfg = replace(CANON, starbase_count_start=0)
    g = Game(cfg=cfg, seed=4, out=lambda *a: None)
    actual = sum(1 for i in range(1, 9) for j in range(1, 9)
                 if (g.galaxy[i][j] // 10) % 10 == 1)
    assert g.bases_total == actual


def test_direction_calculator_does_not_crash_on_zero_distance():
    """BUGS.md #3 -- the original halted with ?DIVISION BY ZERO here."""
    g, cap = mk(1)
    g._direction_distance(4, 4, 4, 4)
    assert cap.has("DIRECTION")
    assert cap.has("DISTANCE")


def test_bearing_points_the_right_way():
    """8220-8450 for all eight compass points.

    Regression: an earlier version of this port skipped line 8360, so every
    target to the west or south-west was reported on course 9 or 7-ish --
    due west came out as 9, i.e. EAST.
    """
    g, _ = mk(1)
    expected = {
        (4, 7): 1,   # east
        (1, 7): 2,   # north-east
        (1, 4): 3,   # north
        (1, 1): 4,   # north-west
        (4, 1): 5,   # west       <- was 9
        (7, 1): 6,   # south-west <- was wrong too
        (7, 4): 7,   # south
        (7, 7): 8,   # south-east
    }
    for (row, col), course in expected.items():
        direction, _ = g.bearing(4, 4, row, col)
        assert direction == course, f"target {row},{col}: got {direction}, want {course}"


def test_com_bearing_is_the_exact_inverse_of_the_torpedo():
    """The listing's direction calculator is linear in the RATIO of the
    deltas, exactly undoing the torpedo's course interpolation at 4850.

    So on an empty field, a torpedo fired along the computer's own bearing
    hits every target from every square: 4,032 shots, no misses.  (An atan2
    bearing, which is linear in the angle, misses about 4% of them.)
    """
    g, _ = mk(1)
    misses = []
    for sr in range(1, 9):
        for sc in range(1, 9):
            for kr in range(1, 9):
                for kc in range(1, 9):
                    if (sr, sc) == (kr, kc):
                        continue
                    course, _ = g.bearing(sr, sc, kr, kc)
                    path = list(g_path(g, sr, sc, kr, kc, course))
                    if path[-1] != (kr, kc):
                        misses.append(((sr, sc), (kr, kc), course))
    assert not misses, f"{len(misses)} misses, e.g. {misses[:3]}"


def g_path(g, sr, sc, kr, kc, course):
    """Walk the torpedo track on an empty field with a single target."""
    g.q = EMPTY * 64
    g.srow, g.scol = sr, sc
    g.put(sr, sc, SHIP)
    g.put(kr, kc, KLINGON)
    for _, _, x3, y3, what in g.torpedo_track(course):
        if what is None:
            return
        yield (x3, y3)


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok    {name}")
            except AssertionError as exc:
                failures += 1
                print(f"  FAIL  {name}: {exc}")
    print(f"\n{'FAILED' if failures else 'all passed'} ({failures} failures)")
    sys.exit(1 if failures else 0)
