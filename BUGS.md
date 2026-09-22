# Bugs in the 1978 listing

Policy: **preserve, unless it makes the game unplayable.** The listing is an
artifact. A game that behaves exactly like the one on a 1979 TRS-80, warts
included, is more interesting than a corrected one.

Where a bug would crash Python but merely halted BASIC with an error message,
it is guarded rather than fixed — the behaviour is documented below and the
original logic is left intact around the guard.

---

## 1. The starbase count starts at two — PRESERVED

```basic
440  ... B9=2 ...                         <- starts at TWO
980  IF RND(1)>.96 THEN B3=1:B9=B9+1      <- then counts up from there
1100 IF B9<>0 THEN 1200                   <- "if no starbases exist..."
1150 IF G(Q1,Q2)<200 THEN ...             <- ...place one.  DEAD CODE.
1272 PRINT "  ";B9;"STARBASE";X$;" IN THE GALAXY..."
```

`B9` is initialised to 2 and never zeroed before the counting loop.

**Two consequences.** The mission briefing overstates the starbase count by
two, every single game. And the "galaxy generated with no starbases, force one
into existence" fallback at 1150-1160 can never run, because `B9` is never 0
at line 1100 — so the rare zero-base galaxy quietly dooms you instead of
rescuing you.

Not game-breaking; you can still win, you are just lied to about your supply
lines. Preserved, and it is the reason a freshly generated galaxy will tell
you there are 6 starbases when the map holds 4.

Run `python -m trek --fix-starbase-count` to set it to 0, which both corrects
the count and reactivates the dead fallback.

