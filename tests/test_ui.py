"""Tests for the split-screen UI.

These drive the real engine through the real Screen, with a scripted
keyboard and a fixed-size fake terminal, and check that frames render at
every size, that output lands in the right place, and that the fairness rule
holds -- panels die when their instruments do.

Animation delays are set to zero so the suite stays quick; the frames are
still drawn.

    pytest -q          (or just: python tests/test_ui.py)
"""

import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trek.game import Game, MissionEnd, EMPTY, SHIP, KLINGON, STAR    # noqa: E402
from trek.ui import app                                               # noqa: E402
from trek.ui import cadet                                             # noqa: E402
from trek.ui.app import Screen, pick_size, play                       # noqa: E402

for key in app.DELAY:
    app.DELAY[key] = 0

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def plain(text):
    return ANSI.sub("", text)


def screen(keys="", size=(130, 40), **kwargs):
    return Screen(stdin=io.StringIO(keys), stdout=io.StringIO(),
                  terminal_size=size, **kwargs)


def staged(s, seed=3):
    """A Screen with a game already in its first quadrant."""
    g = s.new_game(seed=seed)
    g.print_orders()
    g.enter_quadrant()
    return g


# ------------------------------------------------------------------ layout

def test_sprite_size_follows_the_terminal():
    assert pick_size(130, 40) == 8          # trek.cmd's window
    assert pick_size(120, 30) == 6          # Windows Terminal's default
    assert pick_size(100, 30) == 4
    assert pick_size(80, 24) is None        # too small: falls back to teletype


def test_frames_fit_exactly_at_every_size():
    for size in ((130, 40), (120, 30), (100, 30)):
        s = screen(size=size)
        staged(s)
        lines = plain(s.render()).splitlines()
        assert len(lines) == size[1] - 1, size
        assert max(len(line) for line in lines) <= size[0] - 1, size


def test_forced_sprite_size_is_honoured():
    s = screen(size=(130, 40), sprite_size=4)
    staged(s)
    first = plain(s.render()).splitlines()[0]
    # a 4x4 quadrant panel is 8*4 + 4 = 36 wide, so the SRS title starts early
    assert first.index("SHORT RANGE SCAN") < 60


# ------------------------------------------------------------- the log

def test_scan_output_goes_to_panels_not_the_log():
    s = screen()
    g = staged(s)
    s.log.clear()
    g.short_range_scan()
    g.long_range_scan()
    assert not any("-----" in line for line in s.log), "scan grids leaked into the log"
    assert any("LONG RANGE SCAN FOR QUADRANT" in line for line in s.log)


def test_computer_tables_become_an_overlay_for_one_command():
    s = screen(keys="0\nSRS\n")
    g = staged(s)
    g.library_computer()                     # COM 0 -- galactic record
    assert s.overlay and "RECORD" in s.overlay[0]
    assert "COMPUTER RECORD OF GALAXY" in plain(s.render())
    s.read("COMMAND? ")                      # the next command clears it
    assert s.overlay is None


def test_what_you_type_is_logged_with_its_prompt():
    s = screen(keys="LRS\n")
    staged(s)
    s.read("COMMAND? ")
    assert s.log[-1] == "COMMAND? LRS"


# ------------------------------------------------------- the fairness rule

def test_damaged_short_range_sensors_kill_the_pixel_view():
    s = screen()
    g = staged(s)
    g.damage[2] = -1
    frame = plain(s.render())
    assert "SHORT RANGE SENSORS DAMAGED" in frame
    assert "SHORT RANGE SENSORS ARE OUT" in frame


def test_damaged_computer_removes_decoding_and_cadet():
    s = screen(cadet=True)
    g = staged(s)
    assert "1K 1B 1" in plain(s.render())                # decoded while working
    g.damage[8] = -1
    frame = plain(s.render())
    assert "1K 1B 1" not in frame
    assert "computer damaged" in frame


def test_damaged_damage_control_hides_the_report():
    s = screen()
    g = staged(s)
    g.damage[6] = -1
    assert "REPORT" in plain(s.render()) and "NOT AVAILABLE" in plain(s.render())


def test_long_range_panel_shows_the_chart_not_the_galaxy():
    s = screen()
    g = staged(s)
    unscanned = "···"
    assert unscanned in plain(s.render())                # neighbours unknown
    g.long_range_scan()
    assert unscanned not in plain(s.render())            # now charted


