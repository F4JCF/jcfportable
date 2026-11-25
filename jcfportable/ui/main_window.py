"""Fenêtre principale : opérations, saisie rapide des QSO, spots, statistiques."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QRectF, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import (QAction, QColor, QDesktopServices, QFont, QKeySequence, QLinearGradient, QPainter,
                           QPainterPath, QPen, QShortcut)
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDockWidget, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QPushButton, QSizePolicy, QTableWidget, QTabWidget, QTextBrowser, QToolBar,
                               QToolButton, QVBoxLayout, QWidget)

from jcfportable import APP_NAME, VERSION, adif, commands, maps, spots
from jcfportable.bands import BAND_NAMES, MODES, band_for_freq, default_freq_for_band, default_rst, fmt_freq
from jcfportable.config import config_dir, data_dir
from jcfportable.db import iso, now_utc, parse_iso
from jcfportable.geo import grid_distance
from jcfportable.lookup import Lookup
from jcfportable.refs import PROGRAM_KEYS, PROGRAMS, expand_ref
from jcfportable.ui import icons
from jcfportable.ui.dialogs import (DataDialog, OperationDialog, OperationForm, QsoEditDialog, SettingsDialog,
                                    _item)
from jcfportable.ui.workers import CatThread, run_bg

BIG = QFont()
BIG.setPointSize(15)


class SpaceToNext(QObject):
    """Dans le champ indicatif, la barre d'espace passe au champ suivant (comme PoLo)."""

    def __init__(self, nxt):
        super().__init__()
        self.nxt = nxt

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.KeyPress and ev.key() == Qt.Key_Space and obj.text().strip():
            self.nxt.setFocus()
            self.nxt.selectAll()
            return True
        return False


class Banner(QWidget):
    """Bandeau montagnes + pylône à droite de la barre d'outils, avec l'indicatif de la station."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pix = icons.asset("banner.png")
        self.call = ""
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def set_call(self, call):
        self.call = (call or "").split("/")[0].upper()
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        h = self.height()
        if not self.pix.isNull():
            w = int(self.pix.width() * h / self.pix.height())
            x = self.width() - w
            p.drawPixmap(QRectF(x, 0, w, h), self.pix, QRectF(self.pix.rect()))
            # fondu vers la barre d'outils à gauche
            g = QLinearGradient(x, 0, x + 70, 0)
            g.setColorAt(0, QColor(10, 40, 75, 255))
            g.setColorAt(1, QColor(10, 40, 75, 0))
            p.fillRect(QRectF(x, 0, 70, h), g)
        else:
            w, x = self.width(), 0
        if self.call:
            f = QFont("Segoe UI", 1, QFont.Black)
            f.setItalic(True)
            f.setPixelSize(int(h * 0.50))
            path = QPainterPath()
            fm_w = p.fontMetrics()
            p.setFont(f)
            fm_w = p.fontMetrics().horizontalAdvance(self.call)
            cx = x + w * 0.60 - fm_w / 2
            base = h * 0.66
            path.addText(cx, base, f, self.call)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 20, 50, 170))
            p.drawPath(path.translated(3, 3))
            g = QLinearGradient(0, base - h * 0.42, 0, base)
            g.setColorAt(0, QColor("#ffffff"))
            g.setColorAt(0.55, QColor("#e3eef9"))
            g.setColorAt(1, QColor("#9fb4c9"))
            p.setBrush(g)
            p.setPen(QPen(QColor(20, 45, 80, 200), 1.2))
            p.drawPath(path)
        p.end()


class InfoBar(QFrame):
    """Ligne d'information sous le carnet : indicatif, drapeau, nom, QTH, pays…"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("infobar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(12)
        self.call = QLabel()
        self.call.setObjectName("infocall")
        self.flag = QLabel()
        self.body = QLabel(" ")
        self.body.setTextFormat(Qt.RichText)
        self.body.setWordWrap(True)
        lay.addWidget(self.call)
        lay.addWidget(self.flag)
        lay.addWidget(self.body, 1)
        self.setMinimumHeight(46)
        self.setText(" ")

    def text(self):
        return self.body.text()

    def setText(self, html):
        self.call.hide()
        self.flag.hide()
        self.body.setText(html)

    def show_call(self, call, flag_pm, html):
        self.call.setText(call)
        self.call.show()
        if flag_pm is not None and not flag_pm.isNull():
            self.flag.setPixmap(flag_pm.scaledToHeight(22, Qt.SmoothTransformation))
            self.flag.show()
        else:
            self.flag.hide()
        self.body.setText(html)


