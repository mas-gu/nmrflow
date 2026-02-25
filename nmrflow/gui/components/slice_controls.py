"""SliceControls — plane-view selector + browse spinbox for 3D/4D navigation."""

from __future__ import annotations
from typing import Optional

import numpy as np
from PySide6.QtWidgets import (
    QGroupBox, QFormLayout, QSpinBox, QLabel,
    QWidget, QHBoxLayout, QPushButton,
)
from PySide6.QtCore import Signal


class SliceControls(QGroupBox):
    """Plane-view mode selector and browse spinbox for 3D/4D spectra.

    View modes (XY / XZ / YZ)
    -------------------------
    Toggle buttons choose which pair of axes is displayed in the canvas.
    The third axis becomes the browse dimension stepped by the spinbox.

    Signals
    -------
    plane_changed(iplane, ia)     — spinbox moved (iplane = index in browse dim).
    plane_mode_changed(mode)      — view mode changed ("XY", "XZ", "YZ").
    """

    plane_changed      = Signal(int, int)
    plane_mode_changed = Signal(str)

    # Label for each browse dimension
    _BROWSE_LABELS = {"XY": "Z", "XZ": "Y", "YZ": "X"}

    def __init__(self, parent=None):
        super().__init__("Plane Selection", parent)
        self._current_mode: str = "XY"
        # Pre-computed per-mode data (populated by configure())
        self._n_planes: dict[str, int] = {}
        self._ppm_browse_data: dict[str, Optional[np.ndarray]] = {}
        self._ppm_browse: Optional[np.ndarray] = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        form = QFormLayout()
        form.setContentsMargins(6, 6, 6, 6)
        form.setSpacing(4)

        # --- View mode buttons ---
        mode_row = QWidget()
        mode_layout = QHBoxLayout(mode_row)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(2)
        self._mode_btns: dict[str, QPushButton] = {}
        for mode in ("XY", "XZ", "YZ"):
            btn = QPushButton(mode)
            btn.setCheckable(True)
            btn.setFixedWidth(38)
            btn.clicked.connect(lambda checked, m=mode: self._on_mode_clicked(m))
            self._mode_btns[mode] = btn
            mode_layout.addWidget(btn)
        mode_layout.addStretch()
        self._mode_btns["XY"].setChecked(True)
        form.addRow("View:", mode_row)

        # --- Browse spinbox (label updates with mode) ---
        self._browse_label = QLabel("Z plane:")
        self._iplane = QSpinBox()
        self._iplane.setRange(0, 0)
        self._iplane.setValue(0)
        form.addRow(self._browse_label, self._iplane)

        # --- PPM readout for current browse position ---
        self._ppm_label = QLabel("—")
        self._ppm_label.setStyleSheet("color: #aaaaaa; font-size: 9px;")
        form.addRow("  (ppm):", self._ppm_label)

        # --- A-plane spinbox (4D only) ---
        self._ia = QSpinBox()
        self._ia.setRange(0, 0)
        self._ia.setValue(0)
        form.addRow("A plane:", self._ia)

        self.setLayout(form)
        self._iplane.valueChanged.connect(self._emit_plane)
        self._ia.valueChanged.connect(self._emit_plane)

        self.setEnabled(False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit_plane(self, *_):
        self._update_ppm_label()
        self.plane_changed.emit(self._iplane.value(), self._ia.value())

    def _update_ppm_label(self):
        if self._ppm_browse is None:
            self._ppm_label.setText("—")
            return
        idx = self._iplane.value()
        if 0 <= idx < len(self._ppm_browse):
            self._ppm_label.setText(f"{self._ppm_browse[idx]:.3f}")

    def _on_mode_clicked(self, mode: str):
        if mode == self._current_mode:
            # Keep the button checked — can't deselect current mode
            self._mode_btns[mode].setChecked(True)
            return
        self._current_mode = mode
        # Enforce mutual exclusivity manually
        for m, btn in self._mode_btns.items():
            btn.setChecked(m == mode)
        self._update_for_mode()
        self.plane_mode_changed.emit(mode)

    def _update_for_mode(self):
        """Refresh spinbox range and labels for the current mode."""
        if not self._n_planes:
            return
        n = self._n_planes.get(self._current_mode, 1)
        self._ppm_browse = self._ppm_browse_data.get(self._current_mode)
        lbl = self._BROWSE_LABELS.get(self._current_mode, "Z")
        self._browse_label.setText(f"{lbl} plane:")
        self._iplane.blockSignals(True)
        self._iplane.setRange(0, max(n - 1, 0))
        self._iplane.setValue(0)
        self._iplane.blockSignals(False)
        self._update_ppm_label()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def configure(self, spectrum) -> None:
        """Update controls based on the loaded spectrum.

        Accepts a ``Spectrum`` object or ``None``.  Only the scalar values
        needed for display are extracted here; no reference to the spectrum
        is retained, preventing the widget from keeping large data arrays
        alive after the spectrum is replaced.
        """
        if spectrum is None or spectrum.ndim < 3:
            self._n_planes = {}
            self._ppm_browse_data = {}
            self._ppm_browse = None
            self._update_ppm_label()
            self._iplane.setRange(0, 0)
            self._ia.setRange(0, 0)
            self.setEnabled(False)
            return

        # Pre-compute per-mode data now; drop the spectrum reference afterwards
        self._n_planes = {m: spectrum.n_planes(m) for m in ("XY", "XZ", "YZ")}
        self._ppm_browse_data = {m: spectrum.ppm_browse(m) for m in ("XY", "XZ", "YZ")}

        # Enable only valid modes for this dimensionality
        for mode, btn in self._mode_btns.items():
            btn.setEnabled(True)

        if spectrum.ndim >= 4:
            self._ia.setRange(0, max(spectrum.shape[-4] - 1, 0))

        self._update_for_mode()
        self.setEnabled(True)

    def current_mode(self) -> str:
        return self._current_mode

    def step_iz(self, delta: int):
        """Step the browse index by *delta* (keyboard navigation)."""
        self._iplane.setValue(self._iplane.value() + delta)
