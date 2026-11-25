"""Bandes, modes et utilitaires de fréquence (fréquences en kHz)."""

# (nom, début kHz, fin kHz, fréquence par défaut kHz)
BANDS = [
    ("160m", 1800, 2000, 1840),
    ("80m", 3500, 4000, 3650),
    ("60m", 5060, 5450, 5355),
    ("40m", 7000, 7300, 7150),
    ("30m", 10100, 10150, 10120),
    ("20m", 14000, 14350, 14250),
    ("17m", 18068, 18168, 18130),
    ("15m", 21000, 21450, 21250),
    ("12m", 24890, 24990, 24940),
    ("10m", 28000, 29700, 28400),
    ("6m", 50000, 54000, 50150),
    ("4m", 70000, 71000, 70200),
    ("2m", 144000, 148000, 144300),
    ("70cm", 420000, 450000, 432200),
    ("23cm", 1240000, 1300000, 1296200),
]
BAND_NAMES = [b[0] for b in BANDS]

MODES = ["SSB", "CW", "FM", "AM", "FT8", "FT4", "RTTY", "PSK31", "JS8", "SSTV", "DATA"]

# Correspondance mode -> (MODE ADIF, SUBMODE ADIF)
ADIF_MODES = {
    "SSB": ("SSB", None),
    "CW": ("CW", None),
    "FM": ("FM", None),
    "AM": ("AM", None),
    "FT8": ("FT8", None),
    "FT4": ("MFSK", "FT4"),
    "RTTY": ("RTTY", None),
    "PSK31": ("PSK", "PSK31"),
    "JS8": ("MFSK", "JS8"),
    "SSTV": ("SSTV", None),
    "DATA": ("DATA", None),
}

DIGITAL_MODES = {"FT8", "FT4", "RTTY", "PSK31", "JS8", "DATA"}


def band_for_freq(khz):
    if not khz:
        return None
    for name, lo, hi, _ in BANDS:
        if lo <= khz <= hi:
            return name
    return None


def default_freq_for_band(band):
    for name, _, _, default in BANDS:
        if name == band:
            return default
    return None


def default_rst(mode):
    if mode in ("CW", "RTTY", "PSK31"):
        return "599"
    if mode in ("FT8", "FT4", "JS8"):
        return "-10"
    return "59"


def fmt_freq(khz):
    """14250.0 -> '14.250.0' style PoLo (MHz.kHz)."""
    if not khz:
        return "—"
    mhz = int(khz // 1000)
    rest = khz - mhz * 1000
    if abs(rest - round(rest)) < 1e-6:
        return f"{mhz}.{int(round(rest)):03d}"
    return f"{mhz}.{rest:07.3f}".rstrip("0").rstrip(".")


def normalize_band(text):
    t = text.strip().lower()
    for name in BAND_NAMES:
        if t == name.lower():
            return name
    return None
