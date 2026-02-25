"""FileBrowser — directory + file list panel."""

from __future__ import annotations
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QPushButton, QFileDialog, QLabel, QListWidgetItem,
)
from PySide6.QtCore import Signal, Qt


_SPECTRUM_EXTS = {".ft", ".ft2", ".ft3", ".ft4", ".fid", ".dat", ".pipe", ".ucsf"}


class FileBrowser(QWidget):
    """Panel showing NMRPipe files in a chosen directory.

    Signals
    -------
    file_selected(path: str) : emitted when the user double-clicks a file.
    """

    file_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._directory = Path.home()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Directory row
        dir_row = QHBoxLayout()
        self._dir_label = QLabel(str(self._directory))
        self._dir_label.setWordWrap(True)
        dir_row.addWidget(self._dir_label, 1)
        btn_browse = QPushButton("…")
        btn_browse.setFixedWidth(28)
        btn_browse.clicked.connect(self._choose_directory)
        dir_row.addWidget(btn_browse)
        layout.addLayout(dir_row)

        # File list
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list, 1)

        self._refresh_list()

    def _choose_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Choose directory", str(self._directory))
        if d:
            self._directory = Path(d)
            self._dir_label.setText(str(self._directory))
            self._refresh_list()

    def _refresh_list(self):
        self._list.clear()
        try:
            entries = sorted(self._directory.iterdir())
        except OSError:
            return
        for entry in entries:
            if entry.is_file() and entry.suffix.lower() in _SPECTRUM_EXTS:
                item = QListWidgetItem(entry.name)
                item.setData(Qt.ItemDataRole.UserRole, str(entry))
                self._list.addItem(item)

    def _on_double_click(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.file_selected.emit(path)

    def set_directory(self, path: str | Path):
        self._directory = Path(path)
        self._dir_label.setText(str(self._directory))
        self._refresh_list()
