# Design

How this port is built, and why — the decisions made along the way, in
roughly the order they were made. For the game's history see
[HISTORY.md](HISTORY.md); for the bugs, [../BUGS.md](../BUGS.md).

---

## What we set out to do

- **A proper ASCII build, as is,** running in a modern terminal. Canon rules,
  canon 8×8 galaxy, canon output down to the typos.
- **"Precise dynamics" — then relaxed to "rough".** The formulas are exact;
  the random numbers feeding them don't need to match 1978 BASIC's `RND`,
  which no modern language can reproduce anyway.
- **Then a split screen:** the ASCII display on one side and a chunky,
  pixellated view of the same quadrant on the other, with better descriptions
  than `107` — without going "ultra modern", and without changing a single
  rule.
- **A fun hobby project, and a learning one.** The code archaeology is part
  of the point.

It was built in three stages:

| | |
|---|---|
| **Phase 1** | The 1978 listing transliterated to Python. Scrolling teletype, `print` and `input`. `python -m trek` |
| **Phase 2** | The split screen, with the pixel quadrant, panels, cadet mode and animation. `python -m trek --ui` |
| **Beginner aids** | A command bar, prompt hints and a course compass round the ship |

---

## The engine

### Transliterate, don't reimplement

`trek/game.py` follows `SUPERSTARTREK.BAS` section by section. Every formula
carries its BASIC line number in a comment, so any behaviour can be traced
back to the listing:

```python
h = int((h1 / self.distance_to(i)) * (self.rng.random() + 2))   # 4480
```

Arrays are **1-based** with index 0 unused, so `K(I,3)` in the listing is
`self.k[i][3]` here. Where the original is odd, it stays odd.

### The quadrant stays a string

Line 8670 stored the current quadrant as `Q$`, one 192-character string,
three characters per sector, rebuilt in full on every write. Collision
detection was string comparison. That is kept verbatim — it's the most
characterful thing in the program, and it turned out to be exactly what a
renderer wants to read.

### Seams, not stdio

The engine never calls `print()` or `input()`. It talks through callables on
the `Game` object:

| Seam | Purpose |
|---|---|
| `out(text)` | every line of output |
| `ask_str`, `ask_num`, `ask_two` | every prompt |
| `event(name, **info)` | moments worth animating, and markers around blocks of output |

The teletype, the split screen, the tests and the autoplay bot are all just
different things plugged into those seams.

**How the split screen gets its data** was the user's idea: don't re-skin the
engine, wrap it — input in, output out. Refined in one respect: the renderer
**reads the engine's state** (`game.q`, `game.energy`, `game.chart`, …)
rather than parsing its printed text, because the grid is only printed when
the player asks for a scan. Reading state means the pixel view is never stale.

