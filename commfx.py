"""Comm sound for a recorded line, by where the commander is (1.10040).

A voice with comms - Celestia - is recorded clean, once. Before a line is
played this gives it the sound of the link it comes over:

    ship   the cockpit's comms: a clean link, gently band-limited, a little
           compression, a faint carrier hiss, a tone at key-up and key-off
    srv    the Rhino's short-range set: narrower, grittier, more hiss, a
           chirp in and a burst of static out
    foot   the suit radio inside a helmet: close and a little boxy, soft
           hiss, a light click each end

The result is written once to a cache folder and played from there; the
same line in the same place is never worked out twice. Plain Python, the
wave module and nothing else, so it runs wherever EDSMT runs and adds
nothing to the download. Every step is a pure function of the samples, so
the checks can measure what it does without a sound card.
"""
import hashlib
import math
import os
import random
import struct
import wave

VERSION = 1
PLACES = ("ship", "srv", "foot")
OUT_RATE = 22050
# Silence before the voice (the key-up tone sits in it) and after it (the
# key-off tone and the tail).
PRE_S = 0.14
POST_S = 0.22
# Where the finished line sits: its loudness (RMS) and the most any sample
# may reach.
TARGET_RMS_DB = -20.0
PEAK_DB = -1.5

# Each place: the voice's band, its compressor, how it is driven, what it
# adds, and the tones either end.
PRESETS = {
    "ship": {"hp": 220.0, "lp": 4800.0, "comp": (-20.0, 3.0, 0.005, 0.080),
             "clip": ("tanh", 0.85), "crush": None, "echo": None, "peak": None,
             "gain": 1.10,
             "noise": ("pink", 0.006, None, None),
             "tone_in": ("sine", 2525.0, 0.12, 0.10),
             "tone_out": ("sine", 2475.0, 0.12, 0.08)},
    "srv": {"hp": 380.0, "lp": 3100.0, "comp": (-24.0, 5.0, 0.003, 0.060),
            "clip": ("atan", 0.60), "crush": (10, 0.25), "echo": None, "peak": None,
            "gain": 1.25,
            "noise": ("white", 0.018, 1200.0, 6000.0),
            "tone_in": ("sine", 1800.0, 0.07, 0.12),
            "tone_out": ("burst", 2500.0, 0.16, 0.12)},
    "foot": {"hp": 200.0, "lp": 5200.0, "comp": (-22.0, 3.0, 0.005, 0.090),
             "clip": None, "crush": None,
             "echo": (0.8, 0.35, ((0.004, 0.25), (0.009, 0.15))),
             "peak": (1200.0, 1.2, 3.0), "gain": 1.05,
             "noise": ("pink", 0.008, None, 3500.0),
             "tone_in": ("sine", 3200.0, 0.04, 0.10),
             "tone_out": ("sine", 2600.0, 0.05, 0.08)},
}


def clean_place(place):
    text = str(place or "").strip().lower()
    return text if text in PLACES else "ship"


# -- reading and writing -------------------------------------------------------

def read_wav(path):
    """(samples as floats from -1 to 1, mono, and the sample rate). 16-bit
    PCM only - what the recordings are; stereo is folded to mono."""
    with wave.open(path, "rb") as handle:
        channels, width, rate = handle.getnchannels(), handle.getsampwidth(), handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if width != 2:
        raise ValueError("only 16-bit PCM is read")
    count = len(frames) // 2
    values = struct.unpack("<%dh" % count, frames[:count * 2])
    if channels > 1:
        values = [sum(values[i:i + channels]) / channels for i in range(0, len(values), channels)]
    return [v / 32768.0 for v in values], rate


