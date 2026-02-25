"""NMRPipe .tab peak table reader via nmrglue."""

from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import numpy as np

from .pipe_reader import read_peak_table


@dataclass
class Peak:
    """A single peak entry from a .tab file."""

    index: int
    x_ppm: float
    y_ppm: float
    z_ppm: Optional[float] = None
    height: float = 0.0
    volume: float = 0.0
    label: str = ""


class PeakTable:
    """Container for peaks parsed from an NMRPipe .tab file.

    Attributes
    ----------
    peaks : list[Peak]
        All parsed peak entries.
    columns : dict
        Raw column mapping (name → values array) from nmrglue.
    """

    def __init__(self, peaks: list[Peak], columns: dict):
        self.peaks = peaks
        self.columns = columns

    @classmethod
    def from_file(cls, path: str | Path) -> "PeakTable":
        """Read a .tab file and return a PeakTable."""
        _, col_dict, rows = read_peak_table(str(path))
        peaks = cls._parse_rows(col_dict, rows)
        return cls(peaks, col_dict)

    @staticmethod
    def _parse_rows(col_dict: dict, rows: list) -> list[Peak]:
        """Convert raw nmrglue output into a list of Peak objects."""
        # nmrglue returns a list of row-dicts or a structured array
        # Handle both possibilities
        peaks: list[Peak] = []

        # Determine column name variants
        def _col(candidates: list[str]):
            for c in candidates:
                if c in col_dict:
                    return col_dict[c]
            return None

        x_vals = _col(["X_PPM", "X_AXIS", "POSITION.X", "DELTAX"])
        y_vals = _col(["Y_PPM", "Y_AXIS", "POSITION.Y", "DELTAY"])
        z_vals = _col(["Z_PPM", "Z_AXIS", "POSITION.Z"])
        ht_vals = _col(["HEIGHT", "INTENS", "INTENSITY"])
        vol_vals = _col(["VOL", "VOLUME"])
        lbl_vals = _col(["ASS", "LABEL", "ASSIGN"])

        def _v(arr, idx, default=0.0):
            if arr is None:
                return default
            try:
                return float(arr[idx])
            except Exception:
                return default

        def _s(arr, idx, default=""):
            if arr is None:
                return default
            try:
                v = arr[idx]
                if isinstance(v, (bytes, bytearray)):
                    return v.decode().strip()
                return str(v).strip()
            except Exception:
                return default

        n = len(rows) if rows else (len(x_vals) if x_vals is not None else 0)
        for i in range(n):
            z = z_vals[i] if z_vals is not None and i < len(z_vals) else None
            peaks.append(
                Peak(
                    index=i + 1,
                    x_ppm=_v(x_vals, i),
                    y_ppm=_v(y_vals, i),
                    z_ppm=float(z) if z is not None else None,
                    height=_v(ht_vals, i),
                    volume=_v(vol_vals, i),
                    label=_s(lbl_vals, i),
                )
            )
        return peaks

    def x_ppms(self) -> list[float]:
        return [p.x_ppm for p in self.peaks]

    def y_ppms(self) -> list[float]:
        return [p.y_ppm for p in self.peaks]

    def labels(self) -> list[str]:
        return [p.label for p in self.peaks]

    def __len__(self) -> int:
        return len(self.peaks)

    def __repr__(self) -> str:
        return f"PeakTable({len(self.peaks)} peaks)"
