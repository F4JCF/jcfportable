"""Contrôle CAT via Hamlib (rigctld), pour toutes les radios gérées par Hamlib."""
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

IS_WINDOWS = os.name == "nt"
# Sous Windows, ne pas ouvrir de fenêtre console pour rigctld
NO_WINDOW = {"creationflags": 0x08000000} if IS_WINDOWS else {}

HAMLIB_TO_MODE = {
    "USB": "SSB", "LSB": "SSB", "CW": "CW", "CWR": "CW", "AM": "AM", "SAM": "AM",
    "FM": "FM", "FMN": "FM", "WFM": "FM", "RTTY": "RTTY", "RTTYR": "RTTY",
    "PKTUSB": "DATA", "PKTLSB": "DATA", "PKTFM": "DATA", "PKTAM": "DATA",
}


def find_tool(name):
    """Cherche d'abord les outils Hamlib embarqués dans l'AppImage, puis le système."""
    if IS_WINDOWS and not name.endswith(".exe"):
        name += ".exe"
    candidates = []
    appdir = os.environ.get("APPDIR")
    if appdir:
        candidates.append(Path(appdir) / "usr" / "bin" / name)
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / "hamlib" / name)
        if hasattr(sys, "_MEIPASS"):  # exe unique : fichiers décompressés dans un dossier temporaire
            candidates.append(Path(sys._MEIPASS) / "hamlib" / name)
    for c in candidates:
        if c.exists():
            return str(c)
    return shutil.which(name)


def list_rigs():
    """Liste (numéro, 'Fabricant Modèle') d'après « rigctl -l »."""
    exe = find_tool("rigctl")
    if not exe:
        return []
    try:
        out = subprocess.run([exe, "-l"], capture_output=True, text=True, timeout=15, **NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rigs = []
    for line in out.splitlines():
        parts = line.split()
        if not parts or not parts[0].isdigit():
            continue
        # colonnes à largeur fixe : num, fabricant, modèle, version, statut, macro
        num = int(parts[0])
        body = line[len(line) - len(line.lstrip()):].split(None, 1)
        label = body[1] if len(body) > 1 else ""
        label = " ".join(label.split()[:-3]) if len(label.split()) > 3 else label
        rigs.append((num, " ".join(label.split())))
    return rigs


def serial_ports():
    if IS_WINDOWS:
        try:
            from PySide6.QtSerialPort import QSerialPortInfo
            return [f"{p.portName()}" for p in QSerialPortInfo.availablePorts()] or ["COM3"]
        except ImportError:
            return [f"COM{i}" for i in range(1, 21)]
    ports = []
    for pattern in ("ttyUSB*", "ttyACM*", "ttyS[0-3]"):
        ports += sorted(str(p) for p in Path("/dev").glob(pattern))
    by_id = Path("/dev/serial/by-id")
    if by_id.exists():
        ports += sorted(str(p) for p in by_id.iterdir())
    return ports


def mode_to_hamlib(mode, freq_khz):
    if mode == "SSB":
        return "USB" if (freq_khz or 14000) >= 10000 else "LSB"
    if mode in ("FT8", "FT4", "PSK31", "JS8", "DATA"):
        return "PKTUSB"
    if mode in ("CW", "AM", "FM", "RTTY"):
        return mode
    return None


class RigCtl:
    """Client TCP rigctld ; peut lancer lui-même rigctld."""

    def __init__(self, settings):
        self.s = settings
        self.proc = None
        self.sock = None
        self.last_error = ""

    @property
    def enabled(self):
        return self.s.get("cat_mode", "aucun") != "aucun"

    def start(self):
        self.stop()
        if not self.enabled:
            return False
        port = int(self.s.get("cat_tcp_port", 4532))
        host = "127.0.0.1"
        if self.s.get("cat_mode") == "rigctld_local":
            exe = find_tool("rigctld")
            if not exe:
                self.last_error = ("rigctld.exe introuvable (réinstallez JCF Portable)" if IS_WINDOWS
                                   else "rigctld introuvable (installez le paquet libhamlib-utils)")
                return False
            args = [exe, "-m", str(self.s.get("cat_model", 1)), "-t", str(port)]
            if int(self.s.get("cat_model", 1)) not in (1, 2):  # 1 = rig factice, 2 = rigctld réseau
                args += ["-r", self.s.get("cat_port", "/dev/ttyUSB0"), "-s", str(self.s.get("cat_baud", 38400))]
            if self.s.get("cat_civ"):
                args += ["-c", str(self.s.get("cat_civ"))]
            if self.s.get("cat_extra"):
                args += self.s.get("cat_extra").split()
            try:
                self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **NO_WINDOW)
            except OSError as e:
                self.last_error = f"Impossible de lancer rigctld : {e}"
                return False
            time.sleep(0.8)
            if self.proc.poll() is not None:
                err = (self.proc.stderr.read() or b"").decode(errors="replace").strip()
                self.last_error = f"rigctld s'est arrêté : {err[-300:] or 'vérifiez le port et la vitesse'}"
                self.proc = None
                return False
        else:
            host = self.s.get("cat_host", "127.0.0.1")
        for _ in range(10):
            try:
                self.sock = socket.create_connection((host, port), timeout=2)
                self.sock.settimeout(2)
                self.last_error = ""
                return True
            except OSError as e:
                self.last_error = f"Connexion à rigctld {host}:{port} impossible ({e})"
                time.sleep(0.3)
        return False

    def stop(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None

    def _cmd(self, cmd, lines=1):
        if not self.sock:
            raise OSError("CAT non connecté")
        self.sock.sendall((cmd + "\n").encode())
        buf = b""
        while buf.count(b"\n") < lines:
            chunk = self.sock.recv(1024)
            if not chunk:
                raise OSError("rigctld a fermé la connexion")
            buf += chunk
            if buf.startswith(b"RPRT") and b"\n" in buf:
                break
        text = buf.decode(errors="replace").strip().splitlines()
        if text and text[0].startswith("RPRT") and text[0] != "RPRT 0":
            raise OSError(f"Erreur Hamlib {text[0]}")
        return text

    def read(self):
        """Retourne (freq_kHz, mode_jcf ou None, mode_hamlib)."""
        f = self._cmd("f")
        hz = float(f[0])
        m = self._cmd("m", 2)
        hm = m[0].strip().upper()
        mode = HAMLIB_TO_MODE.get(hm)
        if mode == "DATA":
            mode = self.s.get("cat_digital_mode", "FT8")
        return hz / 1000.0, mode, hm

    def set_freq(self, khz):
        self._cmd(f"F {int(round(khz * 1000))}")

    def set_mode(self, mode, khz):
        hm = mode_to_hamlib(mode, khz)
        if hm:
            self._cmd(f"M {hm} 0")
