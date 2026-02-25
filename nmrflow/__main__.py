"""Entry point: ``python -m nmrflow [args]``."""

from __future__ import annotations
import sys


def main() -> None:
    # Parse CLI args before importing Qt so -help works without a display
    from .cli.args import parse_args
    args = parse_args()

    # Set high-DPI policy BEFORE QApplication is created
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    from .gui.app import configure_app
    from .gui.main_window import NMRDrawWindow

    app = QApplication.instance() or QApplication(sys.argv)
    configure_app(app, args)

    window = NMRDrawWindow(args)
    window.show()

    # Load spectrum if supplied on command line
    if args.infile:
        window.open_spectrum(args.infile)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
