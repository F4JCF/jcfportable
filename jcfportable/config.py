"""Emplacements des fichiers et réglages utilisateur (jamais dans l'exécutable)."""
import json
import os
from pathlib import Path

from jcfportable import APP_ID


IS_WINDOWS = os.name == "nt"


def data_dir():
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    p = Path(base) / APP_ID
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_dir():
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    p = Path(base) / APP_ID
    p.mkdir(parents=True, exist_ok=True)
    return p


DEFAULTS = {
    "station_call": "",
    "operator_call": "",
    "grid": "",
    "power": "10",
    "default_prefix": {"POTA": "FR", "WWFF": "FFF", "SOTA": "F", "GMA": "", "WWBOTA": "B/F"},
    "lookup_service": "aucun",  # aucun | hamqth | qrz
    "lookup_user": "",
    "lookup_password": "",
    "export_dir": str(Path.home() / ("Documents" if IS_WINDOWS else "") / "JCFPortable" / "exports"),
    "cat_mode": "aucun",  # aucun | rigctld_local | rigctld_distant
    "cat_model": 0,
    "cat_model_label": "",
    "cat_port": "COM3" if IS_WINDOWS else "/dev/ttyUSB0",
    "cat_baud": 38400,
    "cat_host": "127.0.0.1",
    "cat_tcp_port": 4532,
    "cat_civ": "",
    "cat_extra": "",
    "cat_digital_mode": "FT8",
    "gma_read_key": "",
    "gma_submit_key": "",
    "spots_programs": ["POTA", "WWFF", "SOTA", "GMA", "WWBOTA"],
    "spots_refresh_s": 60,
    "spots_max_age_min": 60,
    "autospot_interval_min": 10,
}


class Settings:
    def __init__(self, path=None):
        self.path = Path(path) if path else config_dir() / "settings.json"
        self.data = json.loads(json.dumps(DEFAULTS))
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                for k, v in loaded.items():
                    if isinstance(v, dict) and isinstance(self.data.get(k), dict):
                        self.data[k].update(v)
                    else:
                        self.data[k] = v
            except (OSError, ValueError):
                pass

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)  # contient éventuellement le mot de passe QRZ/HamQTH
        except OSError:
            pass
        tmp.replace(self.path)
