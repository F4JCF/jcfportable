"""Lecture et envoi des spots POTA, WWFF, SOTA, GMA, WWBOTA."""
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from jcfportable import APP_NAME, USER_AGENT
from jcfportable.bands import band_for_freq

TIMEOUT = 10
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


@dataclass
class Spot:
    program: str
    call: str
    freq: float          # kHz
    mode: str
    ref: str
    name: str
    time: datetime
    spotter: str = ""
    comment: str = ""

    @property
    def band(self):
        return band_for_freq(self.freq)

    @property
    def age_min(self):
        return (datetime.now(timezone.utc) - self.time).total_seconds() / 60


def _time(s):
    if s is None:
        return datetime.now(timezone.utc)
    if isinstance(s, (int, float)):
        return datetime.fromtimestamp(s, timezone.utc)
    s = str(s).strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:26], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s).astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _mode(m):
    m = (m or "").upper()
    if m in ("USB", "LSB"):
        return "SSB"
    return m


def fetch_pota():
    r = requests.get("https://api.pota.app/spot/activator", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for s in r.json() or []:
        out.append(Spot("POTA", (s.get("activator") or "").upper(), _num(s.get("frequency")), _mode(s.get("mode")),
                        s.get("reference") or "", s.get("name") or "", _time(s.get("spotTime")),
                        s.get("spotter") or "", s.get("comments") or ""))
    return out


def fetch_wwff():
    r = requests.get("https://spots.wwff.co/static/spots.json", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for s in r.json() or []:
        if not s:
            continue
        out.append(Spot("WWFF", (s.get("activator") or "").upper(), _num(s.get("frequency_khz")),
                        _mode(s.get("mode")), s.get("reference") or "", s.get("reference_name") or "",
                        _time(s.get("spot_time")), s.get("spotter") or "", s.get("remarks") or ""))
    return out


def fetch_sota():
    r = requests.get("https://api-db2.sota.org.uk/api/spots/-1/all/all/", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    out, seen = [], set()
    for s in r.json() or []:
        call = (s.get("activatorCallsign") or "").upper()
        if call in seen:
            continue
        seen.add(call)
        if (s.get("type") or "NORMAL") != "NORMAL":
            continue
        ref = s.get("summitCode") or ""
        if s.get("associationCode") and "/" not in ref:
            ref = f"{s['associationCode']}/{ref}"
        out.append(Spot("SOTA", call, _num(s.get("frequency")) * 1000, _mode(s.get("mode")), ref,
                        s.get("summitName") or "", _time(s.get("timeStamp")), s.get("callsign") or "",
                        s.get("comments") or ""))
    return out


def fetch_gma(api_key=""):
    """API GMA v2 : GET /api/spots/gma/ avec une clé de lecture « GMA-… » (en-tête X-API-Key)."""
    if not api_key:
        return []
    r = requests.get("https://www.gma.rocks/api/spots/gma/", timeout=TIMEOUT,
                     headers={**HEADERS, "X-API-Key": api_key})
    r.raise_for_status()
    data = r.json() or {}
    rows = (data.get("RCD") or data.get("spots") or data.get("SPOTS") or []) if isinstance(data, dict) else data
    out = []
    for s in rows or []:
        g = {k.upper(): v for k, v in s.items()}
        when = None
        d, t = str(g.get("DATE", "")), str(g.get("TIME", ""))
        try:
            if len(d) == 8 and t:
                when = datetime.strptime(d + t.replace(":", "")[:4], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
        except ValueError:
            when = None
        if when is None:
            when = _time(g.get("TIMESTAMP") or g.get("SPOT_TIME") or g.get("UTC"))
        freq = _num(g.get("QRG") or g.get("KHZ") or g.get("FREQ"))
        if 0 < freq < 1000:   # valeur en MHz
            freq *= 1000
        out.append(Spot("GMA", str(g.get("ACTIVATOR") or g.get("CALL") or "").upper(), freq,
                        _mode(g.get("MODE")), g.get("REF") or g.get("REFERENCE") or "",
                        str(g.get("NAME") or "").replace("\\", ""), when,
                        str(g.get("SPOTTER") or g.get("MYCALL") or "").upper(),
                        str(g.get("TEXT") or g.get("REMARKS") or g.get("COMMENT") or "").replace("\\", "")))
    return out


def fetch_wwbota():
    r = requests.get("https://api.wwbota.org/spots/", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for s in r.json() or []:
        if (s.get("type") or "Live") != "Live":
            continue
        refs = s.get("references") or []
        ref = " ".join(x.get("reference", "") for x in refs)
        name = refs[0].get("name", "") if len(refs) == 1 else ""
        out.append(Spot("WWBOTA", (s.get("call") or "").upper(), _num(s.get("freq")) * 1000, _mode(s.get("mode")),
                        ref, name, _time(s.get("time")), s.get("spotter") or "", s.get("comment") or ""))
    return out


FETCHERS = {"POTA": fetch_pota, "WWFF": fetch_wwff, "SOTA": fetch_sota, "GMA": fetch_gma, "WWBOTA": fetch_wwbota}


def fetch_all(programs, max_age_min=60, keys=None):
    """Retourne (spots, erreurs) ; un service en panne n'empêche pas les autres."""
    keys = keys or {}
    spots, errors = [], []
    for p in programs:
        fn = FETCHERS.get(p)
        if not fn:
            continue
        if p == "GMA" and not keys.get("gma_read"):
            continue  # la lecture des spots GMA exige une clé personnelle (Réglages > Spots)
        try:
            got = fn(keys.get("gma_read")) if p == "GMA" else fn()
            spots += [s for s in got if s.call and s.age_min <= max_age_min]
        except Exception as e:  # noqa: BLE001 — on remonte le message à l'interface
            errors.append(f"{p} : {e}")
    spots.sort(key=lambda s: s.time, reverse=True)
    return spots, errors


# ---------------------------------------------------------------------------
# Envoi de spots (self-spot ou spot d'une autre station)
# ---------------------------------------------------------------------------
def post_spot(program, activator, spotter, freq_khz, mode, ref, comment="", keys=None):
    """Envoie un spot. Retourne None si OK, sinon un message d'erreur."""
    keys = keys or {}
    mode = mode or "SSB"
    try:
        if program == "POTA":
            r = requests.post("https://api.pota.app/spot", timeout=TIMEOUT,
                              headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
                              json={"activator": activator, "spotter": spotter, "frequency": str(freq_khz),
                                    "reference": ref, "mode": mode, "source": APP_NAME, "comments": comment})
        elif program == "WWFF":
            r = requests.post("https://spots.wwff.co/api/spots/add", timeout=TIMEOUT, headers=HEADERS,
                              json={"activator": activator, "frequency_khz": freq_khz, "mode": mode,
                                    "reference": ref, "remarks": comment, "spotter": spotter})
            if r.status_code != 200 and "Duplicate" in r.text:
                return None
        elif program == "GMA":
            key = keys.get("gms_submit")
            if not key:
                return ("GMA : l'envoi de spots exige une clé GMS personnelle "
                        "(Réglages > Spots et exports)")
            r = requests.post("https://www.gma.rocks/api/spot-submit/", timeout=TIMEOUT,
                              headers={**HEADERS, "Content-Type": "application/json", "X-API-Key": key},
                              json={"SPOT": [{"MYCALL": spotter, "ACTIVATOR": activator, "REF": ref,
                                              "KHZ": f"{freq_khz:.1f}", "MODE": mode, "REMARKS": comment}]})
            if r.status_code < 300:
                try:
                    if r.json().get("ok") is False:
                        return f"GMA : spot refusé ({r.text[:200]})"
                except ValueError:
                    pass
        elif program == "WWBOTA":
            r = requests.post("https://api.wwbota.org/spots/", timeout=TIMEOUT, headers=HEADERS,
                              json={"spotter": spotter, "call": activator, "freq": freq_khz / 1000, "mode": mode,
                                    "comment": f"{ref} {comment}".strip(),
                                    "type": "QRT" if "QRT" in comment.upper() else "Live"})
        elif program == "SOTA":
            return ("Le spot SOTA demande une connexion à un compte SOTA (SSO), pas encore gérée : "
                    "utilisez SOTAwatch ou l'appli SOTA Spotter.")
        else:
            return f"Programme {program} non géré"
    except requests.RequestException as e:
        return f"{program} : réseau indisponible ({e})"
    if r.status_code >= 300:
        return f"{program} : le serveur a répondu {r.status_code} {r.text[:200]}"
    return None
