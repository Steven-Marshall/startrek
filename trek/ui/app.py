"""The split-screen front end.

How it fits the engine
----------------------
The engine is pull-based: in the middle of a command it calls ask_num() and
waits.  That sounds awkward for a screen UI, but it is a gift -- every prompt
is a natural moment to redraw.  So:

    out(text)      ->  append to the log (or capture it, inside a block)
    ask_*(prompt)  ->  redraw the whole screen, then read a line
    event(name)    ->  draw a few animation frames

No threads, no event loop.  The engine stays in charge, exactly as in the
teletype version.

The screen runs in the terminal's alternate buffer, so your scrollback is
left alone and restored on exit.  The last few lines of the log are printed
to the normal screen afterwards, so the result of the mission stays visible.
"""

import shutil
import sys
import time

from rich.console import Console
from rich.layout import Layout
from rich.text import Text

from ..banner import BANNER
from ..basic import Resigned, input_str, input_num, input_two_num
from ..config import CANON
from ..game import Game, MissionEnd
from . import hints, panels
from .panels import (pixel_panel, srs_panel, ship_panel, lrs_panel, damage_panel,
                     log_panel, overlay_panel, working, SHORT_RANGE_SENSORS)
from .sprites import SIZES, EXPLOSION_FRAMES

ALT_SCREEN_ON, ALT_SCREEN_OFF = "\x1b[?1049h", "\x1b[?1049l"
CURSOR_ON, CURSOR_OFF = "\x1b[?25h", "\x1b[?25l"
HOME, CLEAR_BELOW = "\x1b[H", "\x1b[J"

OVERLAY_TITLES = {
    "record": "COMPUTER RECORD OF GALAXY",
    "regionmap": "GALAXY — REGION NAMES",
}

# seconds per animation frame
DELAY = {"torpedo": 0.07, "explode": 0.09, "beam": 0.16, "flash": 0.14}


def left_width(size, sectors=8):
    return sectors * size + 4                  # canvas + row labels + border


def fits(size, width, height, sectors=8, reserved=2):
    """Can a frame of this size be drawn in a width x height terminal?

    reserved is the rows kept below the panels: the prompt, plus the hint
    bar when hints are on.  The last column is never used, so full-width
    lines cannot trigger a wrap.
    """
    frame_w, frame_h = width - 1, height - reserved
    canvas_rows = sectors * size // 2 + 1 + 2  # pixels, header, border
    return (left_width(size, sectors) + panels.RIGHT_MIN_WIDTH <= frame_w
            and max(canvas_rows, panels.RIGHT_MIN_HEIGHT) <= frame_h)


def pick_size(width, height, forced=None, sectors=8, reserved=2):
    for size in ([forced] if forced else SIZES):
        if fits(size, width, height, sectors, reserved):
            return size
    return None