# ---------------------------------------------------------------- cadet

def _cadet_setup(blocked):
    g = Game(seed=1, out=lambda *a: None)
    g.q = EMPTY * 64
    g.srow, g.scol = 4, 1
    g.put(4, 1, SHIP)
    g.put(4, 6, KLINGON)
    if blocked:
        g.put(4, 3, STAR)
    g.k_here = 1
    g.k[1][1:4] = [4, 6, 200]
    return g


def test_cadet_says_clear_when_it_is():
    [t] = cadet.targets(_cadet_setup(blocked=False))
    assert t.clear and t.course == 1.0


def test_cadet_names_the_blocking_star():
    [t] = cadet.targets(_cadet_setup(blocked=True))
    assert not t.clear
    assert t.blocker == (4, 3, STAR)


def test_cadet_verdict_matches_what_the_torpedo_actually_does():
    """The preview is built from the same track the real shot uses."""
    for blocked in (False, True):
        g = _cadet_setup(blocked)
        [t] = cadet.targets(g)
        log = []
        g.out = log.append
        g.ask_num = lambda p, c=t.course: c
        g.torpedoes, g.shields, g.klingons_left = 5, 1e9, 5
        try:
            g.torpedo()
        except MissionEnd:
            pass
        hit = any("KLINGON DESTROYED" in line for line in log)
        assert hit == t.clear, f"cadet said {t.clear}, torpedo {'hit' if hit else 'missed'}"


def test_cadet_line_survives_three_targets_at_every_size():
    """Regression: the hint bar took a row, and at 6x6 in 120x30 the cadet
    line silently fell off the bottom of the panel.  Worst case is three
    Klingons, two blocked -- all three must still be on screen."""
    for size in ((130, 40), (120, 30), (100, 30)):
        s = screen(size=size, cadet=True)
        g = staged(s)
        g.q = EMPTY * 64
        g.srow, g.scol, g.docked = 4, 1, 0
        g.put(4, 1, SHIP)
        for (r, c), what in {(4, 8): KLINGON, (1, 7): KLINGON, (8, 6): KLINGON,
                             (4, 4): STAR, (2, 4): STAR}.items():
            g.put(r, c, what)
        g.k_here = 3
        g.k[1][1:4] = [4, 8, 200]
        g.k[2][1:4] = [1, 7, 200]
        g.k[3][1:4] = [8, 6, 200]
        frame = plain(s.render("PHOTON TORPEDO COURSE (1-9)? "))
        for target in ("4,8→", "1,7→", "8,6→"):
            assert target in frame, f"{size}: cadet lost {target}"
        assert "✗" in frame and "✓" in frame, size


def test_cadet_is_off_unless_asked_for():
    s = screen(cadet=False)
    staged(s)
    assert "CADET" not in plain(s.render())


# ---------------------------------------------------------------- whole games

SCRIPT = "\n".join([
    "SRS", "LRS",
    "COM", "0",          # galactic record overlay
    "COM", "5",          # region map overlay
    "COM", "2",          # torpedo data
    "SHE", "600",
    "PHA", "400",
    "TOR", "2.2",
    "DAM",
    "NAV", "1", "1",
    "LRS",
    "NAV", "5", "2",
    "XXX",
    "NO",
]) + "\n"


def test_a_scripted_mission_plays_through_the_ui():
    for size in ((130, 40), (120, 30), (100, 30)):
        s = screen(keys=SCRIPT, size=size, cadet=True)
        play(s, seed=3)
        log = "\n".join(s.log)
        assert "COMMAND? XXX" in log, size
        assert "KLINGON BATTLE CRUISERS LEFT" in log, size
        assert "MISSION ABORTED" not in log, size


def test_animations_draw_frames():
    s = screen(keys="2.2\n")                 # torpedo() is called directly
    staged(s)
    before = s.stdout.tell()
    s.game.torpedo()
    # one frame per torpedo step plus three for the explosion
    frames = s.stdout.getvalue()[before:].count(app.HOME)
    assert frames >= 5, frames


def test_no_anim_draws_nothing_extra():
    s = screen(keys="2.2\n", animate=False)
    staged(s)
    before = s.stdout.tell()
    s.game.torpedo()
    frames = s.stdout.getvalue()[before:].count(app.HOME)
    assert frames == 1, frames               # just the prompt redraw


