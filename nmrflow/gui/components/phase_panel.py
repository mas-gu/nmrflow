"""PhasePanel — P0/P1 coarse+fine sliders with editable spinboxes,
pivot (PPM), Phasing On/Off (1D live), and Update 2D button."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox, QGridLayout, QHBoxLayout, QDoubleSpinBox, QComboBox,
    QPushButton, QLabel, QSlider, QWidget, QButtonGroup,
)
from PySide6.QtCore import Signal, Qt


class PhasePanel(QGroupBox):
    """Controls for zero- and first-order phase correction.

    Two sliders per parameter
    -------------------------
    Coarse slider — large-range adjustment.
    Fine slider   — small-range trim (narrower widget, finer resolution).

    Editable numeric fields
    -----------------------
    The spinbox to the right of each slider pair is fully editable.
    Typing a value decomposes it into coarse + fine and moves both sliders.

    Phasing On / Off  (1D preview)
    --------------------------------
    On  : every slider/spinbox change live-updates the 1D trace only.
    Off : sliders move freely with no spectrum update.
          Clicking On applies immediately.

    Update 2D
    ---------
    Always-available button that triggers a full 2D contour redraw
    (regardless of the On/Off state).

    Middle-click on the spectrum sets the pivot via set_pivot_ppm().

    Signals
    -------
    phase_changed(p0, p1, pivot_ppm, dim)   — 1D trace live update
    phase_apply_2d(p0, p1, pivot_ppm, dim)  — full 2D contour redraw
    """

    phase_changed       = Signal(float, float, float, int)
    phase_apply_2d      = Signal(float, float, float, int)
    phase_auto_requested = Signal()

    # Scale factors: slider integer × scale = degrees
    _P0_COARSE_SCALE = 1.0     # ±360 units  → ±360°
    _P0_FINE_SCALE   = 0.01    # ±100 units  → ±1°
    _P1_COARSE_SCALE = 1.0     # ±360 units  → ±360°
    _P1_FINE_SCALE   = 0.1     # ±200 units  → ±20°

    def __init__(self, parent=None):
        super().__init__("Phase Correction", parent)
        self._phasing_on = False
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        grid = QGridLayout()
        grid.setContentsMargins(6, 8, 6, 6)
        grid.setSpacing(4)

        # --- P0 row ---
        grid.addWidget(QLabel("P0 (°):"), 0, 0)
        self._p0_coarse = self._make_slider(-360, 360)
        self._p0_fine   = self._make_slider(-100, 100)
        self._p0_spin   = self._make_value_spin(-361.0, 361.0, decimals=2, step=0.1)
        grid.addWidget(self._p0_coarse, 0, 1)
        grid.addWidget(self._p0_fine,   0, 2)
        grid.addWidget(self._p0_spin,   0, 3)

        # --- P1 row ---
        grid.addWidget(QLabel("P1 (°):"), 1, 0)
        self._p1_coarse = self._make_slider(-360, 360)
        self._p1_fine   = self._make_slider(-200, 200)
        self._p1_spin   = self._make_value_spin(-380.0, 380.0, decimals=1, step=0.5)
        grid.addWidget(self._p1_coarse, 1, 1)
        grid.addWidget(self._p1_fine,   1, 2)
        grid.addWidget(self._p1_spin,   1, 3)

        # --- Pivot row ---
        grid.addWidget(QLabel("Pivot (ppm):"), 2, 0)
        self._pivot_spin = QDoubleSpinBox()
        self._pivot_spin.setRange(-999.0, 999.0)
        self._pivot_spin.setSingleStep(0.01)
        self._pivot_spin.setDecimals(3)
        self._pivot_spin.setValue(0.0)
        self._pivot_spin.setToolTip(
            "Pivot position in PPM.\n"
            "Middle-click on the spectrum to set it interactively."
        )
        grid.addWidget(self._pivot_spin, 2, 1, 1, 3)

        # --- Dimension row ---
        grid.addWidget(QLabel("Dimension:"), 3, 0)
        self._dim_combo = QComboBox()
        self._dim_combo.addItems(["X (direct)", "Y (indirect)", "Z"])
        grid.addWidget(self._dim_combo, 3, 1, 1, 3)

        # --- Phasing On/Off row ---
        grid.addWidget(QLabel("Phasing:"), 4, 0)
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)
        self._btn_on  = QPushButton("On")
        self._btn_off = QPushButton("Off")
        for btn in (self._btn_on, self._btn_off):
            btn.setCheckable(True)
            btn.setFixedWidth(40)
        self._btn_off.setChecked(True)
        # Exclusive group ensures exactly one button is always checked,
        # preventing visual/state divergence if a checked button is clicked again.
        self._on_off_group = QButtonGroup(self)
        self._on_off_group.setExclusive(True)
        self._on_off_group.addButton(self._btn_on)
        self._on_off_group.addButton(self._btn_off)
        btn_layout.addWidget(self._btn_on)
        btn_layout.addWidget(self._btn_off)
        btn_layout.addStretch()
        grid.addWidget(btn_row, 4, 1, 1, 3)

        # --- Update 2D row ---
        self._btn_2d = QPushButton("Update 2D")
        self._btn_2d.setToolTip("Redraw 2D contours with current phase values")
        grid.addWidget(self._btn_2d, 5, 0, 1, 4)

        # --- Auto Phase row ---
        self._btn_auto = QPushButton("Auto Phase")
        self._btn_auto.setToolTip(
            "Automatically determine P0/P1 for both X and Y dimensions"
        )
        grid.addWidget(self._btn_auto, 6, 0, 1, 4)

        # --- Last autophase result label ---
        self._result_label = QLabel("")
        self._result_label.setStyleSheet("color: gray; font-size: 10px;")
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._result_label.setWordWrap(True)
        grid.addWidget(self._result_label, 7, 0, 1, 4)

        # Coarse slider gets 3× as much horizontal space as fine slider
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 1)

        self.setLayout(grid)
        self._connect_internal()

    @staticmethod
    def _make_slider(lo: int, hi: int) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi)
        s.setValue(0)
        return s

    @staticmethod
    def _make_value_spin(lo: float, hi: float,
                         decimals: int = 1, step: float = 0.1) -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        sb.setRange(lo, hi)
        sb.setDecimals(decimals)
        sb.setSingleStep(step)
        sb.setValue(0.0)
        sb.setMinimumWidth(62)
        return sb

    def _connect_internal(self):
        self._p0_coarse.valueChanged.connect(self._on_p0_slider_changed)
        self._p0_fine.valueChanged.connect(self._on_p0_slider_changed)
        self._p1_coarse.valueChanged.connect(self._on_p1_slider_changed)
        self._p1_fine.valueChanged.connect(self._on_p1_slider_changed)
        self._p0_spin.valueChanged.connect(self._on_p0_spin_changed)
        self._p1_spin.valueChanged.connect(self._on_p1_spin_changed)
        self._pivot_spin.valueChanged.connect(self._on_param_changed)
        self._dim_combo.currentIndexChanged.connect(self._on_param_changed)
        self._btn_on.clicked.connect(self._on_btn_on)
        self._btn_off.clicked.connect(self._on_btn_off)
        self._btn_2d.clicked.connect(self._on_apply_2d)
        self._btn_auto.clicked.connect(self._on_auto_phase)

    # ------------------------------------------------------------------
    # Value helpers
    # ------------------------------------------------------------------

    def p0(self) -> float:
        return (self._p0_coarse.value() * self._P0_COARSE_SCALE
                + self._p0_fine.value()   * self._P0_FINE_SCALE)

    def p1(self) -> float:
        return (self._p1_coarse.value() * self._P1_COARSE_SCALE
                + self._p1_fine.value()   * self._P1_FINE_SCALE)

    def _args(self):
        """Return (p0, p1, pivot_ppm, dim) tuple."""
        dim_map = {0: -1, 1: -2, 2: -3}
        return (
            self.p0(), self.p1(),
            self._pivot_spin.value(),
            dim_map.get(self._dim_combo.currentIndex(), -1),
        )

    def _emit_1d(self):
        self.phase_changed.emit(*self._args())

    def _emit_2d(self):
        self.phase_apply_2d.emit(*self._args())

    # ------------------------------------------------------------------
    # Slider ↔ spinbox sync (blockSignals prevents feedback loops)
    # ------------------------------------------------------------------

    def _on_p0_slider_changed(self):
        self._p0_spin.blockSignals(True)
        self._p0_spin.setValue(self.p0())
        self._p0_spin.blockSignals(False)
        if self._phasing_on:
            self._emit_1d()

    def _on_p1_slider_changed(self):
        self._p1_spin.blockSignals(True)
        self._p1_spin.setValue(self.p1())
        self._p1_spin.blockSignals(False)
        if self._phasing_on:
            self._emit_1d()

    def _on_p0_spin_changed(self, value: float):
        """Typed value → decompose into coarse + fine, update sliders silently."""
        coarse = max(-360, min(360, int(round(value))))
        fine   = max(-100, min(100, round((value - coarse) / self._P0_FINE_SCALE)))
        for w in (self._p0_coarse, self._p0_fine):
            w.blockSignals(True)
        self._p0_coarse.setValue(coarse)
        self._p0_fine.setValue(fine)
        for w in (self._p0_coarse, self._p0_fine):
            w.blockSignals(False)
        if self._phasing_on:
            self._emit_1d()

    def _on_p1_spin_changed(self, value: float):
        """Typed value → decompose into coarse + fine, update sliders silently."""
        coarse = max(-360, min(360, int(round(value))))
        fine   = max(-200, min(200, round((value - coarse) / self._P1_FINE_SCALE)))
        for w in (self._p1_coarse, self._p1_fine):
            w.blockSignals(True)
        self._p1_coarse.setValue(coarse)
        self._p1_fine.setValue(fine)
        for w in (self._p1_coarse, self._p1_fine):
            w.blockSignals(False)
        if self._phasing_on:
            self._emit_1d()

    def _on_param_changed(self):
        """Pivot or dimension changed."""
        if self._phasing_on:
            self._emit_1d()

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_btn_on(self):
        self._phasing_on = True
        self._emit_1d()   # apply immediately on activation

    def _on_btn_off(self):
        self._phasing_on = False

    def _on_apply_2d(self):
        self._emit_2d()

    def _on_auto_phase(self):
        self.phase_auto_requested.emit()

    # ------------------------------------------------------------------
    # External setters (main window / CLI args)
    # ------------------------------------------------------------------

    def set_p0(self, value: float):
        coarse = max(-360,  min(360,  int(round(value))))
        fine   = max(-100,  min(100,  round((value - coarse) / self._P0_FINE_SCALE)))
        for w in (self._p0_coarse, self._p0_fine, self._p0_spin):
            w.blockSignals(True)
        self._p0_coarse.setValue(coarse)
        self._p0_fine.setValue(fine)
        self._p0_spin.setValue(self.p0())
        for w in (self._p0_coarse, self._p0_fine, self._p0_spin):
            w.blockSignals(False)

    def set_p1(self, value: float):
        coarse = max(-360, min(360, int(round(value))))
        fine   = max(-200,  min(200,  round((value - coarse) / self._P1_FINE_SCALE)))
        for w in (self._p1_coarse, self._p1_fine, self._p1_spin):
            w.blockSignals(True)
        self._p1_coarse.setValue(coarse)
        self._p1_fine.setValue(fine)
        self._p1_spin.setValue(self.p1())
        for w in (self._p1_coarse, self._p1_fine, self._p1_spin):
            w.blockSignals(False)

    def set_dim(self, dim: int):
        """Set the dimension combo from code without triggering a phase signal."""
        dim_to_index = {-1: 0, -2: 1, -3: 2}
        idx = dim_to_index.get(dim, 0)
        self._dim_combo.blockSignals(True)
        self._dim_combo.setCurrentIndex(idx)
        self._dim_combo.blockSignals(False)

    def set_pivot_ppm(self, ppm: float):
        self._pivot_spin.blockSignals(True)
        self._pivot_spin.setValue(ppm)
        self._pivot_spin.blockSignals(False)

    def current_dim(self) -> int:
        return {0: -1, 1: -2, 2: -3}.get(self._dim_combo.currentIndex(), -1)

    def set_autophase_result(
        self, p0_x: float, p1_x: float, p0_y: float, p1_y: float
    ):
        """Persist the last autophase values in the panel label."""
        self._result_label.setText(
            f"Last auto — X: P0={p0_x:+.1f}°  P1={p1_x:+.1f}°\n"
            f"            Y: P0={p0_y:+.1f}°  P1={p1_y:+.1f}°"
        )
