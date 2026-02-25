"""nmrDraw-compatible CLI argument parser."""

from __future__ import annotations
import argparse
import sys
from typing import Optional


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nmrDraw",
        description="nmrflow — Python/PySide6 NMR spectrum viewer (nmrDraw replacement)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,  # we add our own so -help works like nmrDraw
    )

    # Compatibility aliases: -help and --help
    p.add_argument("-help", "--help", action="help", help="Show this help message and exit")

    # ---- Input file ----
    p.add_argument("-in", dest="infile", metavar="INNAME", default=None,
                   help="Input NMRPipe spectrum file or filemask (e.g. spec%%03d.ft3)")

    # ---- Plane selection ----
    p.add_argument("-iz", dest="iz", type=int, default=0,
                   metavar="ZPLANE", help="Initial Z-plane index (3-D spectra, default 0)")
    p.add_argument("-ia", dest="ia", type=int, default=0,
                   metavar="APLANE", help="Initial A-plane index (4-D spectra, default 0)")

    # ---- Contour levels ----
    p.add_argument("-plev", dest="pos_levels", type=int, default=10,
                   metavar="N", help="Number of positive contour levels (default 10)")
    p.add_argument("-nlev", dest="neg_levels", type=int, default=10,
                   metavar="N", help="Number of negative contour levels (default 10)")
    p.add_argument("-hi", dest="height", type=float, default=0.0,
                   metavar="HEIGHT", help="First contour height (default: auto 3×noise)")
    p.add_argument("-mult", dest="mult", type=float, default=1.3,
                   metavar="FACTOR", help="Contour level multiplication factor (default 1.3)")

    # ---- Positive colour range (HSV) ----
    p.add_argument("-pcc", dest="p_color_count", type=int, default=None,
                   metavar="N", help="Positive colour count (default = plev)")
    p.add_argument("-pHue1", dest="p_hue1", type=float, default=0.60, metavar="H")
    p.add_argument("-pHue2", dest="p_hue2", type=float, default=0.50, metavar="H")
    p.add_argument("-pSat1", dest="p_sat1", type=float, default=1.0, metavar="S")
    p.add_argument("-pSat2", dest="p_sat2", type=float, default=0.8, metavar="S")
    p.add_argument("-pVal1", dest="p_val1", type=float, default=0.9, metavar="V")
    p.add_argument("-pVal2", dest="p_val2", type=float, default=1.0, metavar="V")

    # ---- Negative colour range (HSV) ----
    p.add_argument("-ncc", dest="n_color_count", type=int, default=None,
                   metavar="N", help="Negative colour count (default = nlev)")
    p.add_argument("-nHue1", dest="n_hue1", type=float, default=0.00, metavar="H")
    p.add_argument("-nHue2", dest="n_hue2", type=float, default=0.83, metavar="H")
    p.add_argument("-nSat1", dest="n_sat1", type=float, default=1.0, metavar="S")
    p.add_argument("-nSat2", dest="n_sat2", type=float, default=0.8, metavar="S")
    p.add_argument("-nVal1", dest="n_val1", type=float, default=0.9, metavar="V")
    p.add_argument("-nVal2", dest="n_val2", type=float, default=1.0, metavar="V")

    # ---- Display options ----
    p.add_argument("-peak", dest="show_peaks", action="store_true",
                   help="Display peak overlay (looks for a .tab file alongside the spectrum)")
    p.add_argument("-peakFile", dest="peak_file", metavar="FILE", default=None,
                   help="Explicit path to peak .tab file")
    p.add_argument("-vert", dest="vert", action="store_true",
                   help="Use vertical 1-D slice layout")
    p.add_argument("-zero", dest="show_zero", action="store_true",
                   help="Show zero line in 1-D displays")
    p.add_argument("-cursor", dest="show_cursor", action="store_true",
                   help="Show cursor bar on spectrum")

    # ---- UI / appearance ----
    p.add_argument("-scale", dest="scale", choices=["small", "medium", "large"],
                   default="medium", help="UI scale (default: medium)")
    p.add_argument("-fg", dest="fg_color", metavar="COLOR", default=None,
                   help="Foreground colour (name or #RRGGBB)")
    p.add_argument("-bg", dest="bg_color", metavar="COLOR", default=None,
                   help="Background colour (name or #RRGGBB)")

    # ---- Phase ----
    p.add_argument("-p0", dest="p0", type=float, default=0.0,
                   metavar="DEG", help="Zero-order phase (degrees)")
    p.add_argument("-p1", dest="p1", type=float, default=0.0,
                   metavar="DEG", help="First-order phase (degrees)")

    # ---- Region / zoom ----
    p.add_argument("-xT", dest="x_start", type=float, default=None,
                   metavar="PPM", help="X-axis start PPM")
    p.add_argument("-xB", dest="x_end", type=float, default=None,
                   metavar="PPM", help="X-axis end PPM")
    p.add_argument("-yT", dest="y_start", type=float, default=None,
                   metavar="PPM", help="Y-axis start PPM")
    p.add_argument("-yB", dest="y_end", type=float, default=None,
                   metavar="PPM", help="Y-axis end PPM")

    return p


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse argv (default: sys.argv[1:]) and return the Namespace."""
    parser = build_parser()
    return parser.parse_args(argv if argv is not None else sys.argv[1:])
