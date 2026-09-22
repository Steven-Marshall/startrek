"""Render a frame of the split-screen UI to a PNG.

    python tools/screenshot.py                       -> screenshot.png
    python tools/screenshot.py out.png --size 120x30 --seed 3 --cadet
    python tools/screenshot.py out.png --damage 2    (break a device)

Uses the real Screen and panels, so the picture is exactly what the game
draws -- just rasterised here instead of by a terminal.  Colours are Windows
Terminal's default "Campbell" scheme.  Box-drawing and block characters are
drawn geometrically rather than from a font, which is how a terminal does it
too, so the pixel art comes out true.

Needs Pillow (pip install pillow).  The game itself does not.
"""

import argparse
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from PIL import Image, ImageDraw, ImageFont                         # noqa: E402
from rich.console import Console                                    # noqa: E402
from rich.terminal_theme import TerminalTheme                       # noqa: E402

from trek.ui.app import Screen, pick_size                           # noqa: E402

CAMPBELL = TerminalTheme(
    (12, 12, 12), (204, 204, 204),
    [(12, 12, 12), (197, 15, 31), (19, 161, 14), (193, 156, 0),
     (0, 55, 218), (136, 23, 152), (58, 150, 221), (204, 204, 204)],
    [(118, 118, 118), (231, 72, 86), (22, 198, 12), (249, 241, 165),
     (59, 120, 255), (180, 0, 158), (97, 214, 214), (242, 242, 242)],
)
CELL_W, CELL_H = 10, 20            # 1:2, so half-block pixels come out square
FONTS = "C:/Windows/Fonts/"

# box drawing: which of the four arms (up, right, down, left) each char has
ARMS = {
    "\u2500": "rl", "\u2502": "ud", "\u256d": "rd", "\u256e": "ld",
    "\u2570": "ur", "\u256f": "ul", "\u250c": "rd", "\u2510": "ld",
    "\u2514": "ur", "\u2518": "ul", "\u251c": "urd", "\u2524": "uld",
    "\u252c": "rld", "\u2534": "url", "\u253c": "urld",
}


def load_fonts():
    def font(name):
        try:
            return ImageFont.truetype(FONTS + name, 16)
        except OSError:
            return None
    text = font("consola.ttf") or ImageFont.load_default()
    bold = font("consolab.ttf") or text
    symbols = font("seguisym.ttf") or text
    return text, bold, symbols


def rgb(color, foreground):
    if color is None or color.is_default:
        return CAMPBELL.foreground_color if foreground else CAMPBELL.background_color
    return tuple(color.get_truecolor(CAMPBELL, foreground))


def draw_cell(draw, ch, x, y, fg, bg, fonts, bold):
    x0, y0, x1, y1 = x, y, x + CELL_W - 1, y + CELL_H - 1
    draw.rectangle([x0, y0, x1, y1], fill=bg)
    mid_x, mid_y = x + CELL_W // 2, y + CELL_H // 2
    if ch == " ":
        return
    if ch == "\u2580":                                   # upper half block
        draw.rectangle([x0, y0, x1, mid_y - 1], fill=fg)
    elif ch == "\u2584":                                 # lower half block
        draw.rectangle([x0, mid_y, x1, y1], fill=fg)
    elif ch == "\u2588":                                 # full block
        draw.rectangle([x0, y0, x1, y1], fill=fg)
    elif ch == "\u2591":                                 # light shade
        for py in range(y0, y1 + 1, 3):
            for px in range(x0 + (py // 3) % 2, x1 + 1, 3):
                draw.point((px, py), fill=fg)
    elif ch in ARMS:
        arms = ARMS[ch]
        if "u" in arms:
            draw.line([mid_x, y0, mid_x, mid_y], fill=fg)
        if "d" in arms:
            draw.line([mid_x, mid_y, mid_x, y1], fill=fg)
        if "l" in arms:
            draw.line([x0, mid_y, mid_x, mid_y], fill=fg)
        if "r" in arms:
            draw.line([mid_x, mid_y, x1, mid_y], fill=fg)
    else:
        text, heavy, symbols = fonts
        font = symbols if ord(ch) > 0x2000 else (heavy if bold else text)
        draw.text((mid_x, mid_y), ch, fill=fg, font=font, anchor="mm")


def rasterise(screen, width, height, prompt="COMMAND? ", fx=()):
    frame_w, frame_h = width - 1, height - screen.reserved
    size = pick_size(width, height, screen.forced_size, screen.game.cfg.sector_size,
                     screen.reserved)
    layout = screen.build(size, frame_w, frame_h, fx, prompt)
    console = Console(width=frame_w, height=frame_h, force_terminal=True,
                      color_system="standard", file=io.StringIO())
    lines = console.render_lines(layout, console.options.update_dimensions(frame_w, frame_h))
    if screen.hints:
        bar = screen.hint_bar(prompt, frame_w)
        lines += console.render_lines(bar, console.options.update(width=frame_w, height=1,
                                                                   no_wrap=True), pad=False)[:1]

    image = Image.new("RGB", (width * CELL_W, height * CELL_H), CAMPBELL.background_color)
    draw = ImageDraw.Draw(image)
    fonts = load_fonts()
    for row, segments in enumerate(lines + [[]]):
        col = 0
        if row == len(lines):                            # the prompt line
            from rich.segment import Segment
            segments = [Segment(prompt)]
        for seg in segments:
            style = seg.style
            fg = rgb(style.color if style else None, True)
            bg = rgb(style.bgcolor if style else None, False)
            if style and style.reverse:
                fg, bg = bg, fg
            for ch in seg.text:
                draw_cell(draw, ch, col * CELL_W, row * CELL_H, fg, bg, fonts,
                          bool(style and style.bold))
                col += 1
    return image


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("out", nargs="?", default="screenshot.png")
    parser.add_argument("--size", default="130x40")
    parser.add_argument("--seed", type=int, default=3)
    parser.add_argument("--cadet", action="store_true")
    parser.add_argument("--sprites", type=int, choices=(4, 6, 8))
    parser.add_argument("--damage", type=int, action="append", default=[],
                        help="device number to damage (repeatable)")
    parser.add_argument("--keys", default="",
                        help="commands to play first, separated by ';'")
    parser.add_argument("--prompt", default="COMMAND? ",
                        help="the prompt to show, e.g. 'COURSE (0-9)? '")
    parser.add_argument("--no-hints", action="store_true")
    args = parser.parse_args(argv)
    width, height = map(int, args.size.lower().split("x"))

    keys = "\n".join(args.keys.split(";")) + "\n" if args.keys else ""
    screen = Screen(cadet=args.cadet, sprite_size=args.sprites, animate=False,
                    hints=not args.no_hints,
                    stdin=io.StringIO(keys), stdout=io.StringIO(),
                    terminal_size=(width, height))
    game = screen.new_game(seed=args.seed)
    game.print_orders()
    game.enter_quadrant()
    for device in args.damage:
        game.damage[device] = -1.5
    if keys:
        from trek.basic import Resigned
        from trek.game import MissionEnd
        try:
            game.command_loop()
        except (Resigned, MissionEnd):
            pass
    rasterise(screen, width, height, prompt=args.prompt).save(args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
