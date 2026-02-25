"""ComPanel — editable display of an NMRPipe ft*.com processing script.

Provides:
  - A monospace QTextEdit showing the script content (fully editable).
  - "Load…" button for manually picking a .com file.
  - "Run [filename]" button that saves the editor content to disk and
    executes the script via ``csh`` in the script's own directory.

Signals
-------
run_finished()     — emitted when the process exits with code 0.
status_message(str) — status text for the main window's status bar.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QFileDialog, QSizePolicy,
)
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import Signal, QProcess

from ...core.com_parser import parse_ps_phases, update_ps_phases


class ComPanel(QWidget):
    """Editable script viewer with a Run button."""

    run_finished   = Signal()       # emitted on exit-code 0
    status_message = Signal(str)    # routed to main window status bar

    def __init__(self, parent=None):
        super().__init__(parent)
        self._com_path: Path | None = None
        self._baked: dict[str, tuple[float, float]] = {
            "x": (0.0, 0.0),
            "y": (0.0, 0.0),
        }
        self._process: QProcess | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ---- top row: path label + Load button ----
        top = QHBoxLayout()
        self._path_label = QLabel("No script loaded")
        self._path_label.setStyleSheet("color: gray; font-size: 10px;")
        self._path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._btn_load = QPushButton("Load…")
        self._btn_load.setFixedWidth(52)
        top.addWidget(self._path_label)
        top.addWidget(self._btn_load)
        layout.addLayout(top)

        # ---- text editor ----
        self._editor = QTextEdit()
        fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed.setPointSize(10)
        self._editor.setFont(fixed)
        self._editor.setMinimumHeight(120)
        layout.addWidget(self._editor)

        # ---- bottom row: Run button + status label ----
        bottom = QHBoxLayout()
        self._btn_run = QPushButton("Run script")
        self._btn_run.setEnabled(False)
        self._run_status = QLabel("")
        self._run_status.setStyleSheet("color: gray; font-size: 10px;")
        bottom.addWidget(self._btn_run)
        bottom.addWidget(self._run_status)
        bottom.addStretch()
        layout.addLayout(bottom)

        self._btn_load.clicked.connect(self._on_load)
        self._btn_run.clicked.connect(self._on_run)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def com_path(self) -> Path | None:
        return self._com_path

    def load_file(self, path: Path | str):
        """Read *path* into the editor and parse its baked-in PS phases."""
        p = Path(path)
        try:
            text = p.read_text()
        except OSError as exc:
            self.status_message.emit(f"Cannot read {p.name}: {exc}")
            return
        self._com_path = p
        self._baked = parse_ps_phases(text)
        self._set_editor_text(text)
        self._path_label.setText(p.name)
        self._path_label.setToolTip(str(p))
        self._btn_run.setText(f"Run {p.name}")
        self._btn_run.setEnabled(True)
        self._run_status.setText("")

    def update_ps_from_panel(
        self,
        p0_x_correction: float, p1_x_correction: float,
        p0_y_correction: float, p1_y_correction: float,
    ):
        """Update PS values in the editor text to baked-in + panel correction.

        Only modifies the in-memory text; does NOT write to disk (that
        happens when the user clicks Run).
        """
        abs_p0_x = self._baked["x"][0] + p0_x_correction
        abs_p1_x = self._baked["x"][1] + p1_x_correction
        abs_p0_y = self._baked["y"][0] + p0_y_correction
        abs_p1_y = self._baked["y"][1] + p1_y_correction

        new_text = update_ps_phases(
            self._editor.toPlainText(),
            abs_p0_x, abs_p1_x,
            abs_p0_y, abs_p1_y,
        )
        self._set_editor_text(new_text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_editor_text(self, text: str):
        """Replace editor content while preserving cursor position."""
        current = self._editor.toPlainText()
        if current == text:
            return
        pos = self._editor.textCursor().position()
        self._editor.setPlainText(text)
        cursor = self._editor.textCursor()
        cursor.setPosition(min(pos, len(text)))
        self._editor.setTextCursor(cursor)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Processing Script", "",
            "C-shell scripts (*.com);;All files (*)",
        )
        if path:
            self.load_file(path)

    def _on_run(self):
        if self._com_path is None:
            self.status_message.emit("No script loaded.")
            return
        if self._process is not None and \
                self._process.state() != QProcess.ProcessState.NotRunning:
            self.status_message.emit("Script is already running.")
            return

        # Save current editor content to disk
        try:
            self._com_path.write_text(self._editor.toPlainText())
        except OSError as exc:
            self.status_message.emit(f"Cannot save {self._com_path.name}: {exc}")
            return

        self._process = QProcess(self)
        self._process.setWorkingDirectory(str(self._com_path.parent))
        self._process.finished.connect(self._on_process_finished)
        self._process.errorOccurred.connect(self._on_process_error)
        self._process.start("csh", [self._com_path.name])

        self._btn_run.setEnabled(False)
        self._btn_run.setText("Running…")
        self._run_status.setText("")
        self.status_message.emit(f"Running {self._com_path.name}…")

    def _on_process_finished(self, exit_code: int,
                              exit_status: QProcess.ExitStatus):
        name = self._com_path.name if self._com_path else "script"
        self._btn_run.setEnabled(True)
        self._btn_run.setText(f"Run {name}")
        if exit_code == 0:
            self._run_status.setText("Done")
            self.status_message.emit(f"{name} finished — reloading spectrum.")
            self.run_finished.emit()
        else:
            stderr = bytes(self._process.readAllStandardError()).decode(
                errors="replace"
            )
            self._run_status.setText(f"Exit {exit_code}")
            self.status_message.emit(
                f"{name} failed (exit {exit_code}): {stderr[:120]}"
            )

    def _on_process_error(self, error: QProcess.ProcessError):
        name = self._com_path.name if self._com_path else "script"
        self._btn_run.setEnabled(True)
        self._btn_run.setText(f"Run {name}")
        self._run_status.setText("Error")
        self.status_message.emit(f"Could not start {name}: {error}")
