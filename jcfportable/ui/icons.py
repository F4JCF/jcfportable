"""Icônes vectorielles du thème (style maquette : bleu lumineux dégradé), drapeaux et illustrations."""
import json
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parent.parent / "assets"

_DEFS = """<defs>
<linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9fdcff"/>
<stop offset="0.55" stop-color="#3a9df2"/><stop offset="1" stop-color="#1667c9"/></linearGradient>
<linearGradient id="w" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/>
<stop offset="1" stop-color="#cfe6ff"/></linearGradient>
<linearGradient id="o" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd27a"/>
<stop offset="1" stop-color="#ff8a00"/></linearGradient>
<linearGradient id="v" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9dff7a"/>
<stop offset="1" stop-color="#22b52b"/></linearGradient></defs>"""

_GEAR_TEETH = "".join(
    f'<rect x="21" y="2" width="6" height="10" rx="1.5" fill="url(#g)" transform="rotate({a} 24 24)"/>'
    for a in range(0, 360, 45))

SVG = {
    "home": '<path d="M24 5 L44 23 L38 23 L38 43 L28 43 L28 31 L20 31 L20 43 L10 43 L10 23 L4 23 Z" '
            'fill="url(#g)" stroke="#d9f0ff" stroke-width="1.5" stroke-linejoin="round"/>',
    "folder": '<path d="M4 12 Q4 9 7 9 L18 9 L22 13 L41 13 Q44 13 44 16 L44 20 L4 20 Z" fill="#2d86df"/>'
              '<path d="M4 18 L44 18 L44 39 Q44 42 41 42 L7 42 Q4 42 4 39 Z" fill="url(#g)" '
              'stroke="#d9f0ff" stroke-width="1.2"/>',
    "trash": '<rect x="9" y="9" width="30" height="5" rx="2" fill="url(#w)"/>'
             '<rect x="19" y="4" width="10" height="5" rx="2" fill="url(#w)"/>'
             '<path d="M12 16 L36 16 L33.5 44 L14.5 44 Z" fill="url(#w)"/>'
             '<path d="M19 20 L19.8 40 M24 20 L24 40 M29 20 L28.2 40" stroke="#5a7fa6" stroke-width="2.2" '
             'stroke-linecap="round"/>',
    "export": '<rect x="3" y="6" width="38" height="27" rx="3" fill="url(#g)" stroke="#d9f0ff" stroke-width="1.4"/>'
              '<rect x="7" y="10" width="30" height="19" fill="#0b3463"/><rect x="15" y="34" width="14" height="4" '
              'fill="#5fb4ff"/><rect x="11" y="38" width="22" height="3" rx="1.5" fill="#9fdcff"/>'
              '<path d="M26 30 L40 30 L40 25 L47 33 L40 41 L40 36 L26 36 Z" fill="url(#w)" stroke="#1667c9" '
              'stroke-width="1"/>',
    "database": ''.join(
        f'<path d="M8 {y} Q8 {y - 5} 24 {y - 5} Q40 {y - 5} 40 {y} L40 {y + 8} Q40 {y + 13} 24 {y + 13} '
        f'Q8 {y + 13} 8 {y + 8} Z" fill="url(#g)" stroke="#d9f0ff" stroke-width="1.2"/>'
        for y in (33, 22, 11)) + '<ellipse cx="24" cy="11" rx="16" ry="5" fill="#bde6ff"/>',
    "chart": '<rect x="6" y="24" width="9" height="19" rx="1.5" fill="url(#g)"/>'
             '<rect x="19.5" y="8" width="9" height="35" rx="1.5" fill="url(#g)"/>'
             '<rect x="33" y="16" width="9" height="27" rx="1.5" fill="url(#g)"/>',
    "gear": _GEAR_TEETH + '<circle cx="24" cy="24" r="15" fill="url(#g)" stroke="#d9f0ff" stroke-width="1.2"/>'
            '<circle cx="24" cy="24" r="6" fill="#0b2c52"/>',
    "help": '<path d="M14 15 Q14 5 24 5 Q35 5 35 14 Q35 20 28 24 Q26 25.5 26 29 L26 31 L20 31 L20 28 '
            'Q20 22 25 19.5 Q29 17.5 29 14.5 Q29 10.5 24 10.5 Q19.5 10.5 19.5 15 Z" fill="url(#g)" '
            'stroke="#d9f0ff" stroke-width="1.2"/><circle cx="23" cy="39" r="4" fill="url(#g)"/>',
    "calendar": '<rect x="5" y="9" width="38" height="34" rx="4" fill="none" stroke="url(#g)" stroke-width="3.5"/>'
                '<rect x="5" y="9" width="38" height="9" rx="3" fill="url(#g)"/>'
                '<rect x="13" y="4" width="4" height="9" rx="2" fill="#d9f0ff"/>'
                '<rect x="31" y="4" width="4" height="9" rx="2" fill="#d9f0ff"/>'
                + "".join(f'<rect x="{x}" y="{y}" width="5" height="4.5" rx="1" fill="#7cc4ff"/>'
                          for y in (23, 31) for x in (12, 21.5, 31)),
    "clock": '<circle cx="24" cy="24" r="18" fill="none" stroke="url(#g)" stroke-width="4"/>'
             '<path d="M24 13 L24 25 L32 29" fill="none" stroke="#d9f0ff" stroke-width="3.5" '
             'stroke-linecap="round" stroke-linejoin="round"/>',
    "signal": '<rect x="4" y="32" width="7" height="11" rx="1" fill="url(#v)"/>'
              '<rect x="14" y="24" width="7" height="19" rx="1" fill="url(#v)"/>'
              '<rect x="24" y="15" width="7" height="28" rx="1" fill="url(#v)"/>'
              '<rect x="34" y="6" width="7" height="37" rx="1" fill="url(#v)"/>',
    "pulse": '<path d="M2 26 L13 26 L18 14 L25 38 L31 20 L35 26 L46 26" fill="none" stroke="#3b1d00" '
             'stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>',
    "pulse_light": '<path d="M2 26 L13 26 L18 14 L25 38 L31 20 L35 26 L46 26" fill="none" stroke="url(#g)" '
                   'stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>',
    "pin": '<path d="M24 44 Q10 28 10 19 Q10 5 24 5 Q38 5 38 19 Q38 28 24 44 Z" fill="url(#w)"/>'
           '<circle cx="24" cy="19" r="6" fill="#1667c9"/>',
    "bars": '<rect x="7" y="22" width="9" height="20" fill="url(#w)"/><rect x="19.5" y="10" width="9" '
            'height="32" fill="url(#w)"/><rect x="32" y="16" width="9" height="26" fill="url(#w)"/>',
    "pie": '<path d="M22 8 A17 17 0 1 0 40 26 L22 26 Z" fill="url(#w)"/>'
           '<path d="M26 4 A18 18 0 0 1 44 22 L26 22 Z" fill="url(#w)"/>',
    "operators": '<circle cx="24" cy="24" r="20" fill="none" stroke="url(#w)" stroke-width="3"/>'
                 '<circle cx="24" cy="18" r="6" fill="url(#w)"/><path d="M13 35 Q13 26 24 26 Q35 26 35 35 Z" '
                 'fill="url(#w)"/><circle cx="12" cy="20" r="4" fill="#cfe6ff"/><circle cx="36" cy="20" r="4" '
                 'fill="#cfe6ff"/>',
    "edit": '<rect x="4" y="9" width="30" height="34" rx="4" fill="none" stroke="#ffffff" stroke-width="3.5"/>'
            '<path d="M22 31 L24 23 L40 7 L46 13 L30 29 Z" fill="#ffffff"/>',
    "dot_green": '<circle cx="24" cy="24" r="16" fill="url(#v)" stroke="#d6ffd0" stroke-width="2"/>',
    "dot_red": '<circle cx="24" cy="24" r="16" fill="#e74c3c" stroke="#ffd0c8" stroke-width="2"/>',
    "dot_grey": '<circle cx="24" cy="24" r="16" fill="#7f93a8" stroke="#c9d6e3" stroke-width="2"/>',
    "antenna": '<path d="M24 14 L15 44 M24 14 L33 44 M18 34 L30 34 M20 26 L28 26" stroke="url(#g)" '
               'stroke-width="3" fill="none" stroke-linecap="round"/><circle cx="24" cy="12" r="3.5" fill="#d9f0ff"/>'
               '<path d="M14 6 Q10 12 14 18 M34 6 Q38 12 34 18 M9 3 Q3 12 9 21 M39 3 Q45 12 39 21" '
               'stroke="#7cc4ff" stroke-width="2.5" fill="none" stroke-linecap="round"/>',
}


@lru_cache(maxsize=256)
def pixmap(name, size=32, w=None):
    """Rend l'icône SVG à la taille voulue (pixmap carré sauf largeur w)."""
    width = w or size
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">{_DEFS}{SVG[name]}</svg>'
    r = QSvgRenderer(QByteArray(svg.encode()))
    ratio = 2  # netteté sur écrans haute densité
    img = QImage(width * ratio, size * ratio, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p, QRectF(0, 0, width * ratio, size * ratio))
    p.end()
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(ratio)
    return pm


def icon(name, size=32):
    return QIcon(pixmap(name, size))


def asset(name):
    return QPixmap(str(ASSETS / name))


@lru_cache(maxsize=1)
def _countries():
    try:
        return json.loads((ASSETS / "flags" / "countries.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=512)
def flag(country):
    """Drapeau (QPixmap) d'après le nom de pays renvoyé par QRZ/HamQTH, ou None."""
    if not country:
        return None
    c = country.strip().lower()
    m = _countries()
    code = m.get(c)
    if not code:
        for name, cc in m.items():
            if c.startswith(name) or name.startswith(c):
                code = cc
                break
    if not code:
        return None
    path = ASSETS / "flags" / f"{code}.png"
    return QPixmap(str(path)) if path.exists() else None
