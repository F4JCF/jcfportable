"""Recherche d'indicatifs : HamQTH (gratuit) ou QRZ.com (abonnement XML)."""
import xml.etree.ElementTree as ET

import requests

from jcfportable import USER_AGENT

TIMEOUT = 6


def _strip_ns(root):
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


class Lookup:
    def __init__(self, settings):
        self.s = settings
        self.session = None

    @property
    def service(self):
        return self.s.get("lookup_service", "aucun")

    def _login(self):
        user, pwd = self.s.get("lookup_user", ""), self.s.get("lookup_password", "")
        if not user or not pwd:
            raise RuntimeError("Identifiants de recherche d'indicatif non renseignés")
        if self.service == "hamqth":
            r = requests.get("https://www.hamqth.com/xml.php", params={"u": user, "p": pwd},
                             headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            root = _strip_ns(ET.fromstring(r.content))
            sid = root.findtext(".//session_id")
            if not sid:
                raise RuntimeError(root.findtext(".//error") or "Connexion HamQTH refusée")
            self.session = sid
        elif self.service == "qrz":
            r = requests.get("https://xmldata.qrz.com/xml/current/",
                             params={"username": user, "password": pwd, "agent": USER_AGENT},
                             headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            root = _strip_ns(ET.fromstring(r.content))
            key = root.findtext(".//Key")
            if not key:
                raise RuntimeError(root.findtext(".//Error") or "Connexion QRZ refusée")
            self.session = key

    def lookup(self, call, retry=True):
        """Retourne un dict {name, qth, country, grid} ou None."""
        if self.service == "aucun":
            return None
        if not self.session:
            self._login()
        try:
            if self.service == "hamqth":
                r = requests.get("https://www.hamqth.com/xml.php",
                                 params={"id": self.session, "callsign": call, "prg": "JCFPortable"},
                                 headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
                root = _strip_ns(ET.fromstring(r.content))
                err = root.findtext(".//error")
                if err:
                    if "session" in err.lower() and retry:
                        self.session = None
                        return self.lookup(call, retry=False)
                    return None
                s = root.find(".//search")
                if s is None:
                    return None
                return {"name": s.findtext("nick") or s.findtext("adr_name") or "",
                        "qth": s.findtext("qth") or s.findtext("adr_city") or "",
                        "country": s.findtext("country") or "",
                        "grid": s.findtext("grid") or ""}
            r = requests.get("https://xmldata.qrz.com/xml/current/",
                             params={"s": self.session, "callsign": call},
                             headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            root = _strip_ns(ET.fromstring(r.content))
            err = root.findtext(".//Error")
            if err and "session" in err.lower() and retry:
                self.session = None
                return self.lookup(call, retry=False)
            c = root.find(".//Callsign")
            if c is None:
                return None
            name = " ".join(x for x in (c.findtext("fname"), c.findtext("name")) if x)
            return {"name": name, "qth": c.findtext("addr2") or "", "country": c.findtext("country") or "",
                    "grid": c.findtext("grid") or ""}
        except ET.ParseError:
            return None
