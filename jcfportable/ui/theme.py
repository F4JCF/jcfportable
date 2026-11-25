"""Thème visuel JCF Portable : bleu nuit, bordures lumineuses, accents orange (d'après la maquette F4JCF)."""
from pathlib import Path

from PySide6.QtGui import QColor, QPalette

ASSETS = Path(__file__).resolve().parent.parent / "assets"

QSS = """
* { font-family: "Segoe UI", "Noto Sans", "Ubuntu", sans-serif; }
QWidget { color: #eaf4ff; font-size: 10pt; }
QMainWindow { background: #05132a; }
QWidget#central { background: #05132a; }

/* ---------- barre d'outils + bandeau ---------- */
QToolBar#maintoolbar {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #0f3c70, stop:0.5 #0b2f5c, stop:1 #071c3a);
    border: 0; border-bottom: 2px solid #1d8cf0; spacing: 0px; padding: 6px 6px 6px 8px;
}
QToolBar#maintoolbar QToolButton {
    color: #ffffff; font-size: 10pt; font-weight: 600;
    background: transparent; border: 1px solid transparent; border-right: 1px solid #1a4f86;
    border-radius: 0px; padding: 6px 10px 4px 10px; margin: 0px;
}
QToolBar#maintoolbar QToolButton#primary {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #1d6fc4, stop:1 #0c3f7a);
    border: 2px solid #49b3ff; border-radius: 8px; margin-right: 6px;
}
QToolBar#maintoolbar QToolButton:hover { background: #164f8c; border: 1px solid #4fb6ff; border-radius: 8px; }
QToolBar#maintoolbar QToolButton:pressed { background: #f28c0f; color: #05132a; border-radius: 8px; }

/* ---------- panneau Opérations ---------- */
QDockWidget#opsdock { border: 0; }
QWidget#docktitle {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #123f73, stop:1 #0b2a50);
    border: 1px solid #1f6fc2; border-top-left-radius: 8px; border-top-right-radius: 8px;
}
QLabel#docktitletext { font-size: 13pt; font-weight: bold; color: #ffffff; }
QWidget#dockbody {
    background: #071a35; border: 1px solid #1f6fc2; border-top: 0;
    border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;
}
QListWidget#opslist { background: transparent; border: 0; padding: 4px; outline: 0; }
QListWidget#opslist::item { border: 0; margin: 2px 2px; border-radius: 4px; }
QListWidget#opslist::item:selected {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1a73cf, stop:1 #0f56a8);
    border: 1px solid #4fb6ff;
}
QListWidget#opslist::item:hover:!selected { background: #0f3462; }
QLabel#optitleitem { font-size: 11pt; font-weight: 600; color: #ffffff; background: transparent; }
QLabel#opsubitem { font-size: 8pt; color: #cfe4fb; background: transparent; }
QWidget#opitem { background: transparent; }
QLabel#sideart { background: transparent; padding: 0; }

/* ---------- bandeau de l'opération ---------- */
QFrame#header {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #0c2a52, stop:1 #071c3a);
    border: 1px solid #1f6fc2; border-radius: 8px;
}
QLabel#optitle { font-size: 17pt; font-weight: bold; color: #ffffff; background: transparent; }
QLabel#opsub { font-size: 9pt; color: #cfe4fb; background: transparent; }
QLabel#headval { font-size: 13pt; font-weight: bold; color: #ffffff; background: transparent; }
QLabel#headsmall { font-size: 10pt; color: #e6f1ff; background: transparent; }
QFrame#vsep { background: #2a6db5; border: 0; }

/* ---------- onglets ---------- */
QTabWidget#maintabs::pane {
    border: 1px solid #1f6fc2; border-radius: 8px; background: #071a35; top: -1px;
}
QTabWidget#maintabs > QTabBar::tab {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #164a85, stop:1 #0b2c55);
    color: #ffffff; font-size: 11pt; font-weight: 600;
    border: 1px solid #2a76c9; border-bottom: 0;
    padding: 9px 26px 9px 18px; margin-right: 4px; min-width: 90px;
    border-top-left-radius: 8px; border-top-right-radius: 22px;
}
QTabWidget#maintabs > QTabBar::tab:selected {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffbe3b, stop:1 #f08a00);
    color: #1b0d00; border: 1px solid #ffd27a; border-bottom: 0;
}
QTabWidget#maintabs > QTabBar::tab:hover:!selected { background: #1b5a9e; }
QTabBar::tab {
    background: #0f3462; color: #eaf4ff; border: 1px solid #2a76c9; padding: 7px 14px;
    border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px;
}
QTabBar::tab:selected { background: #f49a12; color: #1b0d00; font-weight: bold; }
QTabWidget::pane { border: 1px solid #1f6fc2; background: #071a35; }

/* ---------- tableaux ---------- */
QTableWidget, QTextBrowser, QListWidget {
    background: #061630; alternate-background-color: #0a1f3d;
    border: 1px solid #1f6fc2; border-radius: 6px;
    gridline-color: #15365f; selection-background-color: #1569c4; selection-color: #ffffff;
}
QHeaderView { background: transparent; }
QHeaderView::section {
    color: #ffffff; font-size: 10.5pt; font-weight: bold; padding: 8px 10px;
    border: 0; border-right: 1px solid #2a6db5; border-bottom: 1px solid #2a6db5;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #1d5fa6, stop:1 #0e3a70);
}
QTableCornerButton::section { background: #0e3a70; border: 0; }

/* ---------- ligne d'info ---------- */
QFrame#infobar {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #0d2b52, stop:1 #091f3e);
    border: 1px solid #1f6fc2; border-radius: 6px;
}
QFrame#infobar QLabel { background: transparent; font-size: 10.5pt; }
QFrame#infobar QLabel#infocall { font-size: 15pt; font-weight: bold; color: #ffffff; }

/* ---------- champs de saisie ---------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateTimeEdit {
    background: #051327; color: #f1f7ff; border: 1px solid #2f7fd0;
    border-radius: 6px; padding: 6px 9px; selection-background-color: #1569c4; min-height: 22px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 2px solid #4fb6ff; }
QLineEdit#big { font-size: 15pt; font-weight: 600; padding: 7px 8px; min-height: 30px; }
QComboBox#bigcombo { font-size: 13pt; font-weight: 600; min-height: 30px;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #144a86, stop:1 #0b2d57); }
QComboBox#bigcombo QLineEdit { background: transparent; border: 0; font-size: 13pt; font-weight: 600; }
QComboBox::drop-down { border: 0; width: 26px; }
QComboBox::down-arrow { image: url(@ARROW@); width: 14px; height: 9px; }
QComboBox QAbstractItemView { background: #0a2446; border: 1px solid #2f7fd0; selection-background-color: #1569c4; }

/* ---------- boutons ---------- */
QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #1c6cc0, stop:1 #0c3b72);
    color: #ffffff; border: 1px solid #3a9bf0; border-radius: 6px; padding: 7px 14px; font-weight: 600;
}
QPushButton:hover { background: #1f7ad6; border: 1px solid #7cc8ff; }
QPushButton:pressed { background: #f28c0f; color: #1b0d00; }
QPushButton#save {
    font-size: 15pt; font-weight: bold; color: #ffffff; padding: 8px 22px; min-height: 30px;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffae2e, stop:0.5 #f58a0a, stop:1 #e06d00);
    border: 1px solid #ffd27a; border-radius: 8px;
}
QPushButton#save:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffc04f, stop:1 #f07800); }
QPushButton#save:pressed { background: #c85f00; }

/* ---------- barre d'état ---------- */
QStatusBar#status {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #0a2140, stop:1 #061630);
    border-top: 1px solid #1f6fc2; min-height: 34px;
}
QStatusBar#status QLabel { background: transparent; color: #e6f1ff; font-size: 9.5pt; }
QLabel#stmsg { font-weight: bold; }
QStatusBar::item { border: 0; }

/* ---------- divers ---------- */
QGroupBox { border: 1px solid #1f6fc2; border-radius: 6px; margin-top: 14px; padding-top: 6px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; color: #9fd2ff; }
QFrame[frameShape="6"] { border: 1px solid #1f6fc2; border-radius: 6px; background: #0a2142; }
QCheckBox { spacing: 7px; background: transparent; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #3a9bf0; border-radius: 3px; background: #051327; }
QCheckBox::indicator:checked { background: #f49a12; border: 1px solid #ffd27a; }
QToolTip { background: #0f2d52; color: #ffffff; border: 1px solid #4fb6ff; padding: 5px; }
QDialog { background: #071a35; }
QProgressBar { border: 1px solid #2f7fd0; border-radius: 5px; background: #051327; text-align: center; }
QProgressBar::chunk { background: #f49a12; border-radius: 4px; }
QScrollBar:vertical { background: #061630; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: #1f5fa0; min-height: 25px; border-radius: 5px; }
QScrollBar:horizontal { background: #061630; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: #1f5fa0; min-width: 25px; border-radius: 5px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QMessageBox { background: #071a35; }
"""


def apply_theme(app):
    app.setStyle("Fusion")
    p = app.palette()
    for role, col in ((QPalette.Window, "#05132a"), (QPalette.WindowText, "#eaf4ff"), (QPalette.Base, "#061630"),
                      (QPalette.AlternateBase, "#0a1f3d"), (QPalette.ToolTipBase, "#0f2d52"),
                      (QPalette.ToolTipText, "#ffffff"), (QPalette.Text, "#eaf4ff"), (QPalette.Button, "#12375c"),
                      (QPalette.ButtonText, "#ffffff"), (QPalette.Highlight, "#1569c4"),
                      (QPalette.HighlightedText, "#ffffff"), (QPalette.PlaceholderText, "#7f9bbb"),
                      (QPalette.Link, "#7cc8ff")):
        p.setColor(role, QColor(col))
    app.setPalette(p)
    app.setStyleSheet(QSS.replace("@ARROW@", (ASSETS / "arrow_down.png").as_posix()))
