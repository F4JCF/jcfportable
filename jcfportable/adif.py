"""Exports ADIF : un fichier par référence activée (POTA, WWFF, SOTA, GMA, WWBOTA) et un export complet."""
import re
from pathlib import Path

from jcfportable import APP_NAME, VERSION
from jcfportable.bands import ADIF_MODES
from jcfportable.db import parse_iso


def _field(name, value):
    if value is None or value == "":
        return ""
    v = str(value)
    return f"<{name}:{len(v.encode('utf-8'))}>{v} "


def header(comment=""):
    h = f"{comment}\n" if comment else ""
    h += f"Généré par {APP_NAME} {VERSION}\n"
    h += _field("ADIF_VER", "3.1.4") + _field("PROGRAMID", "JCFPortable") + _field("PROGRAMVERSION", VERSION)
    return h + "<EOH>\n"


def base_fields(op, q, include_private):
    start = parse_iso(q["start"])
    mode, submode = ADIF_MODES.get(q["mode"] or "", (q["mode"], None))
    f = [
        ("CALL", q["call"]),
        ("QSO_DATE", start.strftime("%Y%m%d")),
        ("TIME_ON", start.strftime("%H%M%S")),
        ("BAND", (q["band"] or "").upper() if q["band"] else None),
        ("FREQ", f"{q['freq'] / 1000:.6f}".rstrip("0").rstrip(".") if q["freq"] else None),
        ("MODE", mode),
        ("SUBMODE", submode),
        ("RST_SENT", q["rst_sent"]),
        ("RST_RCVD", q["rst_rcvd"]),
        ("STATION_CALLSIGN", op["station_call"]),
        ("OPERATOR", q.get("operator_call") or op.get("operator_call") or op["station_call"]),
        ("MY_GRIDSQUARE", op.get("grid")),
        ("TX_PWR", q.get("power") or op.get("power")),
    ]
    if include_private:
        f += [("NAME", q.get("name")), ("QTH", q.get("qth")), ("COUNTRY", q.get("country")),
              ("GRIDSQUARE", q.get("their_grid")), ("NOTES", q.get("notes")), ("COMMENT", q.get("notes"))]
    return f


def hunted(q, program):
    return [r["ref"] for r in q.get("their_refs", []) if r.get("program") == program and r.get("ref")]


def program_fields(program, my_ref, q):
    """Champs propres au programme (activation my_ref + chasse éventuelle)."""
    f = []
    their = hunted(q, program)
    if program == "POTA":
        if my_ref:
            f += [("MY_SIG", "POTA"), ("MY_SIG_INFO", my_ref), ("MY_POTA_REF", my_ref)]
        if their:
            f += [("SIG", "POTA"), ("SIG_INFO", their[0]), ("POTA_REF", ",".join(their))]
    elif program == "WWFF":
        if my_ref:
            f += [("MY_SIG", "WWFF"), ("MY_SIG_INFO", my_ref), ("MY_WWFF_REF", my_ref)]
        if their:
            f += [("SIG", "WWFF"), ("SIG_INFO", their[0]), ("WWFF_REF", their[0])]
    elif program == "SOTA":
        if my_ref:
            f += [("MY_SOTA_REF", my_ref)]
        if their:
            f += [("SOTA_REF", their[0])]
    elif program in ("GMA", "WWBOTA"):
        if my_ref:
            f += [("MY_SIG", program), ("MY_SIG_INFO", my_ref)]
        if their:
            f += [("SIG", program), ("SIG_INFO", ",".join(their) if program == "WWBOTA" else their[0])]
    return f


def all_hunt_fields(q):
    f = []
    for prog in ("POTA", "WWFF", "SOTA", "GMA", "WWBOTA"):
        f += program_fields(prog, None, q)
    # un seul couple SIG/SIG_INFO autorisé : on garde le premier
    seen = set()
    out = []
    for k, v in f:
        if k in seen:
            continue
        seen.add(k)
        out.append((k, v))
    return out


def record(fields):
    return "".join(_field(k, v) for k, v in fields) + "<EOR>\n"


def safe_name(s):
    return re.sub(r"[^\w@. -]", "-", s)


def export_operation(op, qsos, out_dir, include_private_full=True):
    """Écrit les fichiers et retourne la liste des chemins créés."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    live = [q for q in qsos if not q.get("deleted")]
    if not live:
        return []
    paths = []
    call = op["station_call"] or "NOCALL"
    first = parse_iso(live[0]["start"])
    date = first.strftime("%Y%m%d")
    file_call = call.replace("/", "-")

    # Un fichier par référence activée, au format attendu par chaque programme
    for r in op.get("refs", []):
        prog, ref = r.get("program"), r.get("ref")
        if not prog or not ref:
            continue
        if prog == "WWFF":
            name = f"{file_call}@{ref} {date}.adi"
        else:
            name = f"{file_call}@{ref.replace('/', '-')}-{date}.adi"
        lines = [header(f"Activation {prog} {ref} par {call}")]
        for q in live:
            lines.append(record(base_fields(op, q, include_private=False) + program_fields(prog, ref, q)))
        p = out / safe_name(name)
        p.write_text("".join(lines), encoding="utf-8")
        paths.append(p)

    # Export complet pour import dans un carnet (JCFLog, QLog…)
    lines = [header(f"Export complet — {op['title']}")]
    for q in live:
        fields = base_fields(op, q, include_private=include_private_full) + all_hunt_fields(q)
        # rappel des activations dans l'export complet
        acts = {r["program"]: r["ref"] for r in reversed(op.get("refs", [])) if r.get("ref")}
        if "POTA" in acts:
            fields += [("MY_POTA_REF", ",".join(r["ref"] for r in op["refs"] if r["program"] == "POTA"))]
        if "WWFF" in acts:
            fields += [("MY_WWFF_REF", acts["WWFF"])]
        if "SOTA" in acts:
            fields += [("MY_SOTA_REF", acts["SOTA"])]
        if not any(k == "MY_SIG" for k, _ in fields):
            for prog in ("GMA", "WWBOTA", "POTA", "WWFF"):
                if prog in acts:
                    fields += [("MY_SIG", prog), ("MY_SIG_INFO", acts[prog])]
                    break
        lines.append(record(fields))
    p = out / safe_name(f"{file_call}-{date}-{safe_name(op['title'])}-complet.adi")
    p.write_text("".join(lines), encoding="utf-8")
    paths.append(p)
    return paths
