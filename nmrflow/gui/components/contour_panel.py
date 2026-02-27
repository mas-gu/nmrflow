"""ContourPanel — level count, height, factor, and two colour pickers."""

from __future__ import annotations
import colorsys

from PySide6.QtWidgets import (
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox, QPushButton,
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QColorDialog

from ...core.contour import ContourParams

_DEFAULT_POS = "#4da6ff"
_DEFAULT_NEG = "#ff4d4d"


class ContourPanel(QGroupBox):
    """Panel: level count, height, factor, positive/negative colour pickers.

    Signals
    -------
    params_changed(ContourParams)
    """

    params_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__("Contour Levels", parent)
        self._building = True
        self._pos_color = _DEFAULT_POS
        self._neg_color = _DEFAULT_NEG
        self._build_ui()
        self._building = False

    def _build_ui(self):
        form = QFormLayout()
        form.setContentsMargins(6, 6, 6, 6)
        form.setSpacing(4)

        self._plev = QSpinBox()
        self._plev.setRange(0, 64)
        self._plev.setValue(10)
        form.addRow("Pos. levels:", self._plev)

        self._nlev = QSpinBox()
        self._nlev.setRange(0, 64)
        self._nlev.setValue(10)
        form.addRow("Neg. levels:", self._nlev)

        self._height = QDoubleSpinBox()
        self._height.setRange(0.0, 1e12)
        self._height.setDecimals(2)
        self._height.setValue(0.0)
        self._height.setSpecialValueText("auto")
        form.addRow("Height:", self._height)

        self._mult = QDoubleSpinBox()
        self._mult.setRange(1.001, 10.0)
        self._mult.setSingleStep(0.05)
        self._mult.setDecimals(3)
        self._mult.setValue(1.3)
        form.addRow("Factor:", self._mult)

        # Colour buttons
        self._pos_btn = self._make_color_btn(self._pos_color)
        self._pos_btn.clicked.connect(self._pick_pos_color)
        form.addRow("Pos. colour:", self._pos_btn)

        self._neg_btn = self._make_color_btn(self._neg_color)
        self._neg_btn.clicked.connect(self._pick_neg_color)
        form.addRow("Neg. colour:", self._neg_btn)

        self.setLayout(form)

        for widget in [self._plev, self._nlev]:
            widget.valueChanged.connect(self._emit)
        for widget in [self._height, self._mult]:
            widget.valueChanged.connect(self._emit)

    @staticmethod
    def _make_color_btn(hex_color: str) -> QPushButton:
        btn = QPushButton()
        btn.setFixedHeight(22)
        ContourPanel._apply_btn_color(btn, hex_color)
        return btn

    @staticmethod
    def _apply_btn_color(btn: QPushButton, hex_color: str):
        btn.setStyleSheet(
            f"background-color: {hex_color}; border: 1px solid #888; border-radius: 3px;"
        )
        btn.setProperty("hex_color", hex_color)

    def _set_color(self, which: str, hex_color: str):
        """Programmatically set 'pos' or 'neg' colour without opening a dialog."""
        if which == "pos":
            self._pos_color = hex_color
            self._apply_btn_color(self._pos_btn, hex_color)
        else:
            self._neg_color = hex_color
            self._apply_btn_color(self._neg_btn, hex_color)
        self._emit()

    def _pick_pos_color(self):
        color = QColorDialog.getColor(QColor(self._pos_color), self, "Positive contour colour")
        if color.isValid():
            self._pos_color = color.name()
            self._apply_btn_color(self._pos_btn, self._pos_color)
            self._emit()

    def _pick_neg_color(self):
        color = QColorDialog.getColor(QColor(self._neg_color), self, "Negative contour colour")
        if color.isValid():
            self._neg_color = color.name()
            self._apply_btn_color(self._neg_btn, self._neg_color)
            self._emit()

    def _emit(self, *_):
        if not self._building:
            self.params_changed.emit(self.get_params())

    def get_params(self) -> ContourParams:
        return ContourParams(
            pos_levels=self._plev.value(),
            neg_levels=self._nlev.value(),
            height=self._height.value(),
            mult=self._mult.value(),
            pos_color=self._pos_color,
            neg_color=self._neg_color,
        )

    def set_height(self, value: float):
        """Set height spinbox to *value* without emitting params_changed."""
        self._building = True
        try:
            self._height.setValue(value)
        finally:
            self._building = False

    def set_from_args(self, args):
        self._building = True
        try:
            self._plev.setValue(getattr(args, "pos_levels", 10))
            self._nlev.setValue(getattr(args, "neg_levels", 10))
            self._height.setValue(getattr(args, "height", 0.0))
            self._mult.setValue(getattr(args, "mult", 1.3))
        finally:
            self._building = False

        # Apply HSV colour args if provided (use hue1/sat1/val1 as the representative colour)
        ph = getattr(args, "p_hue1", None)
        if ph is not None:
            r, g, b = colorsys.hsv_to_rgb(
                getattr(args, "p_hue1", 0.60),
                getattr(args, "p_sat1", 1.0),
                getattr(args, "p_val1", 0.9),
            )
            self._set_color("pos", "#{:02x}{:02x}{:02x}".format(
                int(r * 255), int(g * 255), int(b * 255)))
        nh = getattr(args, "n_hue1", None)
        if nh is not None:
            r, g, b = colorsys.hsv_to_rgb(
                getattr(args, "n_hue1", 0.00),
                getattr(args, "n_sat1", 1.0),
                getattr(args, "n_val1", 0.9),
            )
            self._set_color("neg", "#{:02x}{:02x}{:02x}".format(
                int(r * 255), int(g * 255), int(b * 255)))
