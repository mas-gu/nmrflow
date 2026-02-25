"""QApplication setup — high-DPI, palette, font scaling."""

from __future__ import annotations
import argparse
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt


_SCALE_FONT_PT = {"small": 10, "medium": 11, "large": 13}


def configure_app(app: QApplication, args: argparse.Namespace) -> None:
    """Apply high-DPI settings, optional colour overrides, and font size."""
    app.setApplicationName("nmrflow")
    app.setOrganizationName("NMRPipe")

    # Font scale
    scale = getattr(args, "scale", "medium")
    pt = _SCALE_FONT_PT.get(scale, 11)
    font = app.font()
    font.setPointSize(pt)
    app.setFont(font)

    # Optional background colour (dark mode friendly)
    bg = getattr(args, "bg_color", None)
    fg = getattr(args, "fg_color", None)
    if bg or fg:
        palette = app.palette()
        if bg:
            c = QColor(bg)
            palette.setColor(QPalette.ColorRole.Window, c)
            palette.setColor(QPalette.ColorRole.Base, c)
        if fg:
            c = QColor(fg)
            palette.setColor(QPalette.ColorRole.WindowText, c)
            palette.setColor(QPalette.ColorRole.Text, c)
        app.setPalette(palette)