class MainWindow(QMainWindow):
    def __init__(self, db, settings):
        super().__init__()
        self.db, self.s = db, settings
        self.op = None
        self.qsos = []
        self.frozen = None          # heure fixée à la main (saisie a posteriori)
        self.vfo = {}
        self.cat = None
        self.cat_ok = False
        self.spots_list = []
        self.lookup = Lookup(settings)
        self.lookup_data = {}
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        self.setWindowIcon(icons.icon("antenna", 64))
        self.resize(1360, 820)
        self._build_toolbar()
        self._build_ops_dock()
        self._build_center()
        self._build_statusbar()
        self.clock = QTimer(self, interval=1000, timeout=self._tick)
        self.clock.start()
        self._tick()
        self.spot_timer = QTimer(self, timeout=self.refresh_spots)
        self.auto_timer = QTimer(self, timeout=lambda: self.self_spot("", auto=True))
        self.lookup_timer = QTimer(self, singleShot=True, interval=500, timeout=self._lookup_now)
        self.status_timer = QTimer(self, singleShot=True, timeout=lambda: self.set_status("Prêt"))
        self.apply_settings()
        self.load_operations()
        QTimer.singleShot(300, self._first_run)

    # ------------------------------------------------------------------ construction
    def _build_toolbar(self):
        tb = QToolBar("Actions")
        tb.setObjectName("maintoolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(40, 40))
        tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.addToolBar(tb)

        def act(text, ico, slot, key=None, primary=False):
            a = QAction(icons.icon(ico, 40), text, self)
            a.triggered.connect(slot)
            if key:
                a.setShortcut(QKeySequence(key))
                a.setToolTip(f"{text} ({key})")
            tb.addAction(a)
            btn = tb.widgetForAction(a)
            if isinstance(btn, QToolButton):
                btn.setObjectName("primary" if primary else "tool")
                btn.setMinimumWidth(96)
            return a

        act("Nouvelle opération", "home", self.new_operation, "Ctrl+N", primary=True)
        act("Dupliquer", "folder", self.duplicate_operation)
        act("Supprimer", "trash", self.delete_operation)
        act("Exporter ADIF", "export", self.export_logs, "Ctrl+E")
        act("Carte des QSO", "database", self.show_map, "Ctrl+M")
        act("Données hors ligne", "chart", self.open_data)
        act("Réglages", "gear", self.open_settings, "Ctrl+,")
        act("Aide", "help", self.show_help, "F1")
        self.banner = Banner()
        tb.addWidget(self.banner)

    def _build_ops_dock(self):
        dock = QDockWidget(self)
        dock.setObjectName("opsdock")
        dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        title = QWidget()
        title.setObjectName("docktitle")
        tl = QHBoxLayout(title)
        tl.setContentsMargins(12, 8, 12, 8)
        ic = QLabel()
        ic.setPixmap(icons.pixmap("operators", 26))
        lab = QLabel("Opérations")
        lab.setObjectName("docktitletext")
        tl.addWidget(ic)
        tl.addWidget(lab, 1)
        dock.setTitleBarWidget(title)
        body = QWidget()
        body.setObjectName("dockbody")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        self.ops = QListWidget()
        self.ops.setObjectName("opslist")
        self.ops.setIconSize(QSize(34, 34))
        self.ops.currentItemChanged.connect(lambda cur, _: cur and self.select_operation(cur.data(Qt.UserRole)))
        bl.addWidget(self.ops, 1)
        self.side_art = QLabel()
        self.side_art.setObjectName("sideart")
        self._side_pix = icons.asset("side.png")
        self.side_art.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        bl.addWidget(self.side_art)
        dock.setWidget(body)
        dock.setMinimumWidth(250)
        dock.setMaximumWidth(330)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.ops_dock = dock

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if not self._side_pix.isNull():
            w = max(200, self.ops_dock.width() - 2)
            pm = self._side_pix.scaledToWidth(w, Qt.SmoothTransformation)
            max_h = max(120, int(self.height() * 0.45))
            if pm.height() > max_h:
                pm = pm.copy(0, pm.height() - max_h, pm.width(), max_h)
            self.side_art.setPixmap(pm)

    def _vsep(self):
        s = QFrame()
        s.setObjectName("vsep")
        s.setFixedWidth(1)
        s.setMinimumHeight(30)
        return s

    def _build_center(self):
        central = QWidget()
        central.setObjectName("central")
        v = QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 4)
        # Bandeau d'opération
        head = QFrame()
        head.setObjectName("header")
        h = QHBoxLayout(head)
        h.setContentsMargins(14, 10, 16, 10)
        cal = QLabel()
        cal.setPixmap(icons.pixmap("calendar", 40))
        h.addWidget(cal)
        left = QVBoxLayout()
        left.setSpacing(0)
        self.op_title = QLabel("Aucune opération")
        self.op_title.setObjectName("optitle")
        self.op_refs = QLabel("")
        self.op_refs.setObjectName("opsub")
        self.op_refs.setTextFormat(Qt.RichText)
        left.addWidget(self.op_title)
        left.addWidget(self.op_refs)
        h.addLayout(left, 1)
        sig = QLabel()
        sig.setPixmap(icons.pixmap("signal", 22))
        h.addWidget(sig)
        self.vfo_label = QLabel()
        self.vfo_label.setObjectName("headval")
        self.vfo_label.setTextFormat(Qt.RichText)
        h.addWidget(self.vfo_label)
        h.addSpacing(10)
        h.addWidget(self._vsep())
        h.addSpacing(10)
        clk = QLabel()
        clk.setPixmap(icons.pixmap("clock", 24))
        h.addWidget(clk)
        self.clock_label = QLabel()
        self.clock_label.setObjectName("headval")
        self.clock_label.setTextFormat(Qt.RichText)
        self.clock_label.setCursor(Qt.PointingHandCursor)
        self.clock_label.setToolTip("Cliquez pour revenir à l'heure actuelle")
        self.clock_label.mousePressEvent = lambda e: self._set_frozen(None)
        h.addWidget(self.clock_label)
        h.addSpacing(10)
        h.addWidget(self._vsep())
        h.addSpacing(10)
        self.cat_dot = QLabel()
        self.cat_dot.setPixmap(icons.pixmap("dot_grey", 16))
        self.cat_label = QLabel("CAT inactif")
        self.cat_label.setObjectName("headsmall")
        h.addWidget(self.cat_dot)
        h.addWidget(self.cat_label)
        v.addWidget(head)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("maintabs")
        self.tabs.setIconSize(QSize(22, 22))
        self.tabs.addTab(self._build_qso_tab(), icons.icon("pulse", 22), "QSO")
        self.tabs.addTab(self._build_spots_tab(), icons.icon("pin", 22), "Spots")
        self.tabs.addTab(self._build_op_tab(), icons.icon("bars", 22), "Opération")
        self.stats = QTextBrowser()
        self.tabs.addTab(self.stats, icons.icon("pie", 22), "Statistiques")
        self.tabs.currentChanged.connect(self._tab_changed)
        v.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

    def _build_statusbar(self):
        sb = self.statusBar()
        sb.setObjectName("status")
        sb.setSizeGripEnabled(False)
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(10, 2, 10, 2)
        lay.setSpacing(12)
        self.st_dot = QLabel()
        self.st_dot.setPixmap(icons.pixmap("dot_green", 18))
        self.st_msg = QLabel("Prêt")
        self.st_msg.setObjectName("stmsg")
        self.st_count = QLabel("Enregistrements : 0")
        st_keys = QLabel("Espace : champ suivant · Échap : effacer · ⏎ : enregistrer")
        st_cmds = QLabel("Commandes : 20m · CW · 14.250 · .247 · 5W · OP/ · 14:30 · +15m · NOW · QRV · QRT · SPME")
        st_cmds.setToolTip("Tapez ces commandes dans le champ indicatif puis ⏎ (voir Aide, F1)")
        st_cmds.setMinimumWidth(10)
        lay.addWidget(self.st_dot)
        lay.addWidget(self.st_msg)
        for wdg in (self.st_count, st_keys, st_cmds):
            lay.addWidget(self._vsep())
            lay.addWidget(wdg)
        lay.addStretch(1)
        bars = QLabel()
        bars.setPixmap(icons.pixmap("signal", 26, 80))
        lay.addWidget(bars)
        sb.addPermanentWidget(w, 1)

    def set_status(self, msg, timeout=0):
        self.st_msg.setText(msg)
        if timeout:
            self.status_timer.start(timeout)

    def _build_qso_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 8, 6, 6)
        self.log = QTableWidget(0, 10)
        self.log.setHorizontalHeaderLabels(["Heure", "Indicatif", "Bande", "Fréq.", "Mode", "Env.", "Reçu",
                                            "Réf. P2P", "Nom QTH / Pays", "Notes"])
        self.log.horizontalHeader().setStretchLastSection(True)
        self.log.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for col, wdt in enumerate((72, 112, 72, 84, 66, 58, 62, 104, 210)):
            self.log.setColumnWidth(col, wdt)
        self.log.verticalHeader().hide()
        self.log.verticalHeader().setDefaultSectionSize(32)
        self.log.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.log.setAlternatingRowColors(True)
        self.log.setShowGrid(True)
        self.log.doubleClicked.connect(self.edit_qso)
        v.addWidget(self.log, 1)

        self.info = InfoBar()
        v.addWidget(self.info)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.e_call = QLineEdit()
        self.e_call.setPlaceholderText("Indicatif ou commande")
        self.e_call.setToolTip("Indicatif, ou commande : 20m · 14.250 · CW · .247 · 5W · 14:30 · QRV…")
        self.e_call.setMinimumWidth(180)
        self.e_sent = QLineEdit()
        self.e_rcvd = QLineEdit()
        for e, ph in ((self.e_sent, "Env."), (self.e_rcvd, "Reçu")):
            e.setPlaceholderText(ph)
            e.setFixedWidth(76)
        self.e_p2p_prog = QComboBox()
        self.e_p2p_prog.setObjectName("bigcombo")
        self.e_p2p_prog.addItems(PROGRAM_KEYS)
        self.e_p2p_prog.setFixedWidth(96)
        self.e_p2p = QComboBox()
        self.e_p2p.setObjectName("bigcombo")
        self.e_p2p.setEditable(True)
        self.e_p2p.setInsertPolicy(QComboBox.NoInsert)
        self.e_p2p.lineEdit().setPlaceholderText("Réf. P2P")
        self.e_p2p.setFixedWidth(150)
        self.e_notes = QLineEdit()
        self.e_notes.setPlaceholderText("Notes")
        self.e_notes.setMinimumWidth(140)
        self.b_log = QPushButton("  Enregistrer")
        self.b_log.setObjectName("save")
        self.b_log.setIcon(icons.icon("edit", 26))
        self.b_log.setIconSize(QSize(26, 26))
        self.b_log.setMinimumWidth(170)
        self.b_log.clicked.connect(self.submit)
        for wdg in (self.e_call, self.e_sent, self.e_rcvd, self.e_notes):
            wdg.setObjectName("big")
        for wdg in (self.e_call, self.e_sent, self.e_rcvd, self.e_p2p_prog, self.e_p2p, self.e_notes):
            row.addWidget(wdg)
        row.setStretchFactor(self.e_notes, 1)
        row.addWidget(self.b_log)
        v.addLayout(row)
        self._space = SpaceToNext(self.e_sent)
        self.e_call.installEventFilter(self._space)
        for e in (self.e_call, self.e_sent, self.e_rcvd, self.e_p2p.lineEdit(), self.e_notes):
            e.returnPressed.connect(self.submit)
        self.e_call.textEdited.connect(self._call_edited)
        QShortcut(QKeySequence(Qt.Key_Escape), w, activated=self.clear_entry)
        return w

    def _build_spots_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        row = QHBoxLayout()
        self.spot_filters = {}
        for p in PROGRAM_KEYS:
            cb = QCheckBox(p)
            cb.stateChanged.connect(self.fill_spots)
            self.spot_filters[p] = cb
            row.addWidget(cb)
        self.f_band = QComboBox()
        self.f_band.addItem("Toutes bandes")
        self.f_band.addItems(BAND_NAMES)
        self.f_mode = QComboBox()
        self.f_mode.addItem("Tous modes")
        self.f_mode.addItems(MODES)
        self.f_band.currentIndexChanged.connect(self.fill_spots)
        self.f_mode.currentIndexChanged.connect(self.fill_spots)
        row.addWidget(self.f_band)
        row.addWidget(self.f_mode)
        row.addStretch()
        self.spot_status = QLabel()
        row.addWidget(self.spot_status)
        b = QPushButton("Actualiser")
        b.clicked.connect(self.refresh_spots)
        row.addWidget(b)
        v.addLayout(row)
        self.spot_table = QTableWidget(0, 8)
        self.spot_table.setHorizontalHeaderLabels(["Heure", "Programme", "Indicatif", "Fréq.", "Mode", "Référence",
                                                   "Nom", "Commentaire"])
        self.spot_table.horizontalHeader().setStretchLastSection(True)
        self.spot_table.verticalHeader().hide()
        self.spot_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.spot_table.doubleClicked.connect(self.use_spot)
        v.addWidget(self.spot_table, 1)
        v.addWidget(QLabel("Double-clic sur un spot : la saisie est pré-remplie et, avec le CAT, la radio se cale "
                           "sur la fréquence."))
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        b = QHBoxLayout(box)
        b.addWidget(QLabel("<b>Self-spot</b>"))
        self.spot_comment = QLineEdit()
        self.spot_comment.setPlaceholderText("Commentaire (facultatif)")
        b.addWidget(self.spot_comment, 1)
        for word in ("QRV", "QSY", "QRT"):
            btn = QPushButton(word)
            btn.clicked.connect(lambda _=False, wd=word: self.self_spot(
                (wd + " " + self.spot_comment.text()).strip()))
            b.addWidget(btn)
        sb = QPushButton("Spotter")
        sb.clicked.connect(lambda: self.self_spot(self.spot_comment.text()))
        b.addWidget(sb)
        self.auto_cb = QCheckBox("Auto-spot")
        self.auto_cb.toggled.connect(self._toggle_auto)
        b.addWidget(self.auto_cb)
        v.addWidget(box)
        return w

    def _build_op_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.op_form = OperationForm(self.db, self.s, w)
        v.addWidget(self.op_form, 1)
        row = QHBoxLayout()
        save = QPushButton("Enregistrer l'opération")
        save.clicked.connect(self.save_op_form)
        exp = QPushButton("Exporter les fichiers ADIF")
        exp.clicked.connect(self.export_logs)
        mp = QPushButton("Carte des QSO")
        mp.clicked.connect(self.show_map)
        row.addWidget(save)
        row.addStretch()
        row.addWidget(exp)
        row.addWidget(mp)
        v.addLayout(row)
        return w

    # ------------------------------------------------------------------ réglages / CAT
    def apply_settings(self):
        for p, cb in self.spot_filters.items():
            cb.blockSignals(True)
            cb.setChecked(p in self.s["spots_programs"])
            cb.blockSignals(False)
        self.spot_timer.setInterval(int(self.s["spots_refresh_s"]) * 1000)
        self.lookup = Lookup(self.s)
        self.restart_cat()

    def restart_cat(self):
        if self.cat:
            self.cat.stop()
            self.cat = None
        self.cat_ok = False
        if self.s.get("cat_mode", "aucun") == "aucun":
            self.cat_dot.setPixmap(icons.pixmap("dot_grey", 16))
            self.cat_label.setText("CAT inactif")
            return
        self.cat = CatThread(self.s)
        self.cat.vfo.connect(self._cat_vfo)
        self.cat.status.connect(self._cat_status)
        self.cat.start()

    def _cat_status(self, ok, msg):
        self.cat_ok = ok
        self.cat_dot.setPixmap(icons.pixmap("dot_green" if ok else "dot_red", 16))
        self.cat_label.setText("CAT connecté" if ok else "CAT déconnecté")
        self.cat_label.setToolTip(msg)
        self.set_status(msg, 8000)

    def _cat_vfo(self, khz, mode):
        self.vfo["freq"] = khz
        self.vfo["band"] = band_for_freq(khz) or self.vfo.get("band")
        if mode:
            self.vfo["mode"] = mode
        self._vfo_changed(save=False)

    def closeEvent(self, ev):
        if self.op:
            self.db.update_operation(self.op["id"], vfo=self.vfo)
        if self.cat:
            self.cat.stop()
        super().closeEvent(ev)

    def _first_run(self):
        if not self.s["station_call"]:
            QMessageBox.information(self, "Bienvenue", "Bienvenue dans JCF Portable !\n\nCommencez par indiquer "
                                    "votre indicatif et votre locator, puis téléchargez les listes de références.")
            self.open_settings()
            self.open_data()

    # ------------------------------------------------------------------ opérations
    def load_operations(self, select_id=None):
        self.ops.blockSignals(True)
        self.ops.clear()
        target = None
        for op in self.db.list_operations():
            refs = " ".join(r["ref"] for r in op["refs"]) or "chasse / trafic libre"
            when = parse_iso(op["first_qso"] or op["created"]).strftime("%d/%m/%Y")
            it = QListWidgetItem()
            it.setData(Qt.UserRole, op["id"])
            row = QWidget()
            row.setObjectName("opitem")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 8, 8, 8)
            rl.setSpacing(10)
            ic = QLabel()
            ic.setPixmap(icons.pixmap("calendar", 30))
            txt = QVBoxLayout()
            txt.setSpacing(1)
            t1 = QLabel(op["title"])
            t1.setObjectName("optitleitem")
            t2 = QLabel(f"{when} · {op['qso_count']} QSO · {refs}")
            t2.setObjectName("opsubitem")
            txt.addWidget(t1)
            txt.addWidget(t2)
            rl.addWidget(ic)
            rl.addLayout(txt, 1)
            row.setAttribute(Qt.WA_TransparentForMouseEvents)
            it.setSizeHint(QSize(200, 62))
            self.ops.addItem(it)
            self.ops.setItemWidget(it, row)
            if op["id"] == (select_id or (self.op and self.op["id"])):
                target = it
        self.ops.blockSignals(False)
        if target is None and self.ops.count():
            target = self.ops.item(0)
        if target:
            self.ops.setCurrentItem(target)
            self.select_operation(target.data(Qt.UserRole))
        else:
            self.op = None
            self.refresh_op_view()

    def select_operation(self, op_id):
        if self.op and self.op["id"] != op_id:
            self.db.update_operation(self.op["id"], vfo=self.vfo)
        self.op = self.db.get_operation(op_id)
        if not self.op:
            return
        saved = self.op.get("vfo") or {}
        if not self.cat_ok:
            self.vfo = dict(saved)
        else:
            self.vfo.update({k: v for k, v in saved.items() if k in ("power", "operator")})
        self.vfo.setdefault("power", self.op.get("power") or self.s["power"])
        self.vfo.setdefault("operator", self.op.get("operator_call") or self.op.get("station_call"))
        self.vfo.setdefault("mode", "SSB")
        acts = [r["program"] for r in self.op["refs"]]
        if acts:
            self.e_p2p_prog.setCurrentText(acts[0])
        self.op_form.load(self.op)
        self.refresh_op_view()
        self.e_call.setFocus()

    def refresh_op_view(self):
        if not self.op:
            self.op_title.setText("Aucune opération — Ctrl+N pour en créer une")
            self.op_refs.setText("")
            self.log.setRowCount(0)
            self.st_count.setText("Enregistrements : 0")
            self.banner.set_call(self.s["station_call"])
            self._vfo_changed(save=False)
            return
        self.qsos = self.db.list_qsos(self.op["id"])
        self.op_title.setText(f"{self.op['title']} — {self.op['station_call']}")
        self.banner.set_call(self.op["station_call"] or self.s["station_call"])
        live = [q for q in self.qsos if not q["deleted"]]
        self.st_count.setText(f"Enregistrements : {len(live)}")
        parts = [f"{len(live)} QSO"]
        for r in self.op["refs"]:
            thr = PROGRAMS.get(r["program"], {}).get("threshold", 10)
            n = len({q["call"] for q in live})
            color = "#5ee05a" if n >= thr else "#ffb340"
            parts.append(f"<span style='color:{color}'><b>{r['program']} {r['ref']}</b> {n}/{thr}</span>")
        self.op_refs.setText("  ·  ".join(parts))
        self.fill_log()
        self._vfo_changed(save=False)
        if self.tabs.currentIndex() == 3:
            self.fill_stats()

    def fill_log(self):
        self.log.setRowCount(0)
        strike = QFont()
        strike.setStrikeOut(True)
        for q in self.qsos:
            i = self.log.rowCount()
            self.log.insertRow(i)
            t = parse_iso(q["start"])
            vals = [t.strftime("%H:%M"), q["call"], q["band"] or "", fmt_freq(q["freq"]) if q["freq"] else "",
                    q["mode"] or "", q["rst_sent"], q["rst_rcvd"],
                    " ".join(r["ref"] for r in q["their_refs"]),
                    " · ".join(x for x in (q["name"], q["qth"], q["country"]) if x), q["notes"]]
            for c, val in enumerate(vals):
                it = _item(val, q["id"])
                if q["deleted"]:
                    it.setFont(strike)
                    it.setForeground(QColor("gray"))
                self.log.setItem(i, c, it)
        self.log.scrollToBottom()

    def new_operation(self):
        dlg = OperationDialog(self.db, self.s, None, self)
        if dlg.exec():
            v = dlg.form.values()
            op_id = self.db.create_operation(**v)
            self.load_operations(op_id)
            self.tabs.setCurrentIndex(0)

    def duplicate_operation(self):
        if not self.op:
            return
        new_id = self.db.duplicate_operation(self.op["id"])
        self.load_operations(new_id)
        dlg = OperationDialog(self.db, self.s, self.db.get_operation(new_id), self)
        if dlg.exec():
            self.db.update_operation(new_id, **dlg.form.values())
            self.load_operations(new_id)

    def delete_operation(self):
        if not self.op:
            return
        n = len([q for q in self.qsos if not q["deleted"]])
        if QMessageBox.question(self, "Supprimer", f"Supprimer l'opération « {self.op['title']} » ({n} QSO) ?") \
                == QMessageBox.Yes:
            self.db.delete_operation(self.op["id"])
            self.op = None
            self.load_operations()

    def save_op_form(self):
        if not self.op:
            return
        v = self.op_form.values()
        self.db.update_operation(self.op["id"], **v)
        self.op = self.db.get_operation(self.op["id"])
        self.load_operations(self.op["id"])
        self.set_status("Opération enregistrée", 4000)

    # ------------------------------------------------------------------ horloge / VFO
    def current_time(self):
        return self.frozen or now_utc()

    def _set_frozen(self, dt):
        self.frozen = dt
        self._tick()

    def _tick(self):
        t = self.current_time()
        if self.frozen:
            self.clock_label.setText(f"<span style='color:#ff6b5a'>⏸ {t.strftime('%d/%m %H:%M:%S')} UTC</span>")
        else:
            self.clock_label.setText(f"{t.strftime('%H:%M:%S')} UTC")

    def _vfo_changed(self, save=True):
        f = self.vfo.get("freq")
        band = self.vfo.get("band") or "—"
        txt = f"{fmt_freq(f)} MHz · " if f else (f"{band} · " if band != "—" else "")
        txt += f"{self.vfo.get('mode', '')} {self.vfo.get('power', '')} W"
        if self.op and self.vfo.get("operator") and self.vfo.get("operator") != \
                (self.op.get("operator_call") or self.op.get("station_call")):
            txt += f" · op {self.vfo['operator']}"
        self.vfo_label.setText(txt)
        mode = self.vfo.get("mode", "SSB")
        self.e_sent.setPlaceholderText(default_rst(mode))
        self.e_rcvd.setPlaceholderText(default_rst(mode))
        if save and self.op:
            self.db.update_operation(self.op["id"], vfo=self.vfo)

    def tune(self, khz=None, mode=None):
        if khz:
            self.vfo["freq"] = khz
            self.vfo["band"] = band_for_freq(khz)
        if mode:
            self.vfo["mode"] = mode
        if self.cat and self.cat_ok:
            self.cat.tune(khz, mode)
        self._vfo_changed()

    # ------------------------------------------------------------------ saisie
    def clear_entry(self):
        for e in (self.e_call, self.e_sent, self.e_rcvd, self.e_notes):
            e.clear()
        self.e_p2p.clear()
        self.e_p2p.setEditText("")
        self.lookup_data = {}
        self.info.setText(" ")
        self.e_call.setFocus()

    def flash(self, msg, error=False):
        color = "#ff6b5a" if error else "#5ee05a"
        self.info.setText(f"<span style='color:{color}'>{msg}</span>")

    def apply_command(self, cmd):
        k = cmd.kind
        if k == "error":
            self.flash(cmd.message, True)
            return
        if k == "band":
            f = default_freq_for_band(cmd.value)
            if self.cat_ok:
                self.tune(f, None)
            else:
                self.vfo["band"] = cmd.value
                self.vfo["freq"] = None
                self._vfo_changed()
        elif k == "mode":
            self.tune(None, cmd.value)
        elif k == "freq":
            self.tune(cmd.value, None)
        elif k == "power":
            self.vfo["power"] = cmd.value
            self._vfo_changed()
        elif k == "operator":
            self.vfo["operator"] = cmd.value
            self._vfo_changed()
        elif k == "time":
            base = self.frozen or now_utc()
            hh, mm, ss = cmd.value
            self._set_frozen(base.replace(hour=hh, minute=mm, second=ss))
        elif k == "date":
            base = self.frozen or now_utc()
            y, mo, d = cmd.value
            try:
                self._set_frozen(base.replace(year=y or base.year, month=mo, day=d))
            except ValueError:
                self.flash("Date invalide", True)
                return
        elif k == "offset":
            self._set_frozen((self.frozen or now_utc()) + cmd.value)
        elif k == "now":
            self._set_frozen(None)
        elif k == "spot":
            self.self_spot(cmd.value)
        self.flash("✓ " + cmd.message)

    def submit(self):
        text = self.e_call.text().strip()
        if not text:
            return
        cmd = commands.parse(text, self.vfo.get("freq"))
        if cmd:
            self.apply_command(cmd)
            self.e_call.clear()
            self.e_call.setFocus()
            return
        if not self.op:
            QMessageBox.information(self, "Opération", "Créez d'abord une opération (Ctrl+N).")
            return
        if not self.vfo.get("band"):
            self.flash("Choisissez d'abord une bande ou une fréquence : tapez par ex. 20m ou 14.250 puis ⏎", True)
            return
        calls = commands.split_calls(text)
        mode = self.vfo.get("mode", "SSB")
        their_refs = []
        if self.e_p2p.currentText().strip():
            prog = self.e_p2p_prog.currentText()
            ref, _ = expand_ref(self.db, prog, self.e_p2p.currentText(), self.s["default_prefix"].get(prog, ""))
            their_refs = [{"program": prog, "ref": ref}]
        for n, call in enumerate(calls):
            info = self.lookup_data if (len(calls) == 1 and self.lookup_data.get("call") == call) else \
                (self.db.cached_call(call) or {})
            t = self.current_time()
            self.db.add_qso(self.op["id"], call=call, start=iso(t), freq=self.vfo.get("freq"),
                            band=self.vfo.get("band"), mode=mode,
                            rst_sent=self.e_sent.text().strip() or default_rst(mode),
                            rst_rcvd=self.e_rcvd.text().strip() or default_rst(mode),
                            their_refs=their_refs, name=info.get("name", ""), qth=info.get("qth", ""),
                            country=info.get("country", ""), their_grid=info.get("grid", ""),
                            notes=self.e_notes.text().strip(), operator_call=self.vfo.get("operator", ""),
                            power=self.vfo.get("power", ""))
            if self.frozen:
                self.frozen = self.frozen + timedelta(minutes=1)
            if not info and self.lookup.service != "aucun":
                run_bg(self._fetch_lookup, call, on_result=self._fill_lookup_later)
        msg = f"✓ {', '.join(calls)} enregistré{'s' if len(calls) > 1 else ''}"
        bad = [c for c in calls if not commands.looks_like_call(c)]
        self.clear_entry()
        self.flash(msg + (f" — ⚠ indicatif inhabituel : {', '.join(bad)}" if bad else ""))
        self.refresh_op_view()
        self.load_operations(self.op["id"])

    def _call_edited(self, text):
        t = text.strip().upper()
        if not t or commands.parse(t, self.vfo.get("freq")) or "," in t:
            self.info.setText(" ")
            return
        self.lookup_timer.start()

    def _lookup_now(self):
        call = commands.split_calls(self.e_call.text())
        if len(call) != 1:
            return
        call = call[0]
        self.lookup_data = {"call": call}
        self._show_info(call)
        cached = self.db.cached_call(call)
        if cached:
            self.lookup_data.update(cached)
            self._show_info(call)
        elif self.lookup.service != "aucun":
            run_bg(self._fetch_lookup, call, on_result=self._lookup_result)

    def _fetch_lookup(self, call):
        data = self.lookup.lookup(call.split("/")[0] if len(call.split("/")[0]) > 2 else call)
        if data:
            self.db.cache_call(call, data)
        return call, data

    def _lookup_result(self, res):
        call, data = res
        if data and self.lookup_data.get("call") == call:
            self.lookup_data.update(data)
            self._show_info(call)

    def _fill_lookup_later(self, res):
        call, data = res
        if not data or not self.op:
            return
        for q in self.db.list_qsos(self.op["id"]):
            if q["call"] == call and not q["name"] and not q["country"]:
                self.db.update_qso(q["id"], name=data.get("name", ""), qth=data.get("qth", ""),
                                   country=data.get("country", ""), their_grid=data.get("grid", ""))
        self.refresh_op_view()

    def _show_info(self, call):
        d = self.lookup_data
        parts = []
        ident = " - ".join(x for x in (d.get("name"), d.get("qth"), d.get("country")) if x)
        if ident:
            parts.append(f"<b>{ident}</b>")
        if d.get("grid") and self.op and self.op.get("grid"):
            db_ = grid_distance(self.op["grid"], d["grid"])
            if db_:
                parts.append(f"{d['grid']} — {db_[0]:.0f} km, cap {db_[1]:.0f}°")
        prev = self.db.previous_contacts(call, exclude_op=self.op["id"] if self.op else None)
        if prev:
            parts.append(f"déjà contacté {len(prev)} fois (dernier : {parse_iso(prev[0]).strftime('%d/%m/%Y')})")
        if self.op:
            band, mode = self.vfo.get("band"), self.vfo.get("mode")
            dupe = [q for q in self.qsos if not q["deleted"] and q["call"] == call]
            if any(q["band"] == band and q["mode"] == mode for q in dupe):
                parts.append("<span style='color:#ff6b5a'><b>DOUBLON</b> sur cette bande et ce mode</span>")
            elif dupe:
                parts.append(f"déjà dans ce log ({', '.join(q['band'] or '?' for q in dupe)})")
        self.info.show_call(call, icons.flag(d.get("country")), "  ·  ".join(parts))

    def edit_qso(self, index):
        qso_id = self.log.item(index.row(), 0).data(Qt.UserRole)
        q = self.db.get_qso(qso_id)
        dlg = QsoEditDialog(q, self)
        if dlg.exec() and dlg.action:
            self.db.update_qso(qso_id, **dlg.action[1])
            self.refresh_op_view()
            self.load_operations(self.op["id"])

    # ------------------------------------------------------------------ spots
    def _tab_changed(self, idx):
        if idx == 1:
            if not self.spots_list:
                self.refresh_spots()
            self.spot_timer.start()
        else:
            self.spot_timer.stop()
        if idx == 3:
            self.fill_stats()

    def refresh_spots(self):
        progs = [p for p, cb in self.spot_filters.items() if cb.isChecked()]
        self.spot_status.setText("Chargement…")
        if "GMA" in progs and not self.s.get("gma_read_key"):
            progs = [p for p in progs if p != "GMA"]
        run_bg(spots.fetch_all, progs, int(self.s["spots_max_age_min"]), self._gma_keys(),
               on_result=self._spots_loaded,
               on_error=lambda e: self.spot_status.setText(f"⚠ {e}"))

    def _gma_keys(self):
        return {"gma_read": self.s.get("gma_read_key", ""), "gms_submit": self.s.get("gma_submit_key", "")}

    def _spots_loaded(self, res):
        self.spots_list, errors = res
        stamp = datetime.now(timezone.utc).strftime("%H:%M UTC")
        self.spot_status.setText(f"{len(self.spots_list)} spots à {stamp}"
                                 + (f" — ⚠ {'; '.join(errors)}" if errors else ""))
        self.spot_status.setToolTip("\n".join(errors))
        self.fill_spots()

    def fill_spots(self):
        progs = {p for p, cb in self.spot_filters.items() if cb.isChecked()}
        band = self.f_band.currentText() if self.f_band.currentIndex() > 0 else None
        mode = self.f_mode.currentText() if self.f_mode.currentIndex() > 0 else None
        worked = {q["call"] for q in self.qsos if not q["deleted"]}
        self.spot_table.setRowCount(0)
        for s in self.spots_list:
            if s.program not in progs or (band and s.band != band) or (mode and s.mode != mode):
                continue
            i = self.spot_table.rowCount()
            self.spot_table.insertRow(i)
            vals = [s.time.strftime("%H:%M"), s.program, s.call, fmt_freq(s.freq), s.mode, s.ref, s.name, s.comment]
            for c, v in enumerate(vals):
                it = _item(v, i)
                it.setData(Qt.UserRole, self.spots_list.index(s))
                if s.call in worked:
                    it.setForeground(QColor("gray"))
                self.spot_table.setItem(i, c, it)
        self.spot_table.resizeColumnsToContents()

    def use_spot(self, index):
        s = self.spots_list[self.spot_table.item(index.row(), 0).data(Qt.UserRole)]
        self.tune(s.freq or None, s.mode if s.mode in MODES else None)
        self.tabs.setCurrentIndex(0)
        self.clear_entry()
        self.e_call.setText(s.call)
        if s.ref:
            self.e_p2p_prog.setCurrentText(s.program)
            self.e_p2p.clear()
            self.e_p2p.addItems(s.ref.split())
            self.e_p2p.setEditText(s.ref.split()[0])
        self._lookup_now()
        self.e_sent.setFocus()

    def self_spot(self, comment, auto=False):
        if not self.op:
            self.flash("Pas d'opération en cours", True)
            return
        f = self.vfo.get("freq")
        if not f:
            self.flash("Indiquez la fréquence exacte avant de vous spotter (ex. 14.285)", True)
            return
        acts = {}
        for r in self.op["refs"]:
            acts.setdefault(r["program"], []).append(r["ref"])
        if not acts:
            self.flash("Aucune référence activée dans cette opération", True)
            return
        call = self.op["station_call"]
        mode = self.vfo.get("mode", "SSB")

        def job():
            results = []
            for prog, refs in acts.items():
                extra = f"{len(refs)}-fer: {' '.join(refs)}" if prog == "POTA" and len(refs) > 1 else ""
                err = spots.post_spot(prog, call, call, f, mode, refs[0], " ".join(x for x in (comment, extra) if x),
                                      keys=self._gma_keys())
                results.append(f"{prog} ✗ {err}" if err else f"{prog} ✓")
            return results

        def done(results):
            ok = all("✓" in r for r in results)
            self.flash(("Auto-spot : " if auto else "Spot : ") + " · ".join(results), not ok)
            self.set_status(" · ".join(results), 10000)

        run_bg(job, on_result=done, on_error=lambda e: self.flash(f"Spot impossible : {e}", True))

    def _toggle_auto(self, on):
        if on:
            self.auto_timer.start(int(self.s["autospot_interval_min"]) * 60000)
            self.self_spot("", auto=True)
        else:
            self.auto_timer.stop()

    # ------------------------------------------------------------------ stats / export / carte
    def fill_stats(self):
        if not self.op:
            self.stats.setHtml("")
            return
        live = [q for q in self.qsos if not q["deleted"]]
        calls = {q["call"] for q in live}
        by_band = Counter(q["band"] or "?" for q in live)
        by_mode = Counter(q["mode"] or "?" for q in live)
        by_day = Counter(q["start"][:10] for q in live)
        p2p = [q for q in live if q["their_refs"]]
        html = [f"<h2>{self.op['title']}</h2><p><b>{len(live)}</b> QSO, <b>{len(calls)}</b> indicatifs différents, "
                f"<b>{len(p2p)}</b> contacts P2P/S2S.</p>"]
        if live:
            t0, t1 = parse_iso(live[0]["start"]), parse_iso(live[-1]["start"])
            mins = max(1, (t1 - t0).total_seconds() / 60)
            html.append(f"<p>De {t0.strftime('%H:%M')} à {t1.strftime('%H:%M')} UTC — "
                        f"{len(live) / mins * 60:.0f} QSO/heure en moyenne.</p>")
        html.append("<h3>Validation des activations</h3><ul>")
        for r in self.op["refs"]:
            thr = PROGRAMS.get(r["program"], {}).get("threshold", 10)
            if r["program"] == "POTA":
                for day, _ in sorted(by_day.items()):
                    n = len({q["call"] for q in live if q["start"].startswith(day)})
                    html.append(f"<li>POTA {r['ref']} — {day} UTC : {n}/{thr} "
                                f"{'✅ validée' if n >= thr else '⏳'}</li>")
            else:
                html.append(f"<li>{r['program']} {r['ref']} : {len(calls)}/{thr} "
                            f"{'✅ validée' if len(calls) >= thr else '⏳'}</li>")
        html.append("</ul><h3>Par bande</h3><ul>")
        html += [f"<li>{b} : {n}</li>" for b, n in sorted(by_band.items(), key=lambda x: -x[1])]
        html.append("</ul><h3>Par mode</h3><ul>")
        html += [f"<li>{m} : {n}</li>" for m, n in sorted(by_mode.items(), key=lambda x: -x[1])]
        html.append("</ul>")
        if p2p:
            html.append("<h3>Contacts P2P / S2S</h3><ul>")
            html += [f"<li>{q['call']} — {' '.join(r['program'] + ' ' + r['ref'] for r in q['their_refs'])}</li>"
                     for q in p2p]
            html.append("</ul>")
        self.stats.setHtml("".join(html))

    def export_logs(self):
        if not self.op:
            return
        live = [q for q in self.qsos if not q["deleted"]]
        if not live:
            QMessageBox.information(self, "Export", "Aucun QSO à exporter.")
            return
        folder = Path(self.s["export_dir"]).expanduser() / adif.safe_name(self.op["title"])
        try:
            paths = adif.export_operation(self.op, self.qsos, folder)
        except OSError as e:
            QMessageBox.critical(self, "Export", f"Écriture impossible : {e}")
            return
        box = QMessageBox(self)
        box.setWindowTitle("Export ADIF")
        box.setText(f"{len(paths)} fichier(s) créé(s) dans :\n{folder}\n\n"
                    + "\n".join("• " + p.name for p in paths)
                    + "\n\nLes fichiers « @référence » sont à envoyer au programme (POTA, WWFF…) ; "
                      "le fichier « complet » est à importer dans votre carnet (JCFLog, QLog…).")
        open_b = box.addButton("Ouvrir le dossier", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        box.exec()
        if box.clickedButton() == open_b:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def show_map(self):
        if not self.op:
            return
        path, n = maps.build_map(self.op, self.qsos)
        if n == 0:
            self.set_status("Aucun QSO localisé (la recherche d'indicatif fournit les locators)", 8000)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # ------------------------------------------------------------------ fenêtres
    def open_settings(self):
        if SettingsDialog(self.s, self).exec():
            self.apply_settings()
            self.refresh_op_view()

    def open_data(self):
        DataDialog(self.db, self).exec()

    def show_help(self):
        QMessageBox.information(self, "Aide", f"""<h3>{APP_NAME} {VERSION}</h3>
<p>Carnet d'activation portable inspiré de Ham2K PoLo.</p>
<p><b>Démarrer :</b> Ctrl+N crée une opération (ajoutez la référence du parc ou du sommet), tapez la bande
(<code>20m</code>) ou la fréquence (<code>14.285</code>), puis les indicatifs.</p>
<p><b>Commandes dans le champ indicatif :</b><br>
<code>20m</code> bande · <code>CW</code> mode · <code>14.070</code> fréquence · <code>.247</code> derniers chiffres ·
<code>5W</code> puissance · <code>OP/F4XXX</code> opérateur · <code>14:30</code>, <code>05-09</code>,
<code>+15m</code> heure/date (saisie a posteriori) · <code>NOW</code> heure actuelle ·
<code>QRV</code> <code>QSY</code> <code>QRT</code> <code>SPME</code> self-spot.</p>
<p><b>Raccourcis :</b> Espace = champ suivant, ⏎ = enregistrer, Échap = effacer, virgules = plusieurs QSO,
« . » = « / ». Réf. P2P : tapez juste le numéro (<code>2518</code>).</p>
<p>Double-clic sur un QSO pour le corriger ou le supprimer (il reste barré et peut être restauré).</p>
<p>Carnet : {data_dir()}<br>Réglages : {config_dir()}</p>
<p>Licence GPL v3 — F4JCF.</p>""")
