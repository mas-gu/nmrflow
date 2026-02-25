"""AutoPhaseResultDialog — displays autophase P0/P1 for both X and Y dimensions."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QGridLayout, QLabel, QDialogButtonBox, QVBoxLayout, QFrame,
)
from PySide6.QtCore import Qt


class AutoPhaseResultDialog(QDialog):
    """Modal dialog showing auto-phase results for X and Y dimensions.

    Accept → caller applies the phased data and updates the UI.
    Reject → caller discards the result and leaves data unchanged.
    """

    def __init__(
        self,
        p0_x: float, p1_x: float,
        p0_y: float, p1_y: float,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Auto-Phase Results")
        self.setModal(True)
        self._build_ui(p0_x, p1_x, p0_y, p1_y)

    def _build_ui(self, p0_x: float, p1_x: float, p0_y: float, p1_y: float):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)

        # Column headers
        for col, text in enumerate(("Dimension", "P0 (°)", "P1 (°)")):
            lbl = QLabel(f"<b>{text}</b>")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl, 0, col)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        grid.addWidget(line, 1, 0, 1, 3)

        # X row
        grid.addWidget(QLabel("X  (direct)"), 2, 0)
        for col, val in enumerate((p0_x, p1_x), start=1):
            lbl = QLabel(f"{val:+.2f}")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(lbl, 2, col)

        # Y row
        grid.addWidget(QLabel("Y  (indirect)"), 3, 0)
        for col, val in enumerate((p0_y, p1_y), start=1):
            lbl = QLabel(f"{val:+.2f}")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(lbl, 3, col)

        layout.addLayout(grid)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.adjustSize()
        self.setFixedSize(self.sizeHint())
