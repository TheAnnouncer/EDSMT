"""
Proximity sonar (1.10040, #153): tones, never words.

While the Rhino has a target - the deposit the scope and the compass point
at - a short tone repeats faster and higher as the distance falls: every
two seconds at 1,500 m and beyond, down to five a second inside 25 m, and
nothing at all past 2,000 m. Between the two the steps are even on a
logarithmic scale, so the last hundred metres change as much as the first
thousand - the part of the drive where it matters.

The tones are played on Windows with winsound.Beep in a worker thread of
their own, so the window never waits for a tone. Anywhere else nothing is
played. The player takes whatever plays a tone as an argument, so the
checks hand it a recorder.

The curve is plain arithmetic and needs no window.
"""

import math
import os
import threading
import time

# Nothing beyond this: the Rhino's scanner does not reach further.
FAR_M = 2000.0
# The slowest repeat, from here out to FAR_M.
SLOW_M = 1500.0
# The quickest, from here in.
NEAR_M = 25.0
SLOWEST_S = 2.0
FASTEST_S = 0.2
# Low and far, high and near. winsound.Beep takes 37 to 32,767 Hz.
LOW_HZ = 440
HIGH_HZ = 1320
# One short tone. Shorter than the quickest repeat, so tones never run on.
TONE_MS = 60
# How often the worker looks again while it has nothing to play, so a
# target coming into range is heard within this.
IDLE_S = 0.5


def _nearness(metres):
    """0.0 at SLOW_M and beyond, 1.0 at NEAR_M and inside, even steps on a
    logarithmic scale between - or None past FAR_M or for no distance."""
    try:
        value = float(metres)
    except (TypeError, ValueError):
        return None
    if value != value or value < 0 or value > FAR_M:
        return None
    if value <= NEAR_M:
        return 1.0
    if value >= SLOW_M:
        return 0.0
    return math.log(SLOW_M / value) / math.log(SLOW_M / NEAR_M)


def interval_s(metres):
    """Seconds from one tone to the next at this distance, or None for no
    tone at all: 2.0 at 1,500 m, 0.2 inside 25 m, None past 2,000 m."""
    near = _nearness(metres)
    if near is None:
        return None
    return SLOWEST_S * (FASTEST_S / SLOWEST_S) ** near


def pitch_hz(metres):
    """The tone's pitch at this distance, whole hertz, or None."""
    near = _nearness(metres)
    if near is None:
        return None
    return int(round(LOW_HZ * (float(HIGH_HZ) / LOW_HZ) ** near))


def tone(metres):
    """(hertz, milliseconds, seconds to the next) for this distance, or
    None when nothing is played."""
    every = interval_s(metres)
    if every is None:
        return None
    return pitch_hz(metres), TONE_MS, every


def windows_beep():
    """winsound.Beep on Windows, None anywhere else."""
    if os.name != "nt":
        return None
    try:
        import winsound
    except ImportError:
        return None
    return winsound.Beep


class Sonar:
    """The player. `follow(metres)` says how far the target is now; None is
    no target. The tones run on a daemon thread started with the first one,
    and `close()` ends it. `beep(hertz, milliseconds)` plays one tone: the
    default is Windows' own, and without one nothing is ever started."""

    def __init__(self, beep=None, clock=time.monotonic):
        self.beep = beep if beep is not None else windows_beep()
        self.clock = clock
        self.metres = None
        self.played = 0
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._last = None

    @property
    def running(self):
        thread = self._thread
        return thread is not None and thread.is_alive()

    def follow(self, metres):
        """The target's distance, or None. Never raises; never waits."""
        self.metres = metres
        if tone(metres) is None or self.beep is None or self._stop.is_set():
            return False
        if not self.running:
            self._thread = threading.Thread(target=self._run, name="EDSMT sonar",
                                            daemon=True)
            self._thread.start()
        self._wake.set()
        return True

    def close(self):
        """Stop the tones and the thread."""
        self.metres = None
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def _run(self):
        while not self._stop.is_set():
            found = tone(self.metres)
            if found is None:
                self._last = None
                self._wake.wait(IDLE_S)
                self._wake.clear()
                continue
            hertz, millis, every = found
            now = self.clock()
            due = now if self._last is None else self._last + every
            if now + 0.001 < due:
                # Woken early by a new distance, the wait is worked out
                # again from it: nearer, the next tone comes sooner.
                self._wake.wait(min(due - now, IDLE_S))
                self._wake.clear()
                continue
            self._last = now
            try:
                self.beep(hertz, millis)
                self.played += 1
            except Exception:
                # A sound device that refuses a tone is not worth a fault
                # in the window; the next one is tried as usual.
                pass
