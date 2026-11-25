"""Fenêtres secondaires : opération, recherche de référence, données hors ligne, réglages, édition de QSO."""
from datetime import datetime, timezone

from PySide6.QtCore import QDateTime, Qt, QTimeZone
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDateTimeEdit, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
                               QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
                               QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from jcfportable import cat
from jcfportable.bands import MODES, band_for_freq
from jcfportable.db import iso, parse_iso
from jcfportable.geo import grid_distance, grid_to_latlon
from jcfportable.refs import PROGRAM_KEYS, PROGRAMS, download_program, expand_ref
from jcfportable.ui.workers import run_bg


def _item(text, data=None):
    it = QTableWidgetItem(str(text) if text is not None else "")
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    if data is not None:
        it.setData(Qt.UserRole, data)
    return it


# ---------------------------------------------------------------------------
class RefSearchDialog(QDialog):
    def __init__(self, db, settings, program="POTA", grid="", parent=None):
        super().__init__(parent)
        self.db, self.settings, self.grid = db, settings, grid
        self.setWindowTitle("Rechercher une référence")
        self.resize(760, 520)
        self.selected = None
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.prog = QComboBox()
        self.prog.addItems(PROGRAM_KEYS)
        self.prog.setCurrentText(program)
        self.text = QLineEdit()
        self.text.setPlaceholderText("Référence ou nom (ex. FR-0123, 2518, Estérel…)")
        near = QPushButton("Autour de mon locator")
        row.addWidget(self.prog)
        row.addWidget(self.text, 1)
        row.addWidget(near)
        lay.addLayout(row)
        self.info = QLabel()
        lay.addWidget(self.info)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Référence", "Nom", "Locator", "Distance"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().hide()
        self.table.doubleClicked.connect(self.accept_current)
        lay.addWidget(self.table, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept_current)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.text.textChanged.connect(self.search)
        self.text.returnPressed.connect(self.accept_current)
        self.prog.currentTextChanged.connect(self.search)
        near.clicked.connect(self.search_near)
        if grid:
            self.search_near()
        else:
            self.search()

    def _fill(self, rows):
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            dist = grid_distance(self.grid, r.get("grid")) if self.grid else None
            self.table.setItem(i, 0, _item(r["ref"], r))
            self.table.setItem(i, 1, _item(r.get("name")))
            self.table.setItem(i, 2, _item(r.get("grid")))
            self.table.setItem(i, 3, _item(f"{dist[0]:.1f} km" if dist else ""))
        if rows:
            self.table.selectRow(0)
        n = self.db.count_refs(self.prog.currentText())
        self.info.setText(f"{len(rows)} résultat(s) — {n} références {self.prog.currentText()} en mémoire"
                          if n else "⚠ Liste non téléchargée : menu Données hors ligne. "
                                    "Vous pouvez quand même saisir la référence à la main.")

    def search(self):
        t = self.text.text().strip()
        p = self.prog.currentText()
        if not t:
            if self.grid:
                self.search_near()
            else:
                self._fill([])
            return
        rows = self.db.search_refs(p, t)
        ref, hit = expand_ref(self.db, p, t, self.settings["default_prefix"].get(p, ""))
        if hit and all(r["ref"] != hit["ref"] for r in rows):
            rows.insert(0, hit)
        self._fill(rows)

    def search_near(self):
        ll = grid_to_latlon(self.grid)
        if not ll:
            self.info.setText("Renseignez votre locator (6 caractères) pour chercher autour de vous.")
            return
        self._fill(self.db.refs_near(self.prog.currentText(), ll[0], ll[1]))

    def accept_current(self):
        row = self.table.currentRow()
        if row >= 0:
            data = self.table.item(row, 0).data(Qt.UserRole)
            self.selected = {"program": self.prog.currentText(), "ref": data["ref"], "name": data.get("name", "")}
        elif self.text.text().strip():
            p = self.prog.currentText()
            ref, _ = expand_ref(self.db, p, self.text.text(), self.settings["default_prefix"].get(p, ""))
            self.selected = {"program": p, "ref": ref, "name": ""}
        else:
            return
        self.accept()


