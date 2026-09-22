# History

Where this game came from, which version this port is, and the research
behind it. Links are at the bottom.

---

## The family tree

**Star Trek (1971) — Mike Mayfield.** Written by a high-school student with
unofficial access to a Sigma 7 at the University of California, Irvine, then
rewritten in BASIC on an HP 2000C, finished October 1972. It went into the HP
contributed-program library in February 1973, which is how it escaped into the
world. Galaxy: 8×8 quadrants of 8×8 sectors.

**SPACWR (1973) — David Ahl and Mary Cole.** Ahl converted the HP version to
BASIC-PLUS for DEC's RSTS-11 and published it as *SPACWR* ("Space War — in
retrospect, an incorrect name") in *101 BASIC Computer Games*.

**Super Star Trek (1974) — Bob Leedom.** A Westinghouse engineer ported it to a
Data General Nova 800 with 32K of memory and spent the headroom on it:
three-letter commands (`NAV`, `SRS`, `PHA` …), a better map, and chatter from
Spock, Scotty, Uhura and Sulu.

**The 1978 listing — this port's source.** Converted to Microsoft 8K BASIC by
John Gorders (the listing's header dates the conversion 16 March 1978, and the
listing itself 16 May 1978). Printed in Ahl's *BASIC Computer Games*
(Microcomputer Edition, 1978), the first computer book to sell a million
copies — which is why this is the version a generation typed in on TRS-80s,
Apple IIs and PETs.

**A separate branch: the mainframe "Super Star Trek".** Written at the
University of Texas at Austin from 1973 by David Matuszek, Paul Reynolds and
Don Smith, in FORTRAN. Eric Allman translated it to C in May 1976, and it
became BSD `trek`, still in the `bsdgames` package. Eric S. Raymond maintains
a modernised descendant, `sst`. *This is a different game* — warp-cubed
energy, impulse engines, novas, life support — and search results mix the two
up freely.

**Descendants worth knowing:** *Star Fleet I: The War Begins* (1985), the same
game with the serial numbers filed off, which *Computer Gaming World* called a
"superb rendition of the 'main-frame' Star Trek"; *EGA Trek*, late-1980s DOS
shareware with a graphical, multi-pane display — a direct ancestor of this
project's split screen; and *Netrek* (1988), the multiplayer one.

---

## The 1978 listing, up close

425 lines of Microsoft BASIC. Its header gives a postal address for bug
reports — Westinghouse Defense & Electronics Systems Center, Baltimore — and
spells "original" as `ORIGIONAL`. Nobody ever fixed it.

The details that shaped this port are covered in [DESIGN.md](DESIGN.md) and
[../BUGS.md](../BUGS.md): the quadrant kept as a 192-character string, the
galaxy stored as one base-10 integer per quadrant (`107` is literally what's
in the array), `RIGHT$(STR$(n+1000),3)` as zero-padding before `PRINT USING`
existed, a compass built as a lookup table because it was cheaper than `SIN`,
and `DEF FND` reading a global instead of its own argument.

The listing used here comes from the
[coding-horror/basic-computer-games](https://github.com/coding-horror/basic-computer-games)
project (`84_Super_Star_Trek/superstartrek.bas`), which collects the book's
programs. It isn't copied into this repository; fetch it from there to read
alongside the Python.

---

## Checking the port against outside sources

Findings from the listing and the tests were checked against other people's
work:

- **Jim Boyce's faithful Python port** ([jkboyce/super-star-trek](https://github.com/jkboyce/super-star-trek))
  independently found the `B9=2` starbase bug and the division by zero, and
  found one this port had missed — the phaser penalty wired to the wrong
  device. (Its README writes that as "`D(7)` should be `D(6)`", mixing 0-based
  Python indices with the listing's 1-based ones; in the listing's terms it's
  `D(7)` → `D(8)`.)
- **Aaron Reed's history of the game** confirms that "torpedoes … always
  destroy a single enemy". He describes the quadrant as three strings and the
  program as defining one function, where the 1978 listing has one
  192-character string and two functions — most likely because he's
  describing Leedom's version from before the 1978 Microsoft BASIC conversion.
- Two of this port's findings turned up nowhere else and rest on the listing
  and the tests alone: that crossing into a new quadrant costs one stardate at
  any warp, and that you can win in overtime.

The full table is in BUGS.md.

---

## The 5×5 mystery

This project started from a memory of playing Star Trek on a **5×5 grid**, on
a TRS-80 or a ZX81. The canonical game is 8×8, and no well-known 5×5 version
has turned up. Some clues:

- It was a type-in, so anyone could shrink the arrays, and many small-machine
  versions did adapt it. A variant with a 10×10 grid and clock-face directions
  is documented.
- The **ZX81's 32-column screen** is a plausible reason to shrink it. The
  original's 8×8 scan takes 24 columns before its status panel, which leaves
  nothing for the panel on a ZX81; a 5×5 grid would fit.
- *SoftSide* magazine's May 1980 issue — a TRS-80 magazine — featured a Star
  Trek. It's a three-dimensional variant (8×8×3, "192 quadrants"), so not the
  one.

Still unexplained. If a 5×5 version surfaces, it would be a lovely thing to
add here.

---

## Sources

- [Star Trek (1971 video game)](https://en.wikipedia.org/wiki/Star_Trek_(1971_video_game)) ·
  [BASIC Computer Games](https://en.wikipedia.org/wiki/BASIC_Computer_Games)
- [BASIC Computer Games: Super Star Trek (Atari Archives)](https://www.atariarchives.org/basicgames/showpage.php?page=157)
- [coding-horror/basic-computer-games — Super Star Trek](https://github.com/coding-horror/basic-computer-games/tree/main/84_Super_Star_Trek)
- [Aaron Reed, "1974: Super Star Trek"](https://if50.substack.com/p/1974-super-star-trek) ·
  [Code Archaeology with Super Star Trek](https://medium.com/swlh/code-archaeology-with-super-star-trek-928101eb010c)
- [jkboyce/super-star-trek](https://github.com/jkboyce/super-star-trek)
- [ESR's Super Star Trek (the mainframe game)](http://www.catb.org/~esr/super-star-trek/sst-doc.html) ·
  [trek(6)](https://man.openbsd.org/trek.6)
- [Versions of the 1971 Star Trek game](https://djcube.co.uk/versions-of-the-1971-star-trek-game/)
- [Star Fleet I: The War Begins](https://en.wikipedia.org/wiki/Star_Fleet_I:_The_War_Begins)
- [SoftSide #20, May 1980](https://archive.org/details/softside-magazine-20)
