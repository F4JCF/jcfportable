"""Thème visuel professionnel JCF Portable."""
from PySide6.QtGui import QColor, QPalette


def apply_theme(app):
    app.setStyle("Fusion")
    p = app.palette()
    p.setColor(QPalette.Window, QColor("#071629"))
    p.setColor(QPalette.WindowText, QColor("#eaf4ff"))
    p.setColor(QPalette.Base, QColor("#081a2d"))
    p.setColor(QPalette.AlternateBase, QColor("#0d2239"))
    p.setColor(QPalette.ToolTipBase, QColor("#102c49"))
    p.setColor(QPalette.ToolTipText, QColor("#f2f8ff"))
    p.setColor(QPalette.Text, QColor("#eaf4ff"))
    p.setColor(QPalette.Button, QColor("#12375c"))
    p.setColor(QPalette.ButtonText, QColor("#f3f8ff"))
    p.setColor(QPalette.Highlight, QColor("#087bd5"))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(p)
    app.setStyleSheet("""
    QWidget { color: #eaf4ff; font-family: "Segoe UI"; font-size: 10pt; }
    QMainWindow, QWidget#qt_central_widget { background: #071629; }
    QToolBar {
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #123e68, stop:1 #071a30);
        border: 0; border-bottom: 2px solid #168de2; spacing: 8px;
        padding: 8px 10px;
    }
    QToolButton {
        color: #f3f8ff; background: transparent; border: 1px solid transparent;
        border-radius: 7px; padding: 9px 12px; min-height: 34px;
    }
    QToolButton:hover { background: #174b78; border: 1px solid #269ff4; }
    QToolButton:pressed { background: #e88708; color: #071629; }
    QDockWidget { color: #f3f8ff; font-weight: bold; }
    QDockWidget::title {
        background: #10365b; padding: 9px; border: 1px solid #1765a3;
    }
    QListWidget, QTableWidget, QTextBrowser {
        background: #081a2d; alternate-background-color: #0d2742;
        border: 1px solid #1765a3; border-radius: 7px;
        gridline-color: #173b5d; selection-background-color: #075fa8;
    }
    QListWidget::item { padding: 10px 7px; border-bottom: 1px solid #173b5d; }
    QListWidget::item:selected { background: #075fa8; border-left: 4px solid #ff9b13; }
    QHeaderView::section {
        color: #f4f9ff; font-weight: bold; padding: 8px 6px;
        border: 1px solid #1765a3;
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #15558a, stop:1 #0b2b4b);
    }
    QTabWidget::pane { border: 1px solid #1765a3; background: #081a2d; top: -1px; }
    QTabBar::tab {
        background: #102d4b; color: #d9ebfb; border: 1px solid #1a5d91;
        padding: 9px 17px; margin-right: 3px; border-top-left-radius: 7px;
        border-top-right-radius: 7px;
    }
    QTabBar::tab:selected { background: #f49a12; color: #071629; font-weight: bold; }
    QTabBar::tab:hover:!selected { background: #174b78; }
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
        background: #061426; color: #f1f7ff; border: 1px solid #247fbd;
        border-radius: 5px; padding: 7px 9px; selection-background-color: #087bd5;
        min-height: 22px;
    }
    QLineEdit:focus, QComboBox:focus { border: 2px solid #21a5ff; }
    QLineEdit::placeholder { color: #829bb4; }
    QPushButton {
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #1766a4, stop:1 #0b3156);
        color: #ffffff; border: 1px solid #2798e7; border-radius: 6px;
        padding: 8px 13px; font-weight: 600;
    }
    QPushButton:hover { background: #1b79bf; border: 1px solid #69c2ff; }
    QPushButton:pressed { background: #e88708; color: #071629; }
    QStatusBar { background: #061426; color: #bcd8f1; border-top: 1px solid #1765a3; }
    QStatusBar::item { border: 0; }
    QCheckBox { spacing: 7px; }
    QCheckBox::indicator { width: 16px; height: 16px; }
    QToolTip { background: #102c49; color: #ffffff; border: 1px solid #269ff4; padding: 5px; }
    /* Gros caractères pour la saisie et le bandeau, lisibles sur le terrain */
    QLineEdit#big, QPushButton#big, QLabel#big { font-size: 15pt; }
    QLabel#titre { font-size: 13pt; font-weight: bold; }
    QScrollBar:vertical { background: #071629; width: 13px; margin: 0; }
    QScrollBar::handle:vertical { background: #1b6095; min-height: 25px; border-radius: 5px; }
    QScrollBar:horizontal { background: #071629; height: 13px; margin: 0; }
    QScrollBar::handle:horizontal { background: #1b6095; min-width: 25px; border-radius: 5px; }
    """)
