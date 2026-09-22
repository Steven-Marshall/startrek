"""Entry point.  python -m trek

Phase 1: the 1978 listing, scrolling teletype style, print() and input().
No layout, no colour, no panels -- the original rolled up the screen and so
does this.  The split-screen renderer comes later and reads the same engine.
"""

import argparse
import sys

from .basic import Resigned
from .config import CANON, Config
from .game import Game, MissionEnd

from .banner import BANNER                                  # 220-227


def play(seed=None, cfg=CANON):
    print(BANNER)
    while True:
        game = Game(cfg=cfg, seed=seed)
        game.print_orders()                     # 1230
        try:
            game.enter_quadrant()               # 1320
            game.command_loop()                 # 1990
        except MissionEnd as end:
            if not game.end_of_game(end.kind):  # 6210-6400
                return
        seed = None                             # a fresh galaxy next time


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="trek",
        description="Super Star Trek (1978) -- faithful transliteration.")
    parser.add_argument("--seed", type=int, default=None,
                        help="fix the RNG seed for a reproducible galaxy")
    parser.add_argument("--galaxy", type=int, default=None, metavar="N",
                        help="N x N quadrants (canon 8; other values UNTESTED)")
    parser.add_argument("--sector", type=int, default=None, metavar="N",
                        help="N x N sectors per quadrant (canon 8; UNTESTED)")
    parser.add_argument("--fix-starbase-count", action="store_true",
                        help="repair the 1978 B9=2 bug (see BUGS.md #1)")

    ui = parser.add_argument_group("split-screen UI (Phase 2)")
    ui.add_argument("--ui", action="store_true",
                    help="play in the split-screen UI instead of the teletype")
    ui.add_argument("--cadet", action="store_true",
                    help="targeting assist: shows whether a torpedo course is "
                         "clear or blocked (implies --ui)")
    ui.add_argument("--sprites", type=int, choices=(4, 6, 8), default=None,
                    help="sprite size in pixels (default: largest that fits)")
    ui.add_argument("--no-anim", action="store_true",
                    help="no torpedo, phaser or explosion animation")
    ui.add_argument("--no-hints", action="store_true",
                    help="hide the command bar, prompt hints and course compass")
    args = parser.parse_args(argv)

    changes = {}
    if args.galaxy:
        changes["galaxy_size"] = args.galaxy
    if args.sector:
        changes["sector_size"] = args.sector
    if args.fix_starbase_count:
        changes["starbase_count_start"] = 0
    cfg = Config(**{**CANON.__dict__, **changes}) if changes else CANON

    if args.ui or args.cadet or args.sprites or args.no_hints:
        try:
            from .ui import run as run_ui
        except ImportError:
            print("The split-screen UI needs the 'rich' package:  pip install rich")
            return 1
        if run_ui(cfg=cfg, seed=args.seed, cadet=args.cadet,
                  sprite_size=args.sprites, animate=not args.no_anim,
                  hints=not args.no_hints):
            return 0
        print("Terminal too small for the split screen -- falling back to the "
              "teletype.")
        print("For the full view:  wt --size 130,40 -d . pwsh")
        print()

    try:
        play(seed=args.seed, cfg=cfg)
    except Resigned:
        print("\nMISSION ABORTED.")
        return 1
    except KeyboardInterrupt:
        print("\nMISSION ABORTED.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
