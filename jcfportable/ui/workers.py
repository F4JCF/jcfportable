"""Tâches en arrière-plan (réseau, CAT) pour ne jamais bloquer la saisie."""
import queue
import traceback

from PySide6.QtCore import QObject, QRunnable, QThread, QThreadPool, Signal

from jcfportable.cat import RigCtl


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    progress = Signal(int, str)


class Worker(QRunnable):
    def __init__(self, fn, *args, with_progress=False, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = WorkerSignals()
        if with_progress:
            self.kwargs["progress"] = lambda p, m: self.signals.progress.emit(p, m)

    def run(self):
        try:
            res = self.fn(*self.args, **self.kwargs)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.signals.error.emit(str(e))
            return
        self.signals.result.emit(res)


def run_bg(fn, *args, on_result=None, on_error=None, on_progress=None, **kwargs):
    w = Worker(fn, *args, with_progress=on_progress is not None, **kwargs)
    if on_result:
        w.signals.result.connect(on_result)
    if on_error:
        w.signals.error.connect(on_error)
    if on_progress:
        w.signals.progress.connect(on_progress)
    QThreadPool.globalInstance().start(w)
    return w


class CatThread(QThread):
    """Interroge la radio chaque seconde et applique les ordres (fréquence, mode)."""
    vfo = Signal(float, object)      # kHz, mode
    status = Signal(bool, str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.orders = queue.Queue()
        self._stop = False

    def stop(self):
        self._stop = True
        self.wait(5000)

    def tune(self, khz=None, mode=None):
        self.orders.put((khz, mode))

    def run(self):
        rig = RigCtl(self.settings)
        connected = False
        last = None
        while not self._stop:
            if not connected:
                connected = rig.start()
                if connected:
                    self.status.emit(True, "CAT connecté")
                else:
                    self.status.emit(False, rig.last_error or "CAT non connecté")
                    for _ in range(50):
                        if self._stop:
                            break
                        self.msleep(100)
                    continue
            try:
                while not self.orders.empty():
                    khz, mode = self.orders.get_nowait()
                    if khz:
                        rig.set_freq(khz)
                    if mode:
                        rig.set_mode(mode, khz or (last[0] if last else 14000))
                f, m, _ = rig.read()
                if (f, m) != last:
                    last = (f, m)
                    self.vfo.emit(f, m)
            except OSError as e:
                connected = False
                rig.stop()
                self.status.emit(False, f"CAT perdu : {e}")
                continue
            for _ in range(10):
                if self._stop or not self.orders.empty():
                    break
                self.msleep(100)
        rig.stop()