Independently reported by
[jkboyce/super-star-trek](https://github.com/jkboyce/super-star-trek):
"line `440`: `B9` should be initialized to 0, not 2".

## 2. `DEF FND` ignores its own argument — FIXED (behaviour identical)

```basic
470 DEF FND(D)=SQR((K(I,1)-S1)^2+(K(I,2)-S2)^2)
```

Distance to klingon number `I` — not `D`. The parameter is never read; the
function reaches out to whatever the global `I` happens to be, and is invoked
as `FND(0)` and `FND(1)` interchangeably. It works only because every call
site sits inside `FOR I=1 TO 3`.

Not a bug in BASIC, but the single most likely thing to break silently in
translation. `distance_to(i)` takes a real index here. Every call site was
checked against the listing; results are identical.

## 3. Direction calculator divides by zero — GUARDED

```basic
8270 IF A=0 THEN C1=5:GOTO 8290
8290 IF ABS(A)<=ABS(X) THEN 8330
8330 PRINT "DIRECTION =";C1+(ABS(A)/ABS(X))
```

Ask the direction/distance calculator (COM option 4) for the bearing from a
point to itself and both deltas are zero, so line 8330 evaluates `0/0`.
BASIC halted with `?DIVISION BY ZERO ERROR`, dumping you out of the game.

Python would raise `ZeroDivisionError` and kill the process, which crosses the
"unplayable" line. Guarded: a zero-length bearing prints as direction 5 and
distance 0. The surrounding branch structure is untouched.

jkboyce's port lists four lines as able to divide by zero — 8310, 8330, 8430
and 8450. Running the unguarded branch logic over all 4,096 start/end
coordinate pairs shows only **8330** is reachable with a zero divisor, exactly
64 times: the 64 cases where start equals end. The other three are
over-cautious — each sits behind a comparison that guarantees its divisor is
non-zero.

## 4. Torpedo can strike an unknown object — PRESERVED

```basic
5280 A$=">!<":Z1=X:Z2=Y:GOSUB 8830:IF Z3=0 THEN 4760
```

The torpedo track tests each sector for empty, klingon, star, then starbase.
If it is none of those, control jumps back to line 4760 — *re-asking for a
course*, having already spent the torpedo and 2 units of energy.

Unreachable in canon, since only those four things ever occupy a sector.
Preserved as written, including the lost torpedo.

## 5. A missed klingon lookup blames klingon 3 — PRESERVED

```basic
5150 FOR I=1TO3:IF X3=K(I,1) AND Y3=K(I,2) THEN 5190
5180 NEXT I:I=3
5190 K(I,3)=0
```

When a torpedo destroys a klingon, the code searches `K()` for the one at
those coordinates. If the search falls through, it forces `I=3` and zeroes
klingon 3 regardless — which may be a different klingon, or one already dead.
The explicit `I=3` exists to stop the index running off the end of the array
after a completed `FOR`, so it is a deliberate guard with a careless fallback.

Requires the quadrant string and `K()` to disagree, which should not happen.
Preserved.

## 6. Klingons weaken themselves by firing — PRESERVED (behaviour)

```basic
6060 H=INT((K(I,3)/FND(1))*(2+RND(1))):S=S-H:K(I,3)=K(I,3)/(3+RND(0))
```

Every time a klingon fires it divides its own strength by 3-4. This is almost
certainly intentional (it stops a single quadrant being an instant death
sentence) but it reads like an accident and is worth knowing: **the longer a
fight goes on, the weaker the enemy gets, whether or not you hit them.**

Note `RND(0)`. In Microsoft BASIC `RND(0)` re-returns the *previous* random
number rather than drawing a new one, so the original reused the value from
`RND(1)` earlier on the same line. We draw a fresh number — a deliberate
divergence under the project's "rough dynamics" rule. See DIVERGENCES below.

## 7. You can win in overtime — PRESERVED

Time advances in three places. The deadline is checked in only two.

| Line | Advances time | Checks deadline |
|---|---|---|
| 3450 | `T=T+T8` — moving within a quadrant | yes |
| 3870 | `T=T+1` — crossing into a new quadrant | **no** |
| 5890 | `T=T+D3+.1` — repairs while docked | **no** |

```basic
3450 T=T+T8:IF T>T0+T9 THEN 6220
3870 T=T+1:GOSUB 3910:GOTO 1320
5890 NEXT I:T=T+D3+.1
```

So a quadrant crossing or a repair order can carry you past the deadline
without ending the game. And because phasers and torpedoes cost no time and
never consult the clock, you can keep fighting — and win — in overtime. The
game only notices when you next make an in-quadrant move or hit the rim.

Found while auditing this port against the listing, not from any commentary.
Preserved; it is how the 1978 game behaves, and it rewards a player who
knows it.

## 8. The phaser penalty is wired to the wrong device — PRESERVED

```basic
4330 IF D(8)<0 THEN PRINT "COMPUTER FAILURE HAMPERS ACCURACY"   <- warns on D(8)
4410 E=E-X:IF D(7)<0 THEN X=X*RND(1)                            <- penalises on D(7)
```

In the device table at 8790, `D(7)` is SHIELD CONTROL and `D(8)` is the
LIBRARY-COMPUTER. The warning and the penalty point at different devices:

- **Computer damaged:** you are warned `COMPUTER FAILURE HAMPERS ACCURACY`,
  and then nothing happens. The volley lands at full strength.
- **Shield control damaged:** no warning at all, and the volley is multiplied
  by a random 0–1. Fire 800 units and anything from 0 to 800 arrives.

The intent is plainly that computer damage degrades accuracy.

Missed in the first pass of this port; found by
[jkboyce/super-star-trek](https://github.com/jkboyce/super-star-trek), whose
README lists it as "line `4410`: `D(7)` should be `D(6)`". That wording mixes
their 0-based Python indices with the listing's 1-based ones — their code
changes the penalty from `d[6]` (shield control) to `d[7]` (computer), which
in the listing's terms is **`D(7)` → `D(8)`**. They fixed it; this port keeps
it, since it is not unplayable, only unfair.

## 9. Spelling — PRESERVED, obviously

`ORIGIONAL`, `ENTERPRIZE`, `EXHISTS`, `MAXIUM`, `NAVAGATION`, `CONGRULATION`,
`THEN LAST`, `THEN FEDERATION`, `FDERATION`, `CRUSER`, `YOUR ON IN`, and a
postal address in Baltimore for bug reports. All intact.

---

# Port errata

Mistakes in *this* port, since fixed. Listed because a transliteration that
quietly diverges is worse than one that says where it went wrong.

**Rim bounces were free.** Line 3860 sends a move that ends in the starting
quadrant — typically after being clamped back from the galactic rim — to line
3370, which charges stardates like any in-quadrant move. The port inlined
3370 by hand and left out the clock charge at 3430-3450. Found while auditing
the stardate claims against the listing; now routed through the same code as
every other arrival, with a regression test.

**Bug #8 was described as intended.** Early notes presented the phaser
penalty as "shield control damage hampers accuracy", when it is the listing
wiring the penalty to the wrong device.

**The computer pointed west targets the wrong way.** The direction calculator
(COM 2, 3 and 4) skipped line 8360:

```basic
8350 IF A>0 THEN C1=3:GOTO 8420
8360 IF X<>0 THEN C1=5:GOTO 8290      <- missing from the port
8410 C1=7
```

so every target to the west or south-west fell through to 8410. A Klingon due
west was reported on course **9** — which is east. A player trusting COM 2
would have fired straight away from it. Found while building the cadet
overlay, which needed the bearing to be exact.

Now `Game.bearing()`, shared by the computer and the cadet overlay, with two
tests: all eight compass points, and an exhaustive check that a torpedo fired
along the computer's bearing hits every target from every square of an empty
quadrant — 4,032 shots, no misses. That holds because the listing's formula
is linear in the *ratio* of the deltas, exactly undoing the torpedo's course
interpolation. An `atan2` bearing, linear in the angle instead, misses about
4% of them — which is what the autoplay bot was using, and why its torpedoes
missed. (That was first put down to the track's `INT(X+.5)` rounding. It was
not; the game's own bearing never misses a clear shot.)

---

# Checked against outside sources

| Claim | Listing | Outside source |
|---|---|---|
| A torpedo hit always destroys | 5060-5110, no strength check | Aaron Reed, [*50 Years of Text Games*](https://if50.substack.com/p/1974-super-star-trek): "Torpedoes, however, always destroy a single enemy, but you need line of sight to use them" |
| Phaser damage falls off with distance | 4480 | Same article: damage "varies based on distance, randomness, and the strength of the enemy's shields" |
| `B9=2` overcounts starbases | 440 | jkboyce, as above |
| Direction calculator can divide by zero | 8330 | jkboyce (over-inclusive; see #3) |
| Phaser penalty on the wrong device | 4330 vs 4410 | jkboyce — found there, not here |
| Crossing a quadrant costs 1 stardate at any warp | 3860-3870 | **Nothing found.** Verified in the listing and by test only |
| Overtime loophole | 3450 / 3870 / 5890 | **Nothing found.** Verified in the listing and by test only |

Watch out for Eric S. Raymond's
[Super Star Trek documentation](http://www.catb.org/~esr/super-star-trek/sst-doc.html)
when searching. It describes a *different* game with the same name — the UT
Austin mainframe version by Matuszek, Reynolds and Smith, the ancestor of BSD
`trek` — with warp-cubed energy costs, impulse engines, novas and life
support. None of that applies to this listing, and search summaries blend the
two freely.

Aaron Reed's article describes the quadrant as **three** strings (because of a
72-character string limit) and says the program defines "exactly one
function". The 1978 listing has a single 192-character `Q$` and two functions,
`FND` and `FNR` — he is describing Leedom's earlier version, before John
Gorders' 1978 conversion to Microsoft 8K BASIC merged them.

---

# Deliberate divergences

Things changed on purpose, none of which alter the rules.

**The random number generator.** BASIC's `RND` is not reproducible in any
modern language, and a TRS-80 and an Apple II running this same listing gave
different rolls anyway. Formulas are copied exactly; the numbers feeding them
are Python's. `--seed N` fixes the sequence for a reproducible galaxy.

**Number formatting is emulated, not inherited.** `trek/basic.py` reimplements
MS BASIC's `PRINT` rules — leading sign slot, trailing space, no decimal point
on integers, leading zero dropped from `0.5`. Without it the columns do not
line up and the screen is subtly wrong. The stray space in `SECTOR 3 , 2` is
canon.

**`LEFT$(x,0)` special cases dropped.** Lines 8680 and 8690 exist only because
some BASIC dialects errored on a zero-length `LEFT$`/`RIGHT$`. Python slicing
handles both ends, so the two special cases are gone. `Q$` itself is still a
flat 192-character string rebuilt on every write, exactly as line 8700 did it.

**`GOTO` became structure.** The command dispatch, the torpedo track loop and
the end-of-game block are functions and exceptions rather than jumps. Line
numbers are in the comments so any path can be traced back.
