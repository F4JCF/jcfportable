import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from jcfportable import APP_NAME, VERSION
from jcfportable.config import Settings, data_dir
from jcfportable.db import Database


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setDesktopFileName("jcfportable")
    icon = Path(__file__).with_name("icon.png")
    app.setWindowIcon(QIcon(str(icon)) if icon.exists() else QIcon.fromTheme("jcfportable"))
    if sys.platform == "win32":
        try:  # icône correcte dans la barre des tâches Windows
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("F4JCF.JCFPortable")
        except (AttributeError, OSError):
            pass
    app.setStyle("Fusion")
    tr = QTranslator(app)
    if tr.load(QLocale("fr_FR"), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(tr)
    from jcfportable.ui.main_window import MainWindow
    settings = Settings()
    db = Database(data_dir() / "jcfportable.db")
    win = MainWindow(db, settings)
    win.show()
    sys.exit(app.exec())