**The `event` seam was a change to the engine**, and was declared as one at
the time. Reading state covers static panels, but a torpedo in flight or an
explosion isn't *in* the state afterwards — by the time the renderer looks,
the Klingon is just an empty sector. So the engine announces those moments.
It also brackets blocks of output (`begin`/`end` around a scan or the
computer's tables) so the split screen can route them to a panel instead of
the log. Events change no behaviour; the teletype ignores them.

Two further refactors, both behaviour-preserving, made the engine's maths
reusable:

- `bearing()` — the direction calculator (lines 8220–8450) as a pure function.
  Building it exposed a real port bug (see BUGS.md, port errata).
- `torpedo_track()` — the torpedo's walk (4850–4960) as a pure generator. The
  real shot runs on it, and so does the cadet preview, so the two can never
  disagree.

### Configurable, but canon

`trek/config.py` names every magic number from the listing with its line
number. Canon is the default and the only thing tested. Worth knowing:

- In the original, galaxy size and sector size were **the same constant** —
  line 475's `FNR()` picked a random 1–8 for both. Config splits them.
- The quadrant encoding `G(I,J) = K3*100 + B3*10 + S3` is **base 10**, which
  structurally caps a quadrant at 9 of anything. That's a storage format, not
  a constant.
- The balance is tuned for 64 quadrants — the listing even patches it at line
  1040 ("if we rolled more Klingons than days, extend the clock").

### Bugs are preserved

**Preserve, unless it makes the game unplayable.** Guard only what would crash
Python where BASIC merely halted. Everything is catalogued in BUGS.md,
including this port's own mistakes and which findings outside sources
confirmed.

### Random numbers

Python's `random.Random(seed)`, one instance per game, so `--seed N` replays a
galaxy exactly. A TRS-80 and an Apple II running the same listing didn't
agree either.

---

## The split screen

### Why Python and `rich`

Python for a small, I/O-bound hobby project. For the screen, `rich` rather
than `textual`: `textual` is a full application framework and makes things
look like a modern TUI app, with mouse support and CSS styling; `rich`'s
layouts give two panes and control of every character. Go with `bubbletea`
was considered — a single binary is nice — but not worth the extra code for
this.

### Pull-based engine, redraw on every prompt

The engine asks for input in the middle of a command and waits. That suits a
screen UI surprisingly well: **every prompt is a natural moment to redraw.**
No threads, no event loop. A full frame renders in about 11 ms, so animation
frames just redraw the whole screen too. The screen runs in the terminal's
alternate buffer, so scrollback is untouched, and the last lines of the log
are printed on exit.

### The fairness rule

> A panel may only show what the original gives you for free, and it must
> break when the instrument behind it breaks.

`SRS`, `LRS` and `COM` cost no time and no energy, so a panel that keeps their
results on screen is just "auto-typing a free command" — it changes nothing
about difficulty. But damage has to matter:

| Damaged | Effect |
|---|---|
| short range sensors | the pixel view becomes static; the ASCII scan goes dark |
| long range sensors | the long range panel says so |
| library computer | no decoding of `107`, no cadet assist |
| damage control | no damage report |

Ship-internal readouts (energy, shields, torpedoes, the clock) stay up. The
long range panel shows the player's **chart**, not the galaxy, so `LRS` is
still something to remember to do.

### Cadet mode (opt-in)

The one feature that crosses the fairness line, so it's off by default. For
each Klingon it shows the `COM 2` course (free anyway) and then what the
original never tells you: whether a torpedo on that course gets through or
hits a star first. Built from `bearing()` and `torpedo_track()`, with the
course rounded to two decimals *before* the check — so a tick means "type
exactly this and it hits". No computer, no cadet.

### Animation (modest)

Only where the original prints something anyway: the torpedo flying its
track, phaser and disruptor beams, the ship flashing when hit, three-frame
explosions. Nothing animates when the short range sensors are down.
`--no-anim` turns it off.

### Pixels and sprites

- **Half-block characters** (`▀ ▄ █`) give two pixels per text cell, which
  come out roughly square because terminal cells are about twice as tall as
  they are wide.
- **Sprites at 4×4, 6×6 and 8×8**, chosen automatically to fit the terminal
  (8×8 at 130×40, 6×6 at the Windows Terminal default of 120×30, 4×4 down to
  about 97×29). They are data — lists of strings of palette letters in
  `trek/ui/sprites.py` — so they can be edited without touching code.
- **The 16 standard ANSI colours and nothing else**, for a CGA-era feel.
  Colour does most of the work at this size: Enterprise white, Klingons green,
  stars yellow, starbases cyan, and borders that turn red at `*RED*`.
- The first Enterprise read as a table lamp; the second pass fixed it. That
  was only visible because frames were rendered to images and looked at.

### Beginner aids

The command names are the easy part — anything unrecognised lists them, as in
1978. What stops people is the prompts. So:

- **A command bar** along the bottom while the game waits for a command.
- **Prompt hints**: the bar explains each prompt (shields take the new
  *total*; phaser energy splits between every Klingon and fades with
  distance; what each `COM` number does; `0` cancels). Every hint is a rule
  of the 1978 game, checked against the listing, with line numbers in
  `trek/ui/hints.py`.
- **A compass round the ship** whenever a course is asked for, taken from the
  engine's own course table.

`--no-hints` turns them all off and gives the row back.

### Terminal size on Windows

Windows Terminal doesn't implement the escape sequence that lets a program
resize its own window, so the game adapts to whatever size it gets, and
`trek.cmd` opens a 130×40 window with `wt --size`. (In a `.cmd` file, the
script directory must be quoted `"%~dp0."` — a bare `"%~dp0"` ends in a
backslash that escapes the closing quote.)

---

## Testing

BASIC's random numbers can't be reproduced, so there are no golden
transcripts. The tests check **rules and structure** instead:

- that the base-10 quadrant encoding round-trips for every value 0–999
- that every ending is reachable
- that docking resupplies but does not repair
- **exhaustively, that a torpedo fired along the computer's bearing hits every
  target from every square** of an empty quadrant — 4,032 shots
- that the compass drawn round the ship is true: one sector on each course
  lands where its digit was drawn
- that every panel dies with its instrument, and every prompt has its own hint

Beyond the unit tests:

- **`tools/autoplay.py`** plays the real engine through its seams. It's how
  the balance was measured, and it found the strategic facts in the README —
  torpedoes always kill, a quadrant crossing costs one stardate at any warp.
  A competent bot wins about 8–9% of games.
- **`tools/screenshot.py`** rasterises a UI frame to PNG in Windows
  Terminal's colour scheme, and **`tools/sprite_sheet.py`** draws every
  sprite. The UI was checked by looking at those images, which is what caught
  the lamp-shaped Enterprise and a cadet line silently falling off the bottom
  of the panel.

---

## What's next

- A second pass on the sprites.
- The unexplained memory of a **5×5** grid — see HISTORY.md.
- Sibling projects built the same way: *Imhotep* (a 1980 TRS-80 pyramid
  builder), perhaps *Football Manager*. Shared code is copied rather than
  extracted into a library until there's a third game to show what the
  library should be.
