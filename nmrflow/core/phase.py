"""Phase correction and autophase utilities for NMR spectra.

Signal-processing functions separated from file I/O (pipe_reader).
"""

from __future__ import annotations
import numpy as np

try:
    import nmrglue as ng
except ImportError as exc:  # pragma: no cover
    raise ImportError("nmrglue is required: pip install nmrglue") from exc

try:
    from scipy.signal import hilbert as _hilbert
except ImportError as exc:  # pragma: no cover
    raise ImportError("scipy is required: pip install scipy") from exc


def autophase_1d(trace: np.ndarray) -> tuple[float, float]:
    """Return (p0_deg, p1_deg) that best phase a real 1D NMR trace.

    Reconstructs the analytic signal via Hilbert transform, then uses
    ACME entropy minimization (nmrglue.proc_autophase.autops).
    """
    analytic = _hilbert(trace.astype(np.float64))   # real → complex analytic
    _, phases = ng.proc_autophase.autops(analytic, "acme", return_phases=True)
    return float(phases[0]), float(phases[1])


def apply_phase(data: np.ndarray, p0: float, p1: float, dim: int = -1) -> np.ndarray:
    """Apply zero- and first-order phase correction along *dim*.

    Parameters
    ----------
    data : np.ndarray
        Real or complex spectrum data.
    p0 : float
        Zero-order phase in degrees.
    p1 : float
        First-order phase in degrees.
    dim : int
        Axis along which to apply phasing (default: last axis, -1).

    Notes
    -----
    Processed NMRPipe files (.ft/.ft2/…) store only the real part of the
    spectrum.  Applying a naive ``cos(P0)`` multiplication makes the spectrum
    vanish at ±90°.

    Instead we reconstruct the imaginary (dispersive) component via the
    Hilbert transform, forming the analytic signal, then rotate it by P0/P1:

        phased = Re[ (real + j·H(real)) · exp(j·(P0 + P1·k/N)) ]
               = real·cos(φ) − H(real)·sin(φ)

    This gives proper absorptive→dispersive rotation for any phase angle, as
    nmrDraw does.  For already-complex input the Hilbert step is skipped and
    nmrglue's ps() is used directly.
    """
    orig_dtype = data.dtype
    ndim = data.ndim
    axis = dim % ndim if ndim > 0 else 0

    if np.iscomplexobj(data):
        # Complex data: standard nmrglue path
        if axis == ndim - 1:
            phased = ng.proc_base.ps(data, p0=p0, p1=p1)
        else:
            moved = np.moveaxis(data, axis, -1)
            phased = ng.proc_base.ps(moved, p0=p0, p1=p1)
            phased = np.moveaxis(phased, -1, axis)
        return np.real(phased).astype(orig_dtype)

    # Real data: reconstruct imaginary via Hilbert transform
    # Move target axis to last for uniform processing
    if axis != ndim - 1:
        work = np.moveaxis(data, axis, -1)
    else:
        work = data.copy()

    n = work.shape[-1]
    if n == 0:
        return data.copy().astype(orig_dtype)
    p0_rad = np.deg2rad(p0)
    p1_rad = np.deg2rad(p1)

    # Phase ramp: shape (n,) broadcast over all leading dims.
    # Denominator is max(n-1, 1) so the ramp covers the full P1 sweep
    # across the spectrum (k=0 → 0°, k=n-1 → P1°), matching NMRPipe convention.
    # Also guards against n==1 division by zero.
    k = np.arange(n, dtype=np.float64)
    phase_ramp = np.exp(1j * (p0_rad + p1_rad * k / max(n - 1, 1)))  # shape (n,)

    # Analytic signal along last axis: real + j·H(real)
    analytic = _hilbert(work.astype(np.float64), axis=-1)  # complex128

    # Rotate and keep real part
    phased = np.real(analytic * phase_ramp)

    if axis != ndim - 1:
        phased = np.moveaxis(phased, -1, axis)

    return phased.astype(orig_dtype)


def autophase_2d(
    data: np.ndarray,
    iz: int = 0,
    ia: int = 0,
) -> tuple[np.ndarray, float, float, float, float]:
    """Autophase both X (direct) and Y (indirect) dimensions sequentially.

    Uses maximum-intensity projection along each axis so ACME has full
    coverage of both P0 and P1 even if no 1D slice is active.

    Parameters
    ----------
    data : np.ndarray
        Original (unphased) spectrum data, any dimensionality.
    iz : int
        Z-plane index used to select the representative plane.
    ia : int
        A-plane index (4D spectra).

    Returns
    -------
    (phased_data, p0_x, p1_x, p0_y, p1_y)
    """
    from .spectrum import extract_plane

    plane_orig = extract_plane(data, iz, ia)

    # Step 1: autophase X (direct) on the max-projection row
    p0_x, p1_x = autophase_1d(np.max(plane_orig, axis=0))

    # Step 2: apply X phase to the full dataset
    intermediate = apply_phase(data.copy(), p0_x, p1_x, dim=-1)

    # Step 3: autophase Y (indirect) on the max-projection column of X-phased data
    p0_y, p1_y = autophase_1d(np.max(extract_plane(intermediate, iz, ia), axis=1))

    # Step 4: apply Y phase
    phased = apply_phase(intermediate, p0_y, p1_y, dim=-2)

    return phased, p0_x, p1_x, p0_y, p1_y
