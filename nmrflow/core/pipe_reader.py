"""NMRPipe file I/O via nmrglue."""

from __future__ import annotations
import glob
import re
from pathlib import Path
from typing import Optional
import numpy as np

try:
    import nmrglue as ng
except ImportError as exc:  # pragma: no cover
    raise ImportError("nmrglue is required: pip install nmrglue") from exc

# autophase_1d and apply_phase live in core.phase (signal processing, not I/O).
# Re-exported here so existing ``from .pipe_reader import apply_phase`` calls
# continue to work without modification.
from .phase import autophase_1d, apply_phase  # noqa: F401


def detect_filemask(path: str | Path) -> Optional[str]:
    """If *path* is one plane of a numbered multi-file series, return the filemask.

    Example: ``/data/test001.ft3`` → ``'/data/test%03d.ft3'`` when sibling
    files ``test002.ft3``, ``test003.ft3``, … exist.  Returns ``None`` when
    the file appears to be standalone.
    """
    p = Path(path)
    m = re.match(r'^(.*?)(\d+)(\.\w+)$', p.name)
    if not m:
        return None
    prefix, digits, ext = m.group(1), m.group(2), m.group(3)
    width = len(digits)
    # Collect siblings that match exactly the same numeric width
    candidates = [
        f for f in glob.glob(str(p.parent / f"{prefix}*{ext}"))
        if re.fullmatch(
            rf'{re.escape(prefix)}\d{{{width}}}{re.escape(ext)}',
            Path(f).name,
        )
    ]
    if len(candidates) > 1:
        return str(p.parent / f"{prefix}%0{width}d{ext}")
    return None


def find_filemask_in_folder(folder: str | Path) -> Optional[str]:
    """Scan *folder* for the first NMRPipe numbered-plane series.

    Returns the filemask string (e.g. ``'/data/spec%03d.ft3'``) or ``None``
    if no multi-file series is detected.  Extensions are checked in order of
    decreasing dimensionality so 3D/4D data is preferred over 2D.
    """
    folder = Path(folder)
    for ext in (".ft4", ".ft3", ".ft2", ".ft", ".fid"):
        files = sorted(folder.glob(f"*{ext}"))
        if len(files) >= 2:
            mask = detect_filemask(files[0])
            if mask:
                return mask
    return None


def read_ucsf(path: str | Path) -> tuple[dict, np.ndarray]:
    """Read a UCSF/Sparky spectrum file and return (dic, data)."""
    return ng.sparky.read(str(path))


def make_unit_converters_ucsf(dic: dict, data: np.ndarray) -> list:
    """Return unit-conversion objects for every axis of a UCSF spectrum."""
    return [ng.sparky.make_uc(dic, data, dim=i) for i in range(data.ndim)]


def read_spectrum(path: str | Path) -> tuple[dict, np.ndarray]:
    """Read an NMRPipe spectrum file (or 3-D/4-D filemask) and return (dic, data).

    Supports:
    - Single 2-D file: ``spectrum.ft2``
    - 3-D filemask:    ``spec%03d.ft3``
    - 4-D filemask:    ``spec%03d%03d.ft4``

    Byte-order detection and header parsing are handled by nmrglue.
    """
    return ng.pipe.read(str(path))


def make_unit_converters(dic: dict, data: np.ndarray) -> list:
    """Return a unit-conversion object for every axis (outermost first).

    For a 2-D spectrum, returns ``[uc_y, uc_x]``.
    For a 3-D spectrum, returns ``[uc_z, uc_y, uc_x]``.
    """
    ndim = data.ndim
    return [ng.pipe.make_uc(dic, data, dim=i) for i in range(ndim)]


def read_peak_table(path: str | Path) -> tuple[dict, dict, list]:
    """Read an NMRPipe .tab peak table.

    Returns ``(header_dict, col_dict, rows)`` as produced by
    ``nmrglue.pipe.read_table``.
    """
    return ng.pipe.read_table(str(path))