# ---------------------------------------------------------------------------
class OperationForm(QWidget):
    """Formulaire d'opération : indicatif, locator, activations…"""

    def __init__(self, db, settings, parent=None):
        super().__init__(parent)
        self.db, self.settings = db, settings
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.title = QLineEdit()
        self.title.setPlaceholderText("ex. Activation Estérel")
        self.station = QLineEdit()
        self.station.setPlaceholderText("Indicatif utilisé à l'antenne, ex. F4JCF/P")
        self.operator = QLineEdit()
        self.grid = QLineEdit()
        self.grid.setMaxLength(8)
        gl = QHBoxLayout()
        gl.addWidget(self.grid)
        b = QPushButton("Mon locator")
        b.clicked.connect(lambda: self.grid.setText(self.settings["grid"]))
        gl.addWidget(b)
        self.power = QLineEdit()
        form.addRow("Titre", self.title)
        form.addRow("Indicatif station", self.station)
        form.addRow("Opérateur", self.operator)
        form.addRow("Locator", gl)
        form.addRow("Puissance (W)", self.power)
        lay.addLayout(form)
        box = QGroupBox("Activations (références activées pendant cette opération)")
        bl = QVBoxLayout(box)
        self.refs = QTableWidget(0, 3)
        self.refs.setHorizontalHeaderLabels(["Programme", "Référence", "Nom"])
        self.refs.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.refs.verticalHeader().hide()
        self.refs.setSelectionBehavior(QAbstractItemView.SelectRows)
        bl.addWidget(self.refs)
        br = QHBoxLayout()
        add = QPushButton("Ajouter une référence…")
        rem = QPushButton("Retirer")
        add.clicked.connect(self.add_ref)
        rem.clicked.connect(lambda: self.refs.removeRow(self.refs.currentRow()))
        br.addWidget(add)
        br.addWidget(rem)
        br.addStretch()
        bl.addLayout(br)
        lay.addWidget(box)
        lay.addWidget(QLabel("Notes"))
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(90)
        lay.addWidget(self.notes)

    def add_ref(self):
        prog = "POTA"
        if self.refs.rowCount():
            prog = self.refs.item(self.refs.rowCount() - 1, 0).text()
        dlg = RefSearchDialog(self.db, self.settings, prog, self.grid.text(), self)
        if dlg.exec() and dlg.selected:
            s = dlg.selected
            self._add_row(s["program"], s["ref"], s.get("name", ""))
            if not self.grid.text():
                hit = self.db.find_ref(s["program"], s["ref"])
                if hit and hit.get("grid"):
                    self.grid.setText(hit["grid"])
            if not self.title.text():
                self.title.setText(f"{s['program']} {s['ref']} {s.get('name', '')}".strip())

    def _add_row(self, prog, ref, name):
        i = self.refs.rowCount()
        self.refs.insertRow(i)
        self.refs.setItem(i, 0, _item(prog))
        self.refs.setItem(i, 1, _item(ref))
        self.refs.setItem(i, 2, _item(name))

    def load(self, op=None):
        s = self.settings
        op = op or {}
        self.title.setText(op.get("title", ""))
        self.station.setText(op.get("station_call") or s["station_call"])
        self.operator.setText(op.get("operator_call") or s["operator_call"] or s["station_call"])
        self.grid.setText(op.get("grid") or s["grid"])
        self.power.setText(op.get("power") or s["power"])
        self.refs.setRowCount(0)
        for r in op.get("refs", []):
            hit = self.db.find_ref(r["program"], r["ref"])
            self._add_row(r["program"], r["ref"], hit["name"] if hit else "")
        self.notes.setPlainText(op.get("notes", ""))

    def values(self):
        refs = [{"program": self.refs.item(i, 0).text(), "ref": self.refs.item(i, 1).text()}
                for i in range(self.refs.rowCount())]
        title = self.title.text().strip() or datetime.now().strftime("Opération du %d/%m/%Y")
        return {"title": title, "station_call": self.station.text().strip().upper(),
                "operator_call": self.operator.text().strip().upper(), "grid": self.grid.text().strip(),
                "power": self.power.text().strip(), "refs": refs, "notes": self.notes.toPlainText()}