def write_wav(path, samples, rate=OUT_RATE):
    """Mono 16-bit PCM, written to a temporary name and moved into place."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = struct.pack("<%dh" % len(samples),
                       *(max(-32768, min(32767, int(round(s * 32767.0)))) for s in samples))
    temp = path + ".tmp"
    with wave.open(temp, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(int(rate))
        handle.writeframes(data)
    os.replace(temp, path)
    return path


# -- the parts -----------------------------------------------------------------

def resample(samples, rate, to=OUT_RATE):
    """Linear resampling; fine for speech going into a comm band."""
    if not samples or rate == to:
        return list(samples)
    step = float(rate) / float(to)
    out, last = [], len(samples) - 1
    position = 0.0
    while position <= last:
        i = int(position)
        frac = position - i
        nxt = samples[i + 1] if i < last else samples[i]
        out.append(samples[i] + (nxt - samples[i]) * frac)
        position += step
    return out


def _biquad(samples, b0, b1, b2, a0, a1, a2):
    b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
    out = [0.0] * len(samples)
    x1 = x2 = y1 = y2 = 0.0
    for i, x in enumerate(samples):
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, x, y1, y
        out[i] = y
    return out


def highpass(samples, freq, rate, q=0.7071):
    w = 2.0 * math.pi * min(freq, rate * 0.45) / rate
    alpha, cos = math.sin(w) / (2.0 * q), math.cos(w)
    return _biquad(samples, (1 + cos) / 2, -(1 + cos), (1 + cos) / 2, 1 + alpha, -2 * cos, 1 - alpha)


def lowpass(samples, freq, rate, q=0.7071):
    w = 2.0 * math.pi * min(freq, rate * 0.45) / rate
    alpha, cos = math.sin(w) / (2.0 * q), math.cos(w)
    return _biquad(samples, (1 - cos) / 2, 1 - cos, (1 - cos) / 2, 1 + alpha, -2 * cos, 1 - alpha)


def peaking(samples, freq, q, gain_db, rate):
    a = 10.0 ** (gain_db / 40.0)
    w = 2.0 * math.pi * min(freq, rate * 0.45) / rate
    alpha, cos = math.sin(w) / (2.0 * q), math.cos(w)
    return _biquad(samples, 1 + alpha * a, -2 * cos, 1 - alpha * a,
                   1 + alpha / a, -2 * cos, 1 - alpha / a)


def compress(samples, threshold_db, ratio, attack_s, release_s, rate):
    """A plain feed-forward compressor on the peak envelope."""
    threshold = 10.0 ** (threshold_db / 20.0)
    attack = math.exp(-1.0 / max(1.0, attack_s * rate))
    release = math.exp(-1.0 / max(1.0, release_s * rate))
    env, out = 0.0, [0.0] * len(samples)
    for i, x in enumerate(samples):
        level = abs(x)
        coeff = attack if level > env else release
        env = coeff * env + (1.0 - coeff) * level
        if env > threshold:
            gain = (threshold * (env / threshold) ** (1.0 / ratio)) / env
        else:
            gain = 1.0
        out[i] = x * gain
    return out


def softclip(samples, kind, threshold):
    if kind == "atan":
        scale = threshold / (math.pi / 2.0)
        return [scale * math.atan(x / scale) for x in samples]
    return [threshold * math.tanh(x / threshold) for x in samples]


def crush(samples, bits, mix):
    levels = float(2 ** (int(bits) - 1))
    return [(1.0 - mix) * x + mix * (round(x * levels) / levels) for x in samples]


def echo(samples, rate, in_gain, out_gain, taps):
    out = [0.0] * len(samples)
    delays = [(max(1, int(d * rate)), decay) for d, decay in taps]
    for i, x in enumerate(samples):
        wet = x * in_gain
        for d, decay in delays:
            if i >= d:
                wet += samples[i - d] * in_gain * decay
        out[i] = wet * out_gain
    return out


def noise(length, kind, amplitude, rng):
    """White, or pink (Paul Kellet's filter on white), at an amplitude."""
    out = [0.0] * length
    if kind == "pink":
        b0 = b1 = b2 = b3 = b4 = b5 = b6 = 0.0
        for i in range(length):
            w = rng.uniform(-1.0, 1.0)
            b0 = 0.99886 * b0 + w * 0.0555179
            b1 = 0.99332 * b1 + w * 0.0750759
            b2 = 0.96900 * b2 + w * 0.1538520
            b3 = 0.86650 * b3 + w * 0.3104856
            b4 = 0.55000 * b4 + w * 0.5329522
            b5 = -0.7616 * b5 - w * 0.0168980
            out[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362) * 0.11 * amplitude
            b6 = w * 0.115926
    else:
        for i in range(length):
            out[i] = rng.uniform(-1.0, 1.0) * amplitude
    return out


def tone(kind, freq, seconds, volume, rate, rng):
    """A key-up or key-off sound, with a 20 ms fade at its end."""
    count = max(1, int(seconds * rate))
    if kind == "burst":
        raw = noise(count, "white", volume, rng)
        raw = lowpass(highpass(raw, freq * 0.5, rate), min(freq * 1.5, rate * 0.45), rate)
        fade_from = int(0.04 * rate)
        return [v * (1.0 if i < fade_from else max(0.0, 1.0 - (i - fade_from) / max(1, count - fade_from)))
                for i, v in enumerate(raw)]
    fade = max(1, int(0.02 * rate))
    return [volume * math.sin(2.0 * math.pi * freq * i / rate)
            * (1.0 if i < count - fade else (count - i) / fade) for i in range(count)]


def level(samples):
    """(RMS, peak) of the samples, as plain amplitudes."""
    if not samples:
        return 0.0, 0.0
    total = sum(s * s for s in samples)
    return math.sqrt(total / len(samples)), max(abs(s) for s in samples)


def normalise(samples, rms_db=TARGET_RMS_DB, peak_db=PEAK_DB):
    """Brought to the target loudness, the few peaks above the ceiling
    rounded off rather than the whole line turned down for them."""
    rms, _peak = level(samples)
    if rms <= 0.0:
        return list(samples)
    gain = (10.0 ** (rms_db / 20.0)) / rms
    ceiling = 10.0 ** (peak_db / 20.0)
    knee = ceiling * 0.7
    out = []
    for s in samples:
        v = s * gain
        a = abs(v)
        if a > knee:
            a = knee + (ceiling - knee) * math.tanh((a - knee) / (ceiling - knee))
            v = a if v > 0 else -a
        out.append(v)
    return out


# -- the whole of it -------------------------------------------------------------

def apply(samples, rate, place, seed=0):
    """The voice, in the place's comms, at OUT_RATE: key-up tone, voice,
    key-off tone, all over the link's noise, then levelled."""
    preset = PRESETS[clean_place(place)]
    rng = random.Random(seed)
    voice = resample(samples, rate, OUT_RATE)
    rate = OUT_RATE
    voice = lowpass(highpass(voice, preset["hp"], rate), preset["lp"], rate)
    if preset["peak"]:
        voice = peaking(voice, preset["peak"][0], preset["peak"][1], preset["peak"][2], rate)
    if preset["echo"]:
        voice = echo(voice, rate, *preset["echo"])
    voice = compress(voice, *preset["comp"], rate=rate)
    if preset["clip"]:
        voice = softclip(voice, *preset["clip"])
    if preset["crush"]:
        voice = crush(voice, *preset["crush"])
    voice = [v * preset["gain"] for v in voice]
    pre, post = int(PRE_S * rate), int(POST_S * rate)
    total = pre + len(voice) + post
    mix = [0.0] * total
    for i, v in enumerate(tone(*preset["tone_in"], rate=rate, rng=rng)):
        if i < total:
            mix[i] += v
    for i, v in enumerate(voice):
        mix[pre + i] += v
    start = pre + len(voice) + int(0.04 * rate)
    for i, v in enumerate(tone(*preset["tone_out"], rate=rate, rng=rng)):
        if start + i < total:
            mix[start + i] += v
    kind, amplitude, low, high = preset["noise"]
    bed = noise(total, kind, amplitude, rng)
    if low:
        bed = highpass(bed, low, rate)
    if high:
        bed = lowpass(bed, high, rate)
    mix = [m + b for m, b in zip(mix, bed)]
    return normalise(mix)


def cache_name(source, place):
    """The cached file's name for this recording in this place: changes when
    the recording or this module's sound does."""
    try:
        stat = os.stat(source)
        stamp = "%s|%d|%d" % (os.path.abspath(source), int(stat.st_mtime), stat.st_size)
    except OSError:
        stamp = os.path.abspath(source)
    digest = hashlib.sha1(("%s|%s|%d" % (stamp, clean_place(place), VERSION)).encode("utf-8")).hexdigest()[:12]
    base = os.path.splitext(os.path.basename(source))[0]
    return "%s.%s.%s.wav" % (base, clean_place(place), digest)


def cached(source, place, cache_dir):
    """The recording with the place's comm sound: from the cache when it is
    there, else worked out and kept. The plain recording if anything goes
    wrong - a line is never lost to its effect."""
    if not source or not cache_dir:
        return source
    target = os.path.join(cache_dir, clean_place(place), cache_name(source, place))
    if os.path.isfile(target):
        return target
    try:
        samples, rate = read_wav(source)
        seed = int(hashlib.sha1(os.path.basename(source).encode("utf-8")).hexdigest()[:8], 16)
        return write_wav(target, apply(samples, rate, place, seed=seed))
    except (OSError, ValueError, EOFError, wave.Error, struct.error):
        return source
