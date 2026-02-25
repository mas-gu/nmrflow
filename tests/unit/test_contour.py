"""Unit tests for contour level computation."""

import pytest
import numpy as np
from nmrflow.core.contour import ContourParams, compute_levels


def test_geometric_progression():
    params = ContourParams(pos_levels=5, neg_levels=0, height=100.0, mult=2.0)
    levels = compute_levels(params, noise=1.0)
    assert len(levels.pos) == 5
    expected = [100.0, 200.0, 400.0, 800.0, 1600.0]
    np.testing.assert_allclose(levels.pos, expected, rtol=1e-9)
    assert len(levels.neg) == 0


def test_negative_levels_are_negative_and_ascending():
    params = ContourParams(pos_levels=0, neg_levels=4, height=50.0, mult=1.5)
    levels = compute_levels(params, noise=1.0)
    assert len(levels.neg) == 4
    assert all(v < 0 for v in levels.neg)
    # Must be ascending (most negative first) for matplotlib
    assert list(levels.neg) == sorted(levels.neg)
    # The smallest magnitude (closest to zero) is last
    assert abs(levels.neg[-1]) == pytest.approx(50.0)


def test_auto_height_from_noise():
    params = ContourParams(pos_levels=3, height=0.0, mult=1.3)
    levels = compute_levels(params, noise=10.0)
    # First level = 3 * noise = 30
    assert levels.pos[0] == pytest.approx(30.0)


def test_colors_are_strings():
    params = ContourParams(pos_levels=6, neg_levels=4, height=1.0, mult=1.2)
    levels = compute_levels(params, noise=1.0)
    assert isinstance(levels.pos_color, str)
    assert isinstance(levels.neg_color, str)


def test_degenerate_multiplier_clamped():
    # mult of 0 should not cause infinite levels
    params = ContourParams(pos_levels=3, height=1.0, mult=0.0)
    levels = compute_levels(params, noise=1.0)
    assert len(levels.pos) == 3
    assert all(np.isfinite(v) for v in levels.pos)