class OperationDialog(QDialog):
    def __init__(self, db, settings, op=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nouvelle opération" if not op else "Opération")
        self.resize(620, 560)
        lay = QVBoxLayout(self)
        self.form = OperationForm(db, settings, self)
        self.form.load(op)
        lay.addWidget(self.form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _ok(self):
        if not self.form.station.text().strip():
            QMessageBox.warning(self, "Indicatif manquant", "Indiquez l'indicatif de la station.")
            return
        self.accept()


# ---------------------------------------------------------------------------
class DataDialog(QDialog):
    """Téléchargement des listes de références pour un usage hors ligne."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Données hors ligne")
        self.resize(640, 360)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Téléchargez les listes à la maison : elles servent ensuite sur le terrain, "
                             "sans réseau.\nPOTA et WWFF changent souvent : une mise à jour par mois est conseillée."))
        self.table = QTableWidget(len(PROGRAM_KEYS), 4)
        self.table.setHorizontalHeaderLabels(["Programme", "Références", "Mise à jour", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        for i, p in enumerate(PROGRAM_KEYS):
            self.table.setItem(i, 0, _item(PROGRAMS[p]["label"]))
            b = QPushButton("Télécharger")
            b.clicked.connect(lambda _=False, prog=p: self.download([prog]))
            self.table.setCellWidget(i, 3, b)
        lay.addWidget(self.table)
        self.bar = QProgressBar()
        self.msg = QLabel()
        lay.addWidget(self.bar)
        lay.addWidget(self.msg)
        row = QHBoxLayout()
        all_b = QPushButton("Tout télécharger")
        all_b.clicked.connect(lambda: self.download(list(PROGRAM_KEYS)))
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        row.addWidget(all_b)
        row.addStretch()
        row.addWidget(close)
        lay.addLayout(row)
        self.queue = []
        self.refresh()

    def refresh(self):
        for i, p in enumerate(PROGRAM_KEYS):
            self.table.setItem(i, 1, _item(f"{self.db.count_refs(p):,}".replace(",", " ")))
            upd = self.db.get_meta(f"refs_updated_{p}")
            self.table.setItem(i, 2, _item(parse_iso(upd).strftime("%d/%m/%Y %H:%M") if upd else "jamais"))

    def download(self, programs):
        if self.queue:
            return
        self.queue = list(programs)
        self._next()

    def _next(self):
        if not self.queue:
            self.refresh()
            return
        p = self.queue.pop(0)
        run_bg(download_program, self.db, p,
               on_result=lambda n: (self.msg.setText(f"{p} : {n} références enregistrées"), self.refresh(),
                                    self._next()),
               on_error=lambda e: (self.msg.setText(f"⚠ {p} : {e}"), self._next()),
               on_progress=lambda v, m: (self.bar.setValue(v), self.msg.setText(m)))


# ---------------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.s = settings
        self.setWindowTitle("Réglages")
        self.resize(640, 520)
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        # Station
        w = QWidget()
        f = QFormLayout(w)
        self.call = QLineEdit(settings["station_call"])
        self.oper = QLineEdit(settings["operator_call"])
        self.grid = QLineEdit(settings["grid"])
        self.power = QLineEdit(settings["power"])
        f.addRow("Indicatif par défaut", self.call)
        f.addRow("Opérateur", self.oper)
        f.addRow("Locator (6 caractères)", self.grid)
        f.addRow("Puissance par défaut (W)", self.power)
        f.addRow(QLabel("<b>Préfixes pour la saisie courte</b> (taper « 123 » donne FR-0123)"))
        self.prefixes = {}
        for p in PROGRAM_KEYS:
            e = QLineEdit(settings["default_prefix"].get(p, ""))
            self.prefixes[p] = e
            f.addRow(f"Préfixe {p}", e)
        tabs.addTab(w, "Station")

        # Recherche d'indicatifs
        w = QWidget()
        f = QFormLayout(w)
        self.lk_service = QComboBox()
        self.lk_service.addItem("Aucune", "aucun")
        self.lk_service.addItem("HamQTH (gratuit)", "hamqth")
        self.lk_service.addItem("QRZ.com (abonnement XML)", "qrz")
        self.lk_service.setCurrentIndex(max(0, self.lk_service.findData(settings["lookup_service"])))
        self.lk_user = QLineEdit(settings["lookup_user"])
        self.lk_pass = QLineEdit(settings["lookup_password"])
        self.lk_pass.setEchoMode(QLineEdit.Password)
        f.addRow("Service", self.lk_service)
        f.addRow("Identifiant", self.lk_user)
        f.addRow("Mot de passe", self.lk_pass)
        f.addRow(QLabel("Le mot de passe est enregistré uniquement sur ce PC, dans le dossier des réglages."))
        tabs.addTab(w, "Recherche d'indicatifs")

        # CAT
        w = QWidget()
        f = QFormLayout(w)
        self.cat_mode = QComboBox()
        self.cat_mode.addItem("Pas de CAT (saisie manuelle de la fréquence)", "aucun")
        self.cat_mode.addItem("Radio branchée sur ce PC (le logiciel lance rigctld)", "rigctld_local")
        self.cat_mode.addItem("rigctld déjà lancé ailleurs (réseau, Raspberry…)", "rigctld_distant")
        self.cat_mode.setCurrentIndex(max(0, self.cat_mode.findData(settings["cat_mode"])))
        f.addRow("Mode CAT", self.cat_mode)
        self.rig_filter = QLineEdit()
        self.rig_filter.setPlaceholderText("Filtrer : yaesu 991, icom 705, kenwood…")
        self.rig = QComboBox()
        self.rigs = cat.list_rigs()
        f.addRow("Chercher la radio", self.rig_filter)
        f.addRow("Radio (Hamlib)", self.rig)
        self.rig_filter.textChanged.connect(self._fill_rigs)
        self._fill_rigs()
        if not self.rigs:
            f.addRow(QLabel("⚠ Hamlib introuvable : réinstallez JCF Portable (Windows) ou installez libhamlib-utils (Linux)."))
        prow = QHBoxLayout()
        self.port = QComboBox()
        self.port.setEditable(True)
        self.port.addItems(cat.serial_ports())
        self.port.setCurrentText(settings["cat_port"])
        rb = QPushButton("↻")
        rb.setMaximumWidth(36)
        rb.clicked.connect(lambda: (self.port.clear(), self.port.addItems(cat.serial_ports())))
        prow.addWidget(self.port, 1)
        prow.addWidget(rb)
        f.addRow("Port série", prow)
        self.baud = QComboBox()
        self.baud.addItems(["4800", "9600", "19200", "38400", "57600", "115200"])
        self.baud.setCurrentText(str(settings["cat_baud"]))
        f.addRow("Vitesse (bauds)", self.baud)
        self.civ = QLineEdit(str(settings.get("cat_civ", "")))
        self.civ.setPlaceholderText("Icom uniquement, ex. 0xA4 (laisser vide sinon)")
        f.addRow("Adresse CI-V", self.civ)
        self.host = QLineEdit(settings["cat_host"])
        self.tcp = QSpinBox()
        self.tcp.setRange(1, 65535)
        self.tcp.setValue(int(settings["cat_tcp_port"]))
        f.addRow("Hôte rigctld (mode réseau)", self.host)
        f.addRow("Port TCP rigctld", self.tcp)
        self.digital = QComboBox()
        self.digital.addItems(["FT8", "FT4", "RTTY", "PSK31", "JS8", "DATA"])
        self.digital.setCurrentText(settings["cat_digital_mode"])
        f.addRow("Mode noté quand la radio est en DATA", self.digital)
        self.extra = QLineEdit(settings.get("cat_extra", ""))
        self.extra.setPlaceholderText("Options rigctld avancées, ex. --set-conf=rts_state=OFF")
        f.addRow("Options supplémentaires", self.extra)
        test = QPushButton("Tester la liaison")
        test.clicked.connect(self.test_cat)
        self.test_msg = QLabel()
        self.test_msg.setWordWrap(True)
        f.addRow(test, self.test_msg)
        tabs.addTab(w, "CAT (Hamlib)")

        # Spots / export
        w = QWidget()
        f = QFormLayout(w)
        self.spot_prog = {}
        pl = QHBoxLayout()
        for p in PROGRAM_KEYS:
            cb = QCheckBox(p)
            cb.setChecked(p in settings["spots_programs"])
            self.spot_prog[p] = cb
            pl.addWidget(cb)
        f.addRow("Spots à afficher", pl)
        self.refresh = QSpinBox()
        self.refresh.setRange(30, 600)
        self.refresh.setValue(int(settings["spots_refresh_s"]))
        self.refresh.setSuffix(" s")
        f.addRow("Actualisation des spots", self.refresh)
        self.max_age = QSpinBox()
        self.max_age.setRange(5, 240)
        self.max_age.setValue(int(settings["spots_max_age_min"]))
        self.max_age.setSuffix(" min")
        f.addRow("Âge maximum des spots", self.max_age)
        self.auto = QSpinBox()
        self.auto.setRange(5, 60)
        self.auto.setValue(int(settings["autospot_interval_min"]))
        self.auto.setSuffix(" min")
        f.addRow("Intervalle de l'auto-spot", self.auto)
        el = QHBoxLayout()
        self.export_dir = QLineEdit(settings["export_dir"])
        eb = QPushButton("…")
        eb.setMaximumWidth(36)
        eb.clicked.connect(self._pick_dir)
        el.addWidget(self.export_dir, 1)
        el.addWidget(eb)
        f.addRow("Dossier des exports ADIF", el)
        tabs.addTab(w, "Spots et exports")

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _fill_rigs(self):
        flt = self.rig_filter.text().lower().split()
        cur = int(self.s.get("cat_model", 0))
        self.rig.clear()
        for num, label in self.rigs:
            text = f"{label} (#{num})"
            if all(w in text.lower() for w in flt):
                self.rig.addItem(text, num)
        i = self.rig.findData(cur)
        if i >= 0:
            self.rig.setCurrentIndex(i)

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Dossier des exports", self.export_dir.text())
        if d:
            self.export_dir.setText(d)

    def _apply(self, target):
        target["station_call"] = self.call.text().strip().upper()
        target["operator_call"] = self.oper.text().strip().upper()
        target["grid"] = self.grid.text().strip()
        target["power"] = self.power.text().strip()
        target["default_prefix"] = {p: e.text().strip().upper() for p, e in self.prefixes.items()}
        target["lookup_service"] = self.lk_service.currentData()
        target["lookup_user"] = self.lk_user.text().strip()
        target["lookup_password"] = self.lk_pass.text()
        target["cat_mode"] = self.cat_mode.currentData()
        if self.rig.currentData() is not None:
            target["cat_model"] = int(self.rig.currentData())
            target["cat_model_label"] = self.rig.currentText()
        target["cat_port"] = self.port.currentText().strip()
        target["cat_baud"] = int(self.baud.currentText())
        target["cat_civ"] = self.civ.text().strip()
        target["cat_host"] = self.host.text().strip()
        target["cat_tcp_port"] = self.tcp.value()
        target["cat_digital_mode"] = self.digital.currentText()
        target["cat_extra"] = self.extra.text().strip()
        target["spots_programs"] = [p for p, cb in self.spot_prog.items() if cb.isChecked()]
        target["spots_refresh_s"] = self.refresh.value()
        target["spots_max_age_min"] = self.max_age.value()
        target["autospot_interval_min"] = self.auto.value()
        target["export_dir"] = self.export_dir.text().strip()

    def test_cat(self):
        tmp = dict(self.s.data)
        self._apply(tmp)
        tmp["cat_tcp_port"] = int(tmp["cat_tcp_port"]) + 7  # port à part pour ne pas gêner la liaison en cours
        self.test_msg.setText("Test en cours…")

        def job():
            rig = cat.RigCtl(tmp)
            if tmp["cat_mode"] == "rigctld_distant":
                tmp["cat_tcp_port"] -= 7
            if not rig.start():
                return f"❌ {rig.last_error}"
            try:
                f, m, hm = rig.read()
                return f"✅ Radio OK : {f / 1000:.4f} MHz, mode {hm}"
            except OSError as e:
                return f"❌ {e}"
            finally:
                rig.stop()

        run_bg(job, on_result=self.test_msg.setText, on_error=lambda e: self.test_msg.setText(f"❌ {e}"))

    def save(self):
        self._apply(self.s.data)
        self.s.save()
        self.accept()


# ---------------------------------------------------------------------------
def refs_to_text(refs):
    return ", ".join(f"{r['program']}:{r['ref']}" for r in refs)


def text_to_refs(text):
    out = []
    for part in text.split(","):
        part = part.strip()
        if ":" in part:
            p, r = part.split(":", 1)
            if p.strip().upper() in PROGRAMS and r.strip():
                out.append({"program": p.strip().upper(), "ref": r.strip().upper()})
    return out


class QsoEditDialog(QDialog):
    def __init__(self, qso, parent=None):
        super().__init__(parent)
        self.q = qso
        self.action = None
        self.setWindowTitle(f"QSO avec {qso['call']}")
        lay = QVBoxLayout(self)
        g = QGridLayout()
        self.call = QLineEdit(qso["call"])
        self.when = QDateTimeEdit()
        self.when.setTimeZone(QTimeZone.utc())
        self.when.setDisplayFormat("dd/MM/yyyy HH:mm:ss 'UTC'")
        self.when.setDateTime(QDateTime.fromSecsSinceEpoch(int(parse_iso(qso["start"]).timestamp()), QTimeZone.utc()))
        self.freq = QDoubleSpinBox()
        self.freq.setRange(0, 1500000)
        self.freq.setDecimals(1)
        self.freq.setSuffix(" kHz")
        self.freq.setValue(qso.get("freq") or 0)
        self.mode = QComboBox()
        self.mode.addItems(MODES)
        self.mode.setCurrentText(qso.get("mode") or "SSB")
        self.sent = QLineEdit(qso.get("rst_sent") or "")
        self.rcvd = QLineEdit(qso.get("rst_rcvd") or "")
        self.refs = QLineEdit(refs_to_text(qso.get("their_refs", [])))
        self.refs.setPlaceholderText("POTA:FR-0001, SOTA:F/AM-468")
        self.name = QLineEdit(qso.get("name") or "")
        self.qth = QLineEdit(qso.get("qth") or "")
        self.country = QLineEdit(qso.get("country") or "")
        self.grid = QLineEdit(qso.get("their_grid") or "")
        self.notes = QLineEdit(qso.get("notes") or "")
        rows = [("Indicatif", self.call), ("Date / heure", self.when), ("Fréquence", self.freq), ("Mode", self.mode),
                ("RST envoyé", self.sent), ("RST reçu", self.rcvd), ("Réf. chassées (P2P)", self.refs),
                ("Nom", self.name), ("QTH", self.qth), ("Pays", self.country), ("Locator", self.grid),
                ("Notes", self.notes)]
        for i, (lab, wid) in enumerate(rows):
            g.addWidget(QLabel(lab), i, 0)
            g.addWidget(wid, i, 1)
        lay.addLayout(g)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        dele = bb.addButton("Restaurer" if qso.get("deleted") else "Supprimer", QDialogButtonBox.DestructiveRole)
        dele.clicked.connect(self._toggle_delete)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _toggle_delete(self):
        self.action = ("delete", {"deleted": 0 if self.q.get("deleted") else 1})
        self.accept()

    def _save(self):
        dt = datetime.fromtimestamp(self.when.dateTime().toSecsSinceEpoch(), timezone.utc)
        f = self.freq.value() or None
        self.action = ("save", {
            "call": self.call.text().strip().upper(), "start": iso(dt), "freq": f,
            "band": band_for_freq(f) if f else self.q.get("band"), "mode": self.mode.currentText(),
            "rst_sent": self.sent.text().strip(), "rst_rcvd": self.rcvd.text().strip(),
            "their_refs": text_to_refs(self.refs.text()), "name": self.name.text().strip(),
            "qth": self.qth.text().strip(), "country": self.country.text().strip(),
            "their_grid": self.grid.text().strip(), "notes": self.notes.text().strip()})
        self.accept()
