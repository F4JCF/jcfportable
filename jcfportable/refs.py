"""Programmes « On The Air » : listes de références hors ligne et saisie abrégée."""
import csv
import io
import json
import re

import requests

from jcfportable import USER_AGENT
from jcfportable.geo import latlon_to_grid

# Seuils de validation d'une activation (nombre de QSO)
PROGRAMS = {
    "POTA": {
        "label": "POTA — Parks On The Air",
        "url": "https://pota.app/all_parks_ext.csv",
        "skip_lines": 0,
        "threshold": 10,
        "kind": "Parc",
        "example": "FR-0123",
    },
    "WWFF": {
        "label": "WWFF — World Wide Flora & Fauna",
        "url": "https://wwff.co/wwff-data/wwff_directory.csv",
        "skip_lines": 0,
        "threshold": 44,
        "kind": "Parc",
        "example": "FFF-0123",
    },
    "SOTA": {
        "label": "SOTA — Summits On The Air",
        "url": "https://www.sotadata.org.uk/summitslist.csv",
        "skip_lines": 1,
        "threshold": 4,
        "kind": "Sommet",
        "example": "F/AM-468",
    },
    "GMA": {
        "label": "GMA — Global Mountain Activity",
        "url": "https://www.cqgma.org/download/summits.csv",
        "skip_lines": 1,
        "threshold": 4,
        "kind": "Référence",
        "example": "F/AM-468",
    },
    "WWBOTA": {
        "label": "WWBOTA — World Wide Bunkers On The Air",
        "url": "https://api.wwbota.org/bunkers/?format=CSV",
        "skip_lines": 0,
        "threshold": 10,
        "kind": "Bunker",
        "example": "B/F-0001",
    },
}
PROGRAM_KEYS = list(PROGRAMS.keys())


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _grid(row_grid, lat, lon):
    if row_grid:
        g = row_grid.strip()
        if len(g) >= 6:
            return g[:4].upper() + g[4:6].lower() + g[6:]
        return g.upper()
    if lat is not None and lon is not None and (lat or lon):
        return latlon_to_grid(lat, lon)
    return ""


def _valid_sota(valid_to):
    """ValidTo au format JJ/MM/AAAA ; on garde les sommets encore valides."""
    from datetime import date
    try:
        d, m, y = valid_to.split("/")
        return date(int(y), int(m), int(d)) >= date.today()
    except (ValueError, AttributeError):
        return True


def parse_rows(program, text):
    """Analyse le CSV téléchargé et produit (ref, name, grid, lat, lon, extra_json)."""
    info = PROGRAMS[program]
    lines = text.lstrip("﻿").splitlines()
    lines = lines[info["skip_lines"]:]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    reader.fieldnames = [(h or "").strip().lstrip("﻿") for h in (reader.fieldnames or [])]
    for row in reader:
        if program == "POTA":
            ref = (row.get("reference") or "").strip()
            if not ref or row.get("active", "1") not in ("1", "true", "True"):
                continue
            lat, lon = _f(row.get("latitude")), _f(row.get("longitude"))
            yield ref, row.get("name", ""), _grid(row.get("grid"), lat, lon), lat, lon, json.dumps(
                {"location": row.get("locationDesc", "")})
        elif program == "WWFF":
            ref = (row.get("reference") or "").strip().upper()
            if not ref or row.get("status", "active") != "active":
                continue
            lat, lon = _f(row.get("latitude")), _f(row.get("longitude"))
            yield ref, row.get("name", ""), _grid(row.get("iaruLocator"), lat, lon), lat, lon, json.dumps(
                {"program": row.get("program", "")})
        elif program == "SOTA":
            ref = (row.get("SummitCode") or "").strip().upper()
            if not ref or not _valid_sota(row.get("ValidTo")):
                continue
            lat, lon = _f(row.get("Latitude")), _f(row.get("Longitude"))
            yield ref, row.get("SummitName", ""), _grid("", lat, lon), lat, lon, json.dumps(
                {"alt": row.get("AltM"), "points": row.get("Points"), "region": row.get("RegionName")})
        elif program == "GMA":
            ref = (row.get("Reference") or "").strip().upper()
            if not ref:
                continue
            lat, lon = _f(row.get("Latitude")), _f(row.get("Longitude"))
            yield ref, row.get("Name", ""), _grid(row.get("Maidenhead Locator"), lat, lon), lat, lon, json.dumps(
                {"alt": row.get("Height (m)")})
        elif program == "WWBOTA":
            ref = (row.get("Reference") or "").strip().upper()
            if not ref:
                continue
            lat, lon = _f(row.get("Lat")), _f(row.get("Long"))
            yield ref, row.get("Name", ""), _grid(row.get("Maidenhead") or row.get("Locator"), lat, lon), lat, lon, \
                json.dumps({})


def download_program(db, program, progress=None):
    """Télécharge la liste d'un programme et la range dans la base. Retourne le nombre de références."""
    url = PROGRAMS[program]["url"]
    if progress:
        progress(0, f"Téléchargement {program}…")
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=120, stream=True)
    resp.raise_for_status()
    chunks = []
    total = int(resp.headers.get("Content-Length") or 0)
    got = 0
    for chunk in resp.iter_content(262144):
        chunks.append(chunk)
        got += len(chunk)
        if progress:
            pct = int(got * 80 / total) if total else min(79, got // 400000)
            progress(pct, f"{program} : {got // 1024} Ko reçus")
    raw = b"".join(chunks)
    text = raw.decode("utf-8", errors="replace")
    if progress:
        progress(85, f"{program} : enregistrement…")
    n = db.replace_refs(program, parse_rows(program, text))
    if n == 0:
        raise RuntimeError(f"Aucune référence {program} trouvée dans le fichier téléchargé")
    from jcfportable.db import iso, now_utc
    db.set_meta(f"refs_updated_{program}", iso(now_utc()))
    if progress:
        progress(100, f"{program} : {n} références")
    return n


# ---------------------------------------------------------------------------
# Saisie abrégée des références (comme PoLo) : « 2518 », « FR123 », « FAM468 »…
# ---------------------------------------------------------------------------
_DIGITS = re.compile(r"^\d{1,6}$")
_PREFIX_DIGITS = re.compile(r"^([A-Z0-9]{1,4}?)[-]?(\d{1,6})$")


def expand_ref(db, program, text, default_prefix=""):
    """Transforme une saisie courte en référence complète. Retourne (ref, info) ou (texte_normalisé, None)."""
    t = (text or "").strip().upper().replace(" ", "")
    if not t:
        return "", None
    hit = db.find_ref(program, t)
    if hit:
        return hit["ref"], hit
    if _DIGITS.match(t) and default_prefix:
        cands = db.refs_with_number(program, default_prefix.upper(), int(t))
        if cands:
            return cands[0]["ref"], cands[0]
        # base non téléchargée : on construit quand même la référence
        width = 4 if program in ("POTA", "WWFF", "WWBOTA") else 3
        return f"{default_prefix.upper()}-{int(t):0{width}d}", None
    m = _PREFIX_DIGITS.match(t)
    if m and program in ("POTA", "WWFF"):
        cands = db.refs_with_number(program, m.group(1), int(m.group(2)))
        if cands:
            return cands[0]["ref"], cands[0]
    return t, None


def ref_label(db, program, ref):
    hit = db.find_ref(program, ref)
    if hit and hit.get("name"):
        return f"{hit['ref']} — {hit['name']}"
    return ref
