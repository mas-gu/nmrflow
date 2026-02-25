"""HSV → RGB contour color generation matching nmrDraw's colour scheme."""

from __future__ import annotations
import colorsys
from typing import Sequence


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def hsv_color_list(
    n: int,
    hue1: float,
    sat1: float,
    val1: float,
    hue2: float,
    sat2: float,
    val2: float,
) -> list[tuple[float, float, float]]:
    """Generate *n* RGB colours by linearly interpolating in HSV space.

    Hue/saturation/value parameters are in [0, 1].  Returns a list of
    ``(r, g, b)`` tuples also in [0, 1], suitable for matplotlib.
    """
    if n <= 0:
        return []
    if n == 1:
        return [colorsys.hsv_to_rgb(hue1, sat1, val1)]

    colours: list[tuple[float, float, float]] = []
    for i in range(n):
        t = i / (n - 1)
        h = _lerp(hue1, hue2, t) % 1.0
        s = max(0.0, min(1.0, _lerp(sat1, sat2, t)))
        v = max(0.0, min(1.0, _lerp(val1, val2, t)))
        colours.append(colorsys.hsv_to_rgb(h, s, v))
    return colours


def default_pos_colors(n: int) -> list[tuple[float, float, float]]:
    """Default positive contour colours (blue → cyan)."""
    return hsv_color_list(n, 0.60, 1.0, 0.9, 0.50, 0.8, 1.0)


def default_neg_colors(n: int) -> list[tuple[float, float, float]]:
    """Default negative contour colours (red → magenta)."""
    return hsv_color_list(n, 0.0, 1.0, 0.9, 0.83, 0.8, 1.0)