def test_events_are_balanced_and_harmless_to_the_teletype():
    """Every begin has an end; with no handler the engine behaves as before."""
    stack, seen = [], []

    def event(name, **info):
        seen.append(name)
        if name == "begin":
            stack.append(info["kind"])
        elif name == "end":
            assert stack.pop() == info["kind"]

    keys = iter(["2.2"])
    g = Game(seed=3, out=lambda *a: None, event=event,
             ask_num=lambda p: float(next(keys, "1")))
    g.enter_quadrant()
    g.long_range_scan()
    g.damage_control()
    g.torpedo()
    assert not stack
    assert "torpedo_step" in seen and "explode" in seen


# ---------------------------------------------------------------- hints

def _engine_prompts():
    """Every prompt string the engine passes to ask_str/ask_num/ask_two."""
    source = open(os.path.join(os.path.dirname(__file__), "..", "trek", "game.py"),
                  encoding="utf-8").read()
    return set(re.findall(r'self\.ask_(?:str|num|two)\(f?"([^"{]+)', source))


def test_every_prompt_has_its_own_hint():
    from trek.ui import hints
    prompts = _engine_prompts()
    assert len(prompts) >= 11, prompts
    default = hints.for_prompt("COMMAND? ", 200).plain
    for prompt in prompts:
        text = hints.for_prompt(prompt + "? ", 200).plain
        assert text.strip(), prompt
        if prompt != "COMMAND":
            assert text != default, f"{prompt!r} fell through to the command bar"


def test_hints_fit_every_supported_width():
    from trek.ui import hints
    for prompt in _engine_prompts():
        for width in (96, 119, 129):
            assert hints.for_prompt(prompt + "? ", width).cell_len <= width, (prompt, width)


def test_the_command_bar_names_all_nine_commands():
    from trek.game import COMMANDS
    from trek.ui import hints
    bar = hints.for_prompt("COMMAND? ", 200).plain
    assert all(command in bar for command in COMMANDS)


def test_the_compass_is_true():
    """Each digit drawn round the ship marks exactly where that course goes.

    Render the compass, read back where each digit landed, then fly one
    sector (warp 1/8) on that course and check the ship arrives there.
    """
    from trek.ui.panels import pixel_panel
    size = 8
    for course in range(1, 9):
        g = Game(seed=1, out=lambda *a: None, ask_num=lambda p: 0)
        g.q = EMPTY * 64
        g.srow, g.scol, g.k_here = 4, 4, 0
        g.put(4, 4, SHIP)

        panel = pixel_panel(g, size, compass=True)
        lines = [line.plain for line in panel.renderable.renderables]
        found = None
        for i, line in enumerate(lines[1:]):
            x = line.find(str(course), 2)
            if x >= 0 and line[2:].count(str(course)) == 1:
                sector_row = i // (size // 2) + 1
                sector_col = (x - 2) // size + 1
                found = (sector_row, sector_col)
        assert found, f"digit {course} not drawn"

        answers = iter([course, 1 / 8])            # one sector
        g.ask_num = lambda p: next(answers)
        g.navigate()
        assert (int(g.srow), int(g.scol)) == found, \
            f"course {course}: digit drawn at {found}, ship went to {g.srow},{g.scol}"


def test_compass_only_appears_for_course_prompts():
    s = screen()
    staged(s)
    course = plain(s.render("COURSE (0-9)? "))
    command = plain(s.render("COMMAND? "))
    assert "see the numbers round your ship" in course
    assert "see the numbers round your ship" not in command


def test_welcome_appears_once():
    from trek.ui import hints
    s = screen(keys="SRS\nSRS\n")
    staged(s)
    s.read("COMMAND? ")
    s.read("COMMAND? ")
    assert s.log.count(hints.WELCOME) == 1


def test_no_hints_gives_the_row_back():
    s = screen(hints=False)
    staged(s)
    frame = plain(s.render("COURSE (0-9)? "))
    assert len(frame.splitlines()) == 39                 # 40 rows, less the prompt
    assert "see the numbers" not in frame and "NAV move" not in frame
    # and a terminal one row too short with hints fits without them
    assert pick_size(100, 28) is None
    assert pick_size(100, 28, reserved=1) == 4


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
