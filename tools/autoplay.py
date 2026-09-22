"""Autoplay bot -- plays Super Star Trek properly to test balance.

Not a unit test.  This drives the real engine through its input seams and
plays a competent (not optimal) game, to answer questions the unit tests
cannot: is it winnable?  how often?  what actually kills you?  does the
stardate budget work out?

Strategy, roughly how a human plays:
  * long range scan on arrival, to fill the chart
  * shields up before engaging, topped back up between fights
  * phasers as the main weapon, torpedoes when energy is short
  * run for a starbase when energy or shields get low, repair while docked
  * otherwise head for the nearest charted quadrant containing klingons
"""

import math
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from trek.game import Game, MissionEnd, KLINGON, STARBASE          # noqa: E402


def course_to(drow, dcol):
    """Compass bearing for a delta. 1=east, counterclockwise, rows run down."""
    if drow == 0 and dcol == 0:
        return 1.0
    angle = math.atan2(-drow, dcol)           # -drow because north is up
    course = 1 + angle / (math.pi / 4)
    while course < 1:
        course += 8
    while course >= 9:
        course -= 8
    return course


class Bot:
    def __init__(self, seed, verbose=False):
        self.log = []
        self.verbose = verbose
        self.game = Game(seed=seed, out=self._out,
                         ask_str=self._ask_str,
                         ask_num=self._ask_num,
                         ask_two=lambda p: (1, 1))
        self.answers = []
        self.scanned = set()
        self.blocked = 0          # consecutive navigations that went nowhere
        self.last_stardate = None
        self.stall = 0            # turns since the clock last moved

    # ---- I/O seams -------------------------------------------------
    def _out(self, s=""):
        self.log.append(str(s))
        if self.verbose:
            print(s)

    def _ask_num(self, prompt):
        return self.answers.pop(0) if self.answers else 0

    def _ask_str(self, prompt):
        if "REPAIR ORDER" in prompt:
            return "Y"
        if "AYE" in prompt:
            return "NO"
        return "N"

    # ---- helpers ---------------------------------------------------
    def act(self, method, *answers):
        self.answers = list(answers)
        method()

    def known_klingon_quadrants(self):
        g = self.game
        out = []
        for i in range(1, 9):
            for j in range(1, 9):
                if g.chart[i][j] // 100 > 0:
                    out.append((i, j))
        return out

    def known_starbases(self):
        g = self.game
        return [(i, j) for i in range(1, 9) for j in range(1, 9)
                if (g.chart[i][j] // 10) % 10 == 1]

    def nearest(self, targets):
        g = self.game
        if not targets:
            return None
        return min(targets, key=lambda t: (t[0] - g.qrow) ** 2 + (t[1] - g.qcol) ** 2)

    def best_klingon_target(self):
        """Most klingons first; distance only breaks ties (it costs 1 day
        to reach any quadrant, so a full one is worth crossing the galaxy)."""
        g = self.game
        targets = self.known_klingon_quadrants()
        if not targets:
            return None
        return max(targets, key=lambda t: (g.chart[t[0]][t[1]] // 100,
                                           -((t[0]-g.qrow)**2 + (t[1]-g.qcol)**2)))

    def goto_quadrant(self, target):
        """Head for a quadrant, working around anything in the way.

        Flying into a star stops you one sector short of it, which puts you
        right back where you started -- so a naive bot loops forever burning
        18 energy and a stardate a turn.  After a navigation that goes
        nowhere, fan the course out until something gets through.
        """
        g = self.game
        drow, dcol = target[0] - g.qrow, target[1] - g.qcol
        dist = math.sqrt(drow ** 2 + dcol ** 2)
        warp = max(0.5, min(8.0, dist))
        if g.damage[1] < 0:
            warp = 0.2

        course = course_to(drow, dcol)
        if self.blocked:
            # alternate either side of the ideal heading, widening each time
            offset = ((self.blocked + 1) // 2) * 1.0
            course += offset if self.blocked % 2 else -offset
            while course < 1:
                course += 8
            while course >= 9:
                course -= 8
            if self.blocked > 4:
                warp = max(warp, 1.0)      # a longer hop clears local clutter

        before = (g.qrow, g.qcol, int(g.srow), int(g.scol))
        self.act(g.navigate, course, warp)
        after = (g.qrow, g.qcol, int(g.srow), int(g.scol))
        self.blocked = 0 if after != before else self.blocked + 1

    # A long range scan reveals the 3x3 block around you, so nine scans on a
    # lattice of every third quadrant cover all 64.  Crossing quadrants costs
    # one stardate whatever the warp factor, so the scarce resource is the
    # NUMBER of hops, not their length -- scouting on the lattice is much
    # cheaper than drifting to whatever is nearest and unscanned.
    LATTICE = [(r, c) for r in (2, 5, 8) for c in (2, 5, 8)]

    def wander(self):
        g = self.game
        todo = [q for q in self.LATTICE if q not in self.scanned]
        if todo:
            self.goto_quadrant(self.nearest(todo))
            return
        unseen = [(i, j) for i in range(1, 9) for j in range(1, 9)
                  if g.chart[i][j] == 0]
        self.goto_quadrant(self.nearest(unseen) or (4, 4))

    # ---- the turn --------------------------------------------------
    def turn(self):
        g = self.game

        # Stall guard.  Most actions cost no stardates (scans, shields,
        # phasers), so a bot that keeps picking an action the engine refuses
        # will spin forever without the clock moving.  Watch for it.
        if self.last_stardate == g.stardate:
            self.stall += 1
        else:
            self.stall, self.last_stardate = 0, g.stardate
        if self.stall > 10:
            self.blocked += 1
            self.wander()
            return

        if (g.qrow, g.qcol) not in self.scanned:
            self.scanned.add((g.qrow, g.qcol))
            if g.damage[3] >= 0:
                self.act(g.long_range_scan)
                return

        total = g.energy + g.shields
        hurt = any(g.damage[i] < 0 for i in range(1, 9))
        can_phase = g.damage[4] >= 0
        can_torp = g.damage[5] >= 0 and g.torpedoes > 0
        can_shield = g.damage[7] >= 0

        # Energy emergency: withdraw from the shields.  SHE sets shields to a
        # value and returns the difference to the reserve, so asking for less
        # is how you refuel yourself.
        if g.energy < 250 and g.shields > 300 and can_shield:
            self.act(g.shield_control, max(0, g.shields - 500))
            return

        # Docked: repair, top up, then get going
        if g.docked:
            if hurt:
                self.act(g.damage_control)
                return
            if can_shield:
                self.act(g.shield_control, min(800, total * 0.35))
                return
            target = self.best_klingon_target()
            self.goto_quadrant(target) if target else self.wander()
            return

        # Low on everything: run for a starbase
        if total < 900 or (g.shields < 150 and g.k_here > 0 and total < 1500):
            base = self.nearest(self.known_starbases())
            if base and base != (g.qrow, g.qcol):
                self.goto_quadrant(base)
                return
            if base == (g.qrow, g.qcol) and g.bases_here:
                drow, dcol = g.base_row - g.srow, g.base_col - g.scol
                if abs(drow) <= 1 and abs(dcol) <= 1:
                    self.act(g.short_range_scan)
                    return
                steps = max(abs(drow), abs(dcol)) - 1
                self.act(g.navigate, course_to(drow, dcol), max(0.1, steps / 8))
                return

        # Fight -- but only with a weapon that actually works.
        #
        # Two economics facts drive this.  Fighting costs NO stardates, only
        # travel does; and docking refills energy completely.  So energy is
        # nearly free and time is the scarce resource -- the right play is
        # enormous volleys that kill in one shot, then dock, rather than
        # conserving energy across a long exchange while they shoot back.
        if g.k_here > 0:
            live = [i for i in range(1, 4) if g.k[i][3] > 0]
            threat = sum(g.k[i][3] for i in live)

            # A torpedo hit has NO strength check (line 5060-5110): one
            # torpedo, one dead klingon, whatever its strength or range.
            # Phaser damage is (x/k3/distance)*(rand+2), so a distant,
            # healthy klingon can cost more energy than the ship carries.
            # Torpedoes are therefore the primary weapon and phasers the
            # backup -- the opposite of what it feels like while playing.
            # Incoming per exchange is sum((strength/distance)*(2..3)), and
            # raising shields costs no return fire -- so armour up BEFORE
            # firing, never after.
            incoming = sum(g.k[i][3] / max(1.0, g.distance_to(i)) * 3 for i in live)
            if can_shield and g.shields < incoming * 2.0 and g.energy > 200:
                want = min(g.energy + g.shields - 200, incoming * 2.5)
                if want > g.shields:
                    self.act(g.shield_control, want)
                    return
            if g.shields < incoming and total < 900:
                base = self.nearest(self.known_starbases())
                if base and base != (g.qrow, g.qcol):
                    self.goto_quadrant(base)
                    return

            if can_torp:
                target = max(live, key=lambda i: g.distance_to(i))
                # the game's own COM 2 bearing -- exact, unlike atan2
                course, _ = g.bearing(g.srow, g.scol,
                                      g.k[target][1], g.k[target][2])
                self.act(g.torpedo, course)
                return

            # Out of torpedoes: phasers, sized to guarantee a kill on the
            # worst-case damage roll --  x > strength * distance * k3 / 2
            kill = max((g.k[i][3] * max(1.0, g.distance_to(i)) * g.k_here / 2.0
                        for i in live), default=0) * 1.15
            if can_phase and g.energy >= kill:
                self.act(g.phasers, min(g.energy * 0.95, kill))
                return
            if can_shield and g.shields < threat * 2.0 and g.energy > threat * 1.5:
                self.act(g.shield_control, min(total * 0.45, threat * 2.5))
                return
            if g.shields < threat and total < 1400:
                base = self.nearest(self.known_starbases())
                if base and base != (g.qrow, g.qcol):
                    self.goto_quadrant(base)
                    return
            if can_phase and g.energy > 300:
                self.act(g.phasers, g.energy * 0.85)
                return
            base = self.nearest(self.known_starbases())
            self.goto_quadrant(base) if base else self.wander()
            return

        target = self.best_klingon_target()
        self.goto_quadrant(target) if target else self.wander()

    def play(self, max_turns=400):
        g = self.game
        try:
            g.enter_quadrant()
            for _ in range(max_turns):
                g.check_stranded()
                self.turn()
            return "gave up", g
        except MissionEnd as end:
            return end.kind, g
        except Exception as exc:                       # noqa: BLE001
            return f"CRASH: {type(exc).__name__}: {exc}", g


def main(n=300):
    results = Counter()
    won_times, won_ratings, klingons_at_loss = [], [], []
    crashes = []

    for seed in range(n):
        kind, g = Bot(seed).play()
        if kind.startswith("CRASH"):
            crashes.append((seed, kind))
            results["crash"] += 1
            continue
        results[kind] += 1
        if kind == "won":
            elapsed = g.stardate - g.stardate0
            won_times.append(elapsed)
            won_ratings.append(1000 * (g.klingons_start / elapsed) ** 2 if elapsed else 0)
        else:
            klingons_at_loss.append(g.klingons_left)

    print(f"=== {n} games ===\n")
    for kind, count in results.most_common():
        print(f"  {kind:12s} {count:4d}   {100*count/n:5.1f}%")

    if won_times:
        print(f"\n  wins: {len(won_times)}  "
              f"stardates used avg {sum(won_times)/len(won_times):.1f} "
              f"(min {min(won_times):.1f}, max {max(won_times):.1f})")
        print(f"  efficiency rating avg {sum(won_ratings)/len(won_ratings):.0f}")
    if klingons_at_loss:
        print(f"  klingons still alive when losing: avg "
              f"{sum(klingons_at_loss)/len(klingons_at_loss):.1f}")
    if crashes:
        print("\n  CRASHES:")
        for seed, msg in crashes[:10]:
            print(f"    seed {seed}: {msg}")
    else:
        print("\n  crashes: NONE")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
