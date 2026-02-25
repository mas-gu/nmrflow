"""scipy.signal-based 2-D peak detection for NMR spectra."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np

try:
    from scipy.ndimage import maximum_filter, label
    from scipy.signal import find_peaks
    _SCIPY_OK = True
except ImportError:  # pragma: no cover
    _SCIPY_OK = False


@dataclass
class FoundPeak:
    row: int      # point coordinate (Y axis)
    col: int      # point coordinate (X axis)
    height: float


def find_peaks_2d(
    plane: np.ndarray,
    threshold: float,
    min_distance: int = 3,
    negative: bool = False,
) -> list[FoundPeak]:
    """Find local maxima in a 2-D NMR plane above *threshold*.

    Parameters
    ----------
    plane : np.ndarray
        2-D spectral data (real).
    threshold : float
        Absolute intensity threshold; only peaks above this level are reported.
    min_distance : int
        Minimum separation between peaks in points (neighbourhood radius).
    negative : bool
        If True, search for negative peaks (minima).

    Returns
    -------
    list[FoundPeak]
        Detected peaks sorted by descending absolute height.
    """
    if not _SCIPY_OK:
        raise RuntimeError("scipy is required for peak finding")

    data = -plane if negative else plane.copy()

    # Local maxima via maximum filter
    size = 2 * min_distance + 1
    local_max = maximum_filter(data, size=size) == data
    above = data > threshold
    mask = local_max & above

    rows, cols = np.where(mask)
    peaks = [
        FoundPeak(row=int(r), col=int(c), height=float(plane[r, c]))
        for r, c in zip(rows, cols)
    ]
    peaks.sort(key=lambda p: abs(p.height), reverse=True)
    return peaks


def peaks_to_ppm(
    peaks: list[FoundPeak],
    uc_x,
    uc_y,
) -> list[tuple[float, float, float]]:
    """Convert peak point coordinates to (x_ppm, y_ppm, height) tuples."""
    result = []
    for p in peaks:
        try:
            x = uc_x.ppm(p.col)
            y = uc_y.ppm(p.row)
        except Exception:
            x = float(p.col)
            y = float(p.row)
        result.append((x, y, p.height))
    return result
