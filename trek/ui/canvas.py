"""A tiny pixel canvas, rendered with half-block characters.

A terminal cell is roughly twice as tall as it is wide.  Split it
horizontally and you get two pixels that are close to square: the upper
half-block character "▀" draws the top pixel in the foreground colour and
lets the background colour show through as the bottom pixel.

So one line of text carries two rows of pixels, each with its own colour:

    top only       ▀   fg = top
    bottom only    ▄   fg = bottom
    both, same     █   fg = colour
    both, differ   ▀   fg = top, bg = bottom
    neither        (a space, so the terminal's own background shows)
"""

from rich.style import Style
from rich.text import Text

from .sprites import PALETTE, TRANSPARENT

UPPER, LOWER, FULL = "▀", "▄", "█"


class Canvas:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.px = [[None] * width for _ in range(height)]

    def set(self, x, y, colour):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.px[y][x] = colour

    def blit(self, rows, x0, y0, recolour=None):
        """Draw a sprite with its top-left pixel at (x0, y0).

        recolour, if given, paints every opaque pixel that one palette
        letter -- used for the flash when the ship takes a hit.
        """
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                if ch != TRANSPARENT:
                    self.set(x0 + dx, y0 + dy, PALETTE[recolour or ch])

    def line(self, x0, y0, x1, y1, colour):
        """Bresenham, for phaser and disruptor beams."""
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, colour)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def rows(self):
        """One rich Text per line of terminal output (two pixel rows each)."""
        lines = []
        for y in range(0, self.height, 2):
            top_row = self.px[y]
            bottom_row = self.px[y + 1] if y + 1 < self.height else [None] * self.width
            text = Text()
            for top, bottom in zip(top_row, bottom_row):
                if top is None and bottom is None:
                    text.append(" ")
                elif top == bottom:
                    text.append(FULL, Style(color=top))
                elif bottom is None:
                    text.append(UPPER, Style(color=top))
                elif top is None:
                    text.append(LOWER, Style(color=bottom))
                else:
                    text.append(UPPER, Style(color=top, bgcolor=bottom))
            lines.append(text)
        return lines
