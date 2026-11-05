# Performance

What 1.10040 made faster, measured before and after on the same machine (a
small two-core Linux box, Python 3.12, under a virtual display). The figures
are wall-clock times of single runs and move by a tenth or so between runs;
the order of the gains is what matters. Nothing here changes what the app
reads, books or shows.

## The big tables

Sessions, Find, My sites and Where to land were grids of labels: every cell a
widget of its own, all of them built again on every sort. They are now a
tree view that holds only the rows on screen.

| | Before | After |
|---|---|---|
| Rows drawn | 300 rows in 3.1 s | 2,000 rows in 0.06 s |
| Rows held at once | 100 a page, "Show more" for the rest | every row, no pages |
| 200 wheel steps, each drawn | - | 1.9 s |
| 100 scrollbar drags, each drawn | - | 0.6 s |

A label grid much taller than 300 rows could not be drawn at all: it asked
the display for a picture bigger than it would make.

## The first read of the journal

At start-up EDSMT reads the journal you are playing into from the top. A
synthetic journal of 500,000 lines (90 MB) - the most the game writes to one
file before starting the next - in the shapes the game writes:

| | Before | After |
|---|---|---|
| Time to read it | 3.9 to 4.6 s | 2.5 to 3.1 s |
| The window meanwhile | still for all of it | carries on; never still for more than 0.04 s while it reads, and 0.4 s as the app takes over what was read |
| Memory while reading | 304 MB | 26 MB |
| Progress | none | on the status line |

What was slow, found by profiling that journal:

- **The same names tidied again and again.** A journal names a handful of
  commodities hundreds of thousands of times, and each was folded to its
  plain spelling afresh - a quarter of the time. Names are now remembered.
- **Lines nothing reads, parsed anyway.** Chat, music, signals and ships
  targeted are most of a journal. Each line's event name is now read first,
  and a line no part of the app reads is skipped unparsed - about half the
  lines of a typical journal.
- **The whole file at once, on the window's thread.** A journal long enough
  to matter (8 MB or more) is now read 4 MB at a time by a reader of its own
  on another thread; the app's reader takes over everything it learnt when
  it is done. A shorter one is read in one go, as before.

The older journals, read once each for bodies, ship holds, merits and
Powerplay, were already read on another thread, but each file was read whole
into memory first. They are now read a chunk at a time too: a 14 MB journal
is learnt from with 5 MB at the most, where it took more than the file.

## Your own records

4,000 sites holding 20,000 deposits:

| | Before | After |
|---|---|---|
| Loading them | 0.24 s | 0.14 s |
| Listing every site (My sites) | 0.30 to 0.43 s | 0.12 to 0.18 s |
| 200 lookups of a site | 0.22 s | 0.15 to 0.19 s |

The same remembered names do most of this; a lookup now tidies the name it
is asked for once instead of once a row.

## How it is held to that

`tests/test_110040_tables.py` and `tests/test_110040_speed.py` time each of
these against a budget several times what it measures, and check that every
faster path reads exactly what the slower one did.