class Screen:
    def __init__(self, cadet=False, sprite_size=None, animate=True, hints=True,
                 stdin=None, stdout=None, terminal_size=None):
        self.cadet = cadet
        self.forced_size = sprite_size
        self.animate = animate
        self.hints = hints
        self.reserved = 2 if hints else 1        # hint bar + prompt, or prompt
        self.welcomed = not hints
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self._terminal_size = terminal_size      # fixed size, for tests
        self.console = Console(file=self.stdout, force_terminal=True,
                               color_system="standard", legacy_windows=False,
                               highlight=False, emoji=False)
        self.log = []
        self.block = None          # inside an engine output block, its kind
        self.captured = []
        self.overlay = None        # (title, lines) from COM 0 / COM 5
        self.trail = []            # sectors the current torpedo has crossed
        self.game = None

    # -----------------------------------------------------------------
    # Engine seams
    # -----------------------------------------------------------------
    def new_game(self, cfg=CANON, seed=None):
        self.game = Game(cfg=cfg, seed=seed, out=self.out,
                         ask_str=self.ask_str, ask_num=self.ask_num,
                         ask_two=self.ask_two, event=self.on_event)
        return self.game

    def out(self, text=""):
        for line in str(text).split("\n"):
            if self.block:
                self.captured.append(line)
                continue
            if not line.strip() and (not self.log or not self.log[-1].strip()):
                continue                         # collapse runs of blank lines
            self.log.append(line.rstrip())
        del self.log[:-400]

    def ask_str(self, prompt):
        return input_str(prompt, reader=self.read)

    def ask_num(self, prompt):
        return input_num(prompt, reader=self.read, say=self.out)

    def ask_two(self, prompt):
        return input_two_num(prompt, reader=self.read, say=self.out)

    def read(self, prompt):
        self.trail = []
        if not self.welcomed and prompt.startswith("COMMAND"):
            self.welcomed = True                 # once, just before the first command
            self.log.append(hints.WELCOME)
        self.redraw(prompt=prompt)
        self._write(CURSOR_ON)
        try:
            line = self.stdin.readline()
        except KeyboardInterrupt:
            raise Resigned from None
        finally:
            self._write(CURSOR_OFF)
        if line == "":
            raise Resigned
        answer = line.rstrip("\r\n")
        self.log.append(prompt + answer)
        self.overlay = None                      # COM tables last one command
        return answer.strip()

    def on_event(self, name, **info):
        if name == "begin":
            self.block, self.captured = info["kind"], []
            return
        if name == "end":
            kind, self.block = self.block, None
            if kind in OVERLAY_TITLES:
                self.overlay = (OVERLAY_TITLES[kind], self.captured)
            elif kind == "lrs" and self.captured:
                self.out(self.captured[0])       # "LONG RANGE SCAN FOR QUADRANT 3 , 5"
            self.captured = []
            return

        g = self.game
        if name == "torpedo_missed":
            self.trail = []
        if not self.animate or not working(g, SHORT_RANGE_SENSORS):
            return                               # can't see it without sensors

        row, col = info.get("row"), info.get("col")
        if name == "torpedo_step":
            self.frame([("torpedo", row, col)], DELAY["torpedo"])
            self.trail.append((row, col))
        elif name == "explode":
            self.trail = []
            for f in range(EXPLOSION_FRAMES):
                self.frame([("explode", row, col, f)], DELAY["explode"])
        elif name == "absorbed":
            self.trail = []
            self.frame([("flash", row, col, "W")], DELAY["flash"])
        elif name == "phaser":
            colour = "R" if info.get("hit") else "r"
            self.frame([("beam", int(g.srow), int(g.scol), row, col, colour)], DELAY["beam"])
        elif name == "enterprise_hit":
            self.frame([("beam", row, col, int(g.srow), int(g.scol), "G"),
                        ("flash", int(g.srow), int(g.scol), "R")], DELAY["beam"])

    # -----------------------------------------------------------------
    # Drawing
    # -----------------------------------------------------------------
    def terminal_size(self):
        if self._terminal_size:
            return self._terminal_size
        size = shutil.get_terminal_size((120, 30))
        return size.columns, size.lines

    def frame(self, fx, delay):
        self.redraw(fx=fx)
        if delay:
            time.sleep(delay)

    def build(self, size, frame_w, frame_h, fx=(), prompt=""):
        g = self.game
        left_w = left_width(size, g.cfg.sector_size)
        root = Layout()
        root.split_row(Layout(name="left", size=left_w), Layout(name="right"))
        compass = self.hints and hints.asks_for_course(prompt)
        root["left"].update(pixel_panel(g, size, fx=fx, cadet=self.cadet,
                                        trail=self.trail, height=frame_h,
                                        compass=compass))
        right = root["right"]
        if self.overlay:
            right.update(overlay_panel(*self.overlay))
            return root

        right.split_column(Layout(name="top", size=panels.TOP_HEIGHT),
                           Layout(name="mid", size=panels.MID_HEIGHT),
                           Layout(name="log"))
        right["top"].split_row(Layout(srs_panel(g), size=panels.SRS_WIDTH),
                               Layout(ship_panel(g)))
        right["mid"].split_row(Layout(lrs_panel(g), size=panels.LRS_WIDTH),
                               Layout(damage_panel(g)))
        log_w = frame_w - left_w - 4             # border and padding
        log_h = frame_h - panels.TOP_HEIGHT - panels.MID_HEIGHT - 2
        right["log"].update(log_panel(self.log, log_w, log_h))
        return root

    def render(self, prompt="", fx=()):
        """The whole screen as one string of text and ANSI codes.

        Everything but the bottom row: the panels, then the hint bar if
        hints are on.  The prompt goes on the bottom row, written by redraw().
        """
        width, height = self.terminal_size()
        frame_w, frame_h = width - 1, height - self.reserved
        sectors = self.game.cfg.sector_size
        size = pick_size(width, height, self.forced_size, sectors, self.reserved)
        self.console.size = (frame_w, frame_h)
        with self.console.capture() as capture:
            if size is None:
                self.console.print(Text(
                    f"Terminal too small for the split screen ({width}x{height}).\n"
                    f"Needs about {left_width(SIZES[-1], sectors) + panels.RIGHT_MIN_WIDTH + 1}"
                    f"x{panels.RIGHT_MIN_HEIGHT + self.reserved}.  Try:  wt --size 130,40\n\n"
                    + "\n".join(self.log[-(frame_h - 4):]), style="white"))
            else:
                self.console.print(self.build(size, frame_w, frame_h, fx, prompt))
            if self.hints:
                self.console.print(self.hint_bar(prompt, frame_w),
                                   no_wrap=True, overflow="ellipsis", crop=True)
        return capture.get()

    def hint_bar(self, prompt, width):
        return hints.for_prompt(prompt.rstrip(), width)

    def redraw(self, prompt="", fx=()):
        # One write per frame, homed rather than cleared, so nothing flickers.
        self._write(HOME + self.render(prompt, fx) + CLEAR_BELOW + prompt)

    def _write(self, text):
        self.stdout.write(text)
        self.stdout.flush()


def run(cfg=CANON, seed=None, cadet=False, sprite_size=None, animate=True, hints=True):
    """Play in the split-screen UI.  Returns False if the terminal is too small."""
    width, height = shutil.get_terminal_size((120, 30))
    if pick_size(width, height, sprite_size, cfg.sector_size, 2 if hints else 1) is None:
        return False

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    screen = Screen(cadet=cadet, sprite_size=sprite_size, animate=animate, hints=hints)
    screen._write(ALT_SCREEN_ON + CURSOR_OFF)
    try:
        play(screen, cfg=cfg, seed=seed)
    finally:
        screen._write(CURSOR_ON + ALT_SCREEN_OFF)
        print("\n".join(line for line in screen.log[-14:]))
    return True


def play(screen, cfg=CANON, seed=None):
    """The mission loop, same shape as the teletype's.  Separate from run()
    so tests can drive it without taking over the terminal."""
    screen.log.extend(BANNER.strip("\n").splitlines())
    try:
        while True:
            game = screen.new_game(cfg=cfg, seed=seed)
            game.print_orders()                                   # 1230
            try:
                game.enter_quadrant()                             # 1320
                game.command_loop()                               # 1990
            except MissionEnd as end:
                if not game.end_of_game(end.kind):                # 6210-6400
                    return
            seed = None                          # a fresh galaxy next time
    except Resigned:
        screen.log.append("MISSION ABORTED.")
