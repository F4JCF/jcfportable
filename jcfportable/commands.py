"""Commandes tapées dans le champ indicatif, comme dans Ham2K PoLo.

parse(text, freq_khz) -> Command ou None (None = c'est un ou plusieurs indicatifs).
"""
import re
from dataclasses import dataclass, field
from datetime import timedelta

from jcfportable.bands import MODES, band_for_freq, normalize_band

_TIME = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?$")
_DATE = re.compile(r"^(?:(\d{4})-)?(\d{1,2})-(\d{1,2})$")
_OFFSET = re.compile(r"^([+-])(\d+)([smhdw])$", re.I)
_FREQ_MHZ = re.compile(r"^\d{1,4}\.\d{1,6}$")
_FREQ_KHZ = re.compile(r"^\d{4,8}(\.\d{1,3})?$")
_PARTIAL = re.compile(r"^\.(\d{1,5})$")
_POWER = re.compile(r"^(\d{1,4}(?:\.\d+)?)W$", re.I)
_OPER = re.compile(r"^(?:OPER|OP)/([A-Z0-9/]+)$", re.I)
_SPOT = re.compile(r"^(QRV|QSY|QRT|SPOTME|SPME)(?:/(.*))?$", re.I)
CALL_RE = re.compile(r"^(?:[A-Z0-9]{1,4}/)?[A-Z0-9]{1,3}[0-9][A-Z0-9]{0,4}[A-Z](?:/[A-Z0-9]{1,4})?$")

UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


@dataclass
class Command:
    kind: str           # band, mode, freq, power, operator, time, date, offset, spot, now
    value: object = None
    extra: dict = field(default_factory=dict)
    message: str = ""


def _partial_freq(digits, freq_khz):
    """Sur 14245, « .247 » -> 14247 ; « .7 » -> 14247 (remplace les derniers chiffres)."""
    if not freq_khz:
        return None
    base = str(int(round(freq_khz)))
    if len(digits) >= len(base):
        return None
    return float(base[: len(base) - len(digits)] + digits)


def parse(text, freq_khz=None):
    raw = (text or "").strip()
    t = raw.upper()
    if not t:
        return None
    if t in ("NOW", "MAINTENANT"):
        return Command("now", message="Retour à l'heure actuelle")
    band = normalize_band(t)
    if band:
        return Command("band", band, message=f"Bande {band}")
    if t in MODES:
        return Command("mode", t, message=f"Mode {t}")
    m = _SPOT.match(raw)
    if m:
        word = m.group(1).upper()
        comment = (m.group(2) or "").strip()
        if word in ("QRV", "QSY", "QRT"):
            comment = (word + (" " + comment if comment else "")).strip()
        return Command("spot", comment, extra={"qrt": word == "QRT"}, message="Self-spot")
    m = _PARTIAL.match(t)
    if m:
        f = _partial_freq(m.group(1), freq_khz)
        if f and band_for_freq(f):
            return Command("freq", f, message=f"Fréquence {f / 1000:.3f} MHz")
        return Command("error", message="Fréquence partielle impossible sans fréquence courante")
    if _FREQ_MHZ.match(t):
        f = round(float(t) * 1000, 3)
        if band_for_freq(f):
            return Command("freq", f, message=f"Fréquence {f / 1000:.3f} MHz")
    if _FREQ_KHZ.match(t):
        f = float(t)
        if band_for_freq(f):
            return Command("freq", f, message=f"Fréquence {f / 1000:.3f} MHz")
    m = _POWER.match(t)
    if m:
        p = m.group(1)
        return Command("power", p, message=f"Puissance {p} W")
    m = _OPER.match(t)
    if m:
        return Command("operator", m.group(1).upper(), message=f"Opérateur {m.group(1).upper()}")
    m = _TIME.match(t)
    if m:
        return Command("time", (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)),
                       message=f"Heure fixée à {t} UTC")
    m = _OFFSET.match(t)
    if m:
        n = int(m.group(2)) * (1 if m.group(1) == "+" else -1)
        delta = timedelta(**{UNITS[m.group(3).lower()]: n})
        return Command("offset", delta, message=f"Décalage {t}")
    m = _DATE.match(t)
    if m:
        y = int(m.group(1)) if m.group(1) else None
        mo, d = int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return Command("date", (y, mo, d), message=f"Date fixée au {d:02d}/{mo:02d}")
    return None


def split_calls(text):
    """« F4ABC, EA3XYZ » -> ['F4ABC', 'EA3XYZ'] ; le point remplace la barre oblique."""
    out = []
    for part in (text or "").upper().split(","):
        c = part.strip().replace(".", "/").replace(" ", "")
        if c:
            out.append(c)
    return out


def looks_like_call(call):
    return bool(CALL_RE.match(call or ""))
