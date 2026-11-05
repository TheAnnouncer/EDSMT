"""The journal read from the top a chunk at a time, on a thread of its own
(1.10040, #276) - and the older journals read a chunk at a time too.

At start-up EDSMT reads the journal you are playing into from the top, so
the books see the session you are in. A long evening's journal runs to half
a million lines; read in one go on the window's thread, the window stood
still until it was done and held the whole file in memory. Now a reader of
its own reads it a few megabytes at a time on a thread, the window says how
far it has got, and the app's reader takes over everything it learnt once it
is done. A journal shorter than THREAD_FROM_BYTES is still read in one go:
it takes less time than starting a thread.

The older journals - read once each for bodies, holds, merits and Powerplay -
were already read on a thread, but each was read whole into memory first.
lines_of() and contains() read them a chunk at a time.

Nothing here touches a widget.
"""

import os
import re
import threading

# How much of a journal is read at a time.
CHUNK_BYTES = 4 * 1024 * 1024
# A journal at least this long is read on a thread at start-up.
THREAD_FROM_BYTES = 8 * 1024 * 1024
# What contains() keeps of one chunk to look across into the next.
OVERLAP_BYTES = 256

JOURNAL_NAME = re.compile(r"^Journal\..*\.log$", re.IGNORECASE)
MEGABYTE = 1024.0 * 1024.0


def newest_journal(folder):
    """(path, size) of the journal written to last, or (None, 0)."""
    try:
        names = [name for name in os.listdir(folder or "") if JOURNAL_NAME.match(name)]
    except OSError:
        return None, 0
    best = None
    for name in names:
        path = os.path.join(folder, name)
        try:
            stat = os.stat(path)
        except OSError:
            continue
        if best is None or stat.st_mtime > best[0]:
            best = (stat.st_mtime, path, stat.st_size)
    return (best[1], best[2]) if best else (None, 0)


def wants_thread(folder, least=None):
    """Whether the journal in `folder` is long enough to read on a thread."""
    least = THREAD_FROM_BYTES if least is None else least
    return newest_journal(folder)[1] >= least


def lines_of(path, chunk=None):
    """Every line of a file as bytes, without its newline, read a chunk at a
    time: a 500,000-line journal is never in memory whole. Split on b"\\n"
    only, like the journal reader."""
    chunk = max(1, int(chunk or CHUNK_BYTES))
    with open(path, "rb") as handle:
        tail = b""
        while True:
            block = handle.read(chunk)
            if not block:
                break
            lines = (tail + block).split(b"\n")
            tail = lines.pop()
            for line in lines:
                yield line
        if tail:
            yield tail


def contains(path, pattern, chunk=None):
    """Whether a file has `pattern` (bytes, or a compiled bytes pattern) in
    it anywhere, read a chunk at a time. Stops at the first sight."""
    search = pattern.search if hasattr(pattern, "search") else (lambda data: pattern in data)
    chunk = max(OVERLAP_BYTES + 1, int(chunk or CHUNK_BYTES))
    with open(path, "rb") as handle:
        kept = b""
        while True:
            block = handle.read(chunk)
            if not block:
                return False
            data = kept + block
            if search(data):
                return True
            kept = data[-OVERLAP_BYTES:]


def progress_note(read, total):
    """A few words on how far the first read has got."""
    total = max(0, int(total or 0))
    read = max(0, min(int(read or 0), total)) if total else 0
    share = int(100 * read / total) if total else 0
    return "Reading your journal from the top: %d%% (%.0f of %.0f MB)" % (
        share, read / MEGABYTE, total / MEGABYTE)


class CatchUp:
    """A reader of its own, reading the journal from the top on a thread.

    `reader` is a fresh journal reader - never the one the app is using -
    with catch_up_step(limit) -> (bytes read, size, anything read). When
    done() is true, `reader` has read everything that was there and the app's
    reader adopts it. Never raises."""

    def __init__(self, reader, chunk=None):
        self.reader = reader
        self.chunk = max(1, int(chunk or CHUNK_BYTES))
        self.read, self.total = 0, 0
        self.error = None
        self._stop = threading.Event()
        self._done = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="EDSMT journal catch-up",
                                            daemon=True)
            self._thread.start()
        return self

    def _run(self):
        try:
            while not self._stop.is_set():
                read, total, moved = self.reader.catch_up_step(self.chunk)
                self.read, self.total = int(read), int(total)
                if not moved:
                    break
        except Exception as exc:
            self.error = exc
        finally:
            self._done.set()

    def stop(self):
        """Ask the thread to finish after the chunk it is on."""
        self._stop.set()

    def done(self):
        return self._done.is_set()

    def wait(self, seconds=None):
        return self._done.wait(seconds)

    def progress(self):
        """(bytes read, the journal's size)."""
        return self.read, self.total

    def note(self):
        return progress_note(self.read, self.total)
