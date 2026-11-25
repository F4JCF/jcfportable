"""Base SQLite locale : opérations, QSO, références hors ligne, cache d'indicatifs."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE,
    title TEXT,
    station_call TEXT,
    operator_call TEXT,
    grid TEXT,
    power TEXT,
    refs TEXT DEFAULT '[]',
    notes TEXT DEFAULT '',
    vfo TEXT DEFAULT '{}',
    created TEXT,
    updated TEXT,
    deleted INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS qsos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    op_id INTEGER NOT NULL,
    uuid TEXT UNIQUE,
    call TEXT NOT NULL,
    start TEXT NOT NULL,
    freq REAL,
    band TEXT,
    mode TEXT,
    rst_sent TEXT,
    rst_rcvd TEXT,
    their_refs TEXT DEFAULT '[]',
    name TEXT DEFAULT '',
    qth TEXT DEFAULT '',
    country TEXT DEFAULT '',
    their_grid TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    operator_call TEXT DEFAULT '',
    power TEXT DEFAULT '',
    deleted INTEGER DEFAULT 0,
    FOREIGN KEY(op_id) REFERENCES operations(id)
);
CREATE INDEX IF NOT EXISTS qsos_op ON qsos(op_id);
CREATE INDEX IF NOT EXISTS qsos_call ON qsos(call);
CREATE TABLE IF NOT EXISTS refs (
    program TEXT NOT NULL,
    ref TEXT NOT NULL,
    norm TEXT NOT NULL,
    name TEXT,
    grid TEXT,
    lat REAL,
    lon REAL,
    extra TEXT,
    PRIMARY KEY(program, ref)
);
CREATE INDEX IF NOT EXISTS refs_norm ON refs(program, norm);
CREATE INDEX IF NOT EXISTS refs_pos ON refs(program, lat, lon);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS callcache (
    call TEXT PRIMARY KEY, data TEXT, fetched TEXT
);
"""


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def norm_ref(ref):
    return "".join(ch for ch in (ref or "").upper() if ch.isalnum())


