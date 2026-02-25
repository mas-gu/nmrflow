"""Unit tests for pipe_reader helpers (no actual NMRPipe file required)."""

import pytest
import numpy as np


def test_apply_phase_real_input():
    """apply_phase should not crash on a simple real array."""
    from nmrflow.core.pipe_reader import apply_phase

    data = np.ones((32, 64), dtype=np.float32)
    # Phase of 0 should return unchanged data (or essentially the same)
    result = apply_phase(data, p0=0.0, p1=0.0, dim=-1)
    assert result.shape == data.shape


def test_apply_phase_complex_input():
    """apply_phase on complex data should preserve shape."""
    from nmrflow.core.pipe_reader import apply_phase

    rng = np.random.default_rng(42)
    data = rng.standard_normal((16, 32)) + 1j * rng.standard_normal((16, 32))
    result = apply_phase(data, p0=90.0, p1=0.0, dim=-1)
    assert result.shape == data.shape


def test_spectrum_from_nonexistent_file():
    """Opening a non-existent file should raise an exception."""
    from nmrflow.core.spectrum import Spectrum

    with pytest.raises(Exception):
        Spectrum.from_file("/nonexistent/path/spectrum.ft2")
