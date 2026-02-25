"""Contour level array computation matching nmrDraw's geometric progression."""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field


@dataclass
class ContourParams:
    """Parameters that control how contour levels are computed."""

    pos_levels: int = 10
    neg_levels: int = 10
    height: float = 0.0      # First (lowest) level height; 0 → auto from noise
    mult: float = 1.3        # Geometric step between levels

    pos_color: str = "#4da6ff"   # Single colour for all positive contours
    neg_color: str = "#ff4d4d"   # Single colour for all negative contours


@dataclass
class ContourLevels:
    """Computed contour levels and their single colours."""

    pos: np.ndarray = field(default_factory=lambda: np.array([]))
    neg: np.ndarray = field(default_factory=lambda: np.array([]))
    pos_color: str = "#4da6ff"
    neg_color: str = "#ff4d4d"


def compute_levels(params: ContourParams, noise: float = 1.0) -> ContourLevels:
    """Compute positive and negative contour level arrays."""
    h0 = params.height if params.height > 0 else noise * 3.0
    mult = max(1.001, params.mult)

    def _levels(n: int) -> np.ndarray:
        if n <= 0:
            return np.array([], dtype=float)
        return np.array([h0 * (mult ** i) for i in range(n)], dtype=float)

    # Negative levels must be ascending for matplotlib contour()
    # _levels() returns [h0, h0*mult, …] (ascending positive);
    # negating gives descending negatives, so flip to restore ascending order.
    neg_raw = _levels(params.neg_levels)
    neg = -neg_raw[::-1]   # e.g. [-1600, …, -39, -30]  →  ascending

    return ContourLevels(
        pos=_levels(params.pos_levels),
        neg=neg,
        pos_color=params.pos_color,
        neg_color=params.neg_color,
    )
