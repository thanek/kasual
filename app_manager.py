import logging
import shlex

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

logger = logging.getLogger(__name__)


class AppManager(QObject):
    """Zarządza pojedynczą uruchomioną aplikacją."""

    app_started  = pyqtSignal(int)   # idx
    app_finished = pyqtSignal(int)   # idx

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._process: QProcess | None = None
        self._running_idx: int | None = None

    # ── API ────────────────────────────────────────────────────────────────

    def launch(self, idx: int, app: dict) -> None:
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            logger.warning("Próba uruchomienia app %d gdy %d już działa – ignoruję", idx, self._running_idx)
            return

        command = app["command"]
        args    = [str(a) for a in app.get("args", [])]
        logger.info("Uruchamiam [%d] %s %s", idx, command, args)

        self._process = QProcess(self)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._running_idx = idx
        self._process.start(command, args)
        self.app_started.emit(idx)

    def terminate(self) -> None:
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            logger.info("Kończę aplikację %d", self._running_idx)
            self._process.terminate()

    def kill(self) -> None:
        if self._process:
            self._process.kill()

    def is_running(self) -> bool:
        return (
            self._process is not None
            and self._process.state() != QProcess.ProcessState.NotRunning
        )

    def running_idx(self) -> int | None:
        return self._running_idx if self.is_running() else None

    # ── Wewnętrzne ─────────────────────────────────────────────────────────

    def _on_finished(self, exit_code: int, exit_status) -> None:
        idx = self._running_idx
        logger.info("Aplikacja %d zakończona (kod=%d)", idx, exit_code)
        self._running_idx = None
        self._process     = None
        self.app_finished.emit(idx)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        proc = self.sender()
        cmd  = proc.program() if proc else "?"
        logger.error("Błąd procesu '%s': %s", cmd, error.name)