class Database:
    def __init__(self, path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---------- méta ----------
    def get_meta(self, key, default=None):
        r = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def set_meta(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, str(value)))
        self.conn.commit()

    # ---------- opérations ----------
    def create_operation(self, title, station_call, operator_call="", grid="", power="", refs=None, notes=""):
        t = iso(now_utc())
        cur = self.conn.execute(
            "INSERT INTO operations(uuid,title,station_call,operator_call,grid,power,refs,notes,vfo,created,updated)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), title, station_call.upper(), operator_call.upper(), grid, power,
             json.dumps(refs or []), notes, json.dumps({}), t, t))
        self.conn.commit()
        return cur.lastrowid

    def update_operation(self, op_id, **fields):
        if not fields:
            return
        if "refs" in fields:
            fields["refs"] = json.dumps(fields["refs"])
        if "vfo" in fields:
            fields["vfo"] = json.dumps(fields["vfo"])
        for k in ("station_call", "operator_call"):
            if k in fields and fields[k]:
                fields[k] = fields[k].upper()
        fields["updated"] = iso(now_utc())
        cols = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE operations SET {cols} WHERE id=?", (*fields.values(), op_id))
        self.conn.commit()

    def _op_dict(self, row):
        d = dict(row)
        d["refs"] = json.loads(d.get("refs") or "[]")
        d["vfo"] = json.loads(d.get("vfo") or "{}")
        return d

    def get_operation(self, op_id):
        r = self.conn.execute("SELECT * FROM operations WHERE id=?", (op_id,)).fetchone()
        return self._op_dict(r) if r else None

    def list_operations(self):
        rows = self.conn.execute(
            "SELECT o.*, (SELECT COUNT(*) FROM qsos q WHERE q.op_id=o.id AND q.deleted=0) AS qso_count,"
            " (SELECT MIN(start) FROM qsos q WHERE q.op_id=o.id AND q.deleted=0) AS first_qso"
            " FROM operations o WHERE deleted=0 ORDER BY o.created DESC").fetchall()
        return [self._op_dict(r) for r in rows]

    def delete_operation(self, op_id):
        self.conn.execute("UPDATE operations SET deleted=1 WHERE id=?", (op_id,))
        self.conn.commit()

    def duplicate_operation(self, op_id, title=None):
        op = self.get_operation(op_id)
        return self.create_operation(title or (op["title"] + " (copie)"), op["station_call"], op["operator_call"],
                                     op["grid"], op["power"], op["refs"], "")

    # ---------- QSO ----------
    def add_qso(self, op_id, **q):
        q.setdefault("uuid", str(uuid.uuid4()))
        q["call"] = q["call"].upper()
        if isinstance(q.get("their_refs"), list):
            q["their_refs"] = json.dumps(q["their_refs"])
        q["op_id"] = op_id
        cols = ",".join(q.keys())
        marks = ",".join("?" for _ in q)
        cur = self.conn.execute(f"INSERT INTO qsos({cols}) VALUES({marks})", tuple(q.values()))
        self.conn.execute("UPDATE operations SET updated=? WHERE id=?", (iso(now_utc()), op_id))
        self.conn.commit()
        return cur.lastrowid

    def update_qso(self, qso_id, **q):
        if isinstance(q.get("their_refs"), list):
            q["their_refs"] = json.dumps(q["their_refs"])
        if "call" in q:
            q["call"] = q["call"].upper()
        cols = ", ".join(f"{k}=?" for k in q)
        self.conn.execute(f"UPDATE qsos SET {cols} WHERE id=?", (*q.values(), qso_id))
        self.conn.commit()

    def _qso_dict(self, row):
        d = dict(row)
        d["their_refs"] = json.loads(d.get("their_refs") or "[]")
        return d

    def get_qso(self, qso_id):
        r = self.conn.execute("SELECT * FROM qsos WHERE id=?", (qso_id,)).fetchone()
        return self._qso_dict(r) if r else None

    def list_qsos(self, op_id, include_deleted=True):
        sql = "SELECT * FROM qsos WHERE op_id=?" + ("" if include_deleted else " AND deleted=0") + " ORDER BY start, id"
        return [self._qso_dict(r) for r in self.conn.execute(sql, (op_id,)).fetchall()]

    def previous_contacts(self, call, exclude_op=None):
        rows = self.conn.execute(
            "SELECT start FROM qsos WHERE call=? AND deleted=0" + (" AND op_id<>?" if exclude_op else "")
            + " ORDER BY start DESC", (call.upper(), exclude_op) if exclude_op else (call.upper(),)).fetchall()
        return [r["start"] for r in rows]

    # ---------- références ----------
    def replace_refs(self, program, rows):
        """rows: itérable de (ref, name, grid, lat, lon, extra_json)."""
        self.conn.execute("DELETE FROM refs WHERE program=?", (program,))
        batch = []
        n = 0
        for ref, name, grid, lat, lon, extra in rows:
            batch.append((program, ref, norm_ref(ref), name, grid, lat, lon, extra))
            if len(batch) >= 5000:
                self.conn.executemany("INSERT OR REPLACE INTO refs VALUES(?,?,?,?,?,?,?,?)", batch)
                n += len(batch)
                batch = []
        if batch:
            self.conn.executemany("INSERT OR REPLACE INTO refs VALUES(?,?,?,?,?,?,?,?)", batch)
            n += len(batch)
        self.conn.commit()
        return n

    def count_refs(self, program):
        return self.conn.execute("SELECT COUNT(*) FROM refs WHERE program=?", (program,)).fetchone()[0]

    def find_ref(self, program, ref):
        r = self.conn.execute("SELECT * FROM refs WHERE program=? AND norm=?", (program, norm_ref(ref))).fetchone()
        return dict(r) if r else None

    def search_refs(self, program, text, limit=200):
        t = text.strip()
        like = f"%{t}%"
        n = norm_ref(t)
        rows = self.conn.execute(
            "SELECT * FROM refs WHERE program=? AND (norm LIKE ? OR name LIKE ?) ORDER BY ref LIMIT ?",
            (program, f"%{n}%" if n else like, like, limit)).fetchall()
        return [dict(r) for r in rows]

    def refs_near(self, program, lat, lon, delta=0.5, limit=200):
        rows = self.conn.execute(
            "SELECT * FROM refs WHERE program=? AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
            (program, lat - delta, lat + delta, lon - delta * 1.5, lon + delta * 1.5)).fetchall()
        res = [dict(r) for r in rows]
        res.sort(key=lambda r: (r["lat"] - lat) ** 2 + ((r["lon"] - lon) * 0.7) ** 2)
        return res[:limit]

    def refs_with_number(self, program, prefix, number):
        """Références de forme PREFIX-0123 dont la partie numérique vaut number."""
        rows = self.conn.execute(
            "SELECT * FROM refs WHERE program=? AND ref LIKE ?", (program, f"{prefix}-%")).fetchall()
        out = []
        for r in rows:
            tail = r["ref"].rsplit("-", 1)[-1]
            if tail.isdigit() and int(tail) == number:
                out.append(dict(r))
        return out

    # ---------- cache indicatifs ----------
    def cache_call(self, call, data):
        self.conn.execute("INSERT OR REPLACE INTO callcache VALUES(?,?,?)",
                          (call.upper(), json.dumps(data), iso(now_utc())))
        self.conn.commit()

    def cached_call(self, call):
        r = self.conn.execute("SELECT data FROM callcache WHERE call=?", (call.upper(),)).fetchone()
        return json.loads(r["data"]) if r else None
