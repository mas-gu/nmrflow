"""com_parser — parse and update NMRPipe ft*.com processing scripts.

Identifies the X (direct) and Y (indirect) PS phase-correction calls by their
position relative to the first -fn TP (transpose) command in the pipeline.
"""

from __future__ import annotations

import re
from pathlib import Path

_PS_DETECT  = re.compile(r'-fn\s+PS\b',      re.IGNORECASE)
_TP_DETECT  = re.compile(r'-fn\s+TP\b',      re.IGNORECASE)
_P0_RE      = re.compile(r'(-p0\s+)([-+]?\d*\.?\d+)', re.IGNORECASE)
_P1_RE      = re.compile(r'(-p1\s+)([-+]?\d*\.?\d+)', re.IGNORECASE)


def find_com_script(spectrum_path: str) -> Path | None:
    """Return the path of the first ft*.com script found alongside *spectrum_path*.

    Strips any filemask format specifiers (e.g. ``%03d``) from the path before
    computing the parent directory so that 3-D series paths work correctly.
    Checks common names first (ft2d.com, ft3d.com, ft1d.com, ft.com) then
    falls back to any ``ft*.com`` glob in the same directory.
    """
    clean = re.sub(r"%[0-9]*d", "", spectrum_path)
    d = Path(clean).parent
    for name in ("ft2d.com", "ft3d.com", "ft1d.com", "ft.com"):
        p = d / name
        if p.exists():
            return p
    matches = sorted(d.glob("ft*.com"))
    return matches[0] if matches else None


def parse_ps_phases(text: str) -> dict[str, tuple[float, float]]:
    """Return ``{'x': (p0, p1), 'y': (p0, p1)}`` parsed from *text*.

    Convention: the first PS call before the first TP = X (direct); the first
    PS call after the first TP = Y (indirect).  Returns ``(0.0, 0.0)`` for
    any dimension whose PS line is absent.
    """
    found_tp = False
    ps_x: tuple[float, float] | None = None
    ps_y: tuple[float, float] | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if _TP_DETECT.search(line):
            found_tp = True
            continue
        if _PS_DETECT.search(line):
            m0 = _P0_RE.search(line)
            m1 = _P1_RE.search(line)
            if not m0 or not m1:
                continue
            p0, p1 = float(m0.group(2)), float(m1.group(2))
            if not found_tp and ps_x is None:
                ps_x = (p0, p1)
            elif found_tp and ps_y is None:
                ps_y = (p0, p1)
                break   # no need to scan further

    return {
        "x": ps_x if ps_x is not None else (0.0, 0.0),
        "y": ps_y if ps_y is not None else (0.0, 0.0),
    }


def update_ps_phases(
    text: str,
    p0_x: float, p1_x: float,
    p0_y: float, p1_y: float,
) -> str:
    """Return *text* with the PS -p0/-p1 values replaced by the supplied ones.

    Applies the same X-before-TP / Y-after-TP identification as
    :func:`parse_ps_phases`.  Lines beginning with ``#`` are never modified.
    """
    lines = text.splitlines(keepends=True)
    found_tp  = False
    done_x    = False
    done_y    = False
    result: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("#") and _TP_DETECT.search(line):
            found_tp = True

        if (not stripped.startswith("#")) and _PS_DETECT.search(line):
            if not found_tp and not done_x:
                line = _P0_RE.sub(lambda m, v=p0_x: m.group(1) + f"{v:g}", line)
                line = _P1_RE.sub(lambda m, v=p1_x: m.group(1) + f"{v:g}", line)
                done_x = True
            elif found_tp and not done_y:
                line = _P0_RE.sub(lambda m, v=p0_y: m.group(1) + f"{v:g}", line)
                line = _P1_RE.sub(lambda m, v=p1_y: m.group(1) + f"{v:g}", line)
                done_y = True

        result.append(line)

    return "".join(result)
