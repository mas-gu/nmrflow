"""Spectrum data container exposing PPM axes and plane access."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import numpy as np

from .pipe_reader import (
    read_spectrum, make_unit_converters,
    read_ucsf, make_unit_converters_ucsf,
)


def extract_plane(data: np.ndarray, iz: int = 0, ia: int = 0) -> np.ndarray:
    """Extract a 2-D plane from *data* at Z-index *iz* and A-index *ia*.

    Mirrors the indexing logic of ``Spectrum.get_plane`` but works on any
    array, making it reusable without a full ``Spectrum`` object.

    Returns a **view** into *data* for all dimensionalities.  For 2-D input
    the entire array is returned as-is.  Callers that need to modify the
    result without affecting the source must call ``.copy()`` themselves.
    """
    ndim = data.ndim
    if ndim == 2:
        return data
    if ndim == 3:
        return data[int(iz) % data.shape[0]]
    if ndim == 4:
        return data[int(ia) % data.shape[0], int(iz) % data.shape[1]]
    return data.reshape(-1, data.shape[-2], data.shape[-1])[iz]


class Spectrum:
    """Wraps an NMRPipe dataset (dic + data) with convenient accessors.

    Attributes
    ----------
    dic : dict
        NMRPipe header dictionary from nmrglue.
    data : np.ndarray
        Raw spectral data array (float32 or float64).
    uc : list
        Unit-conversion objects, one per axis (outermost → innermost).
    path : str
        Original file path / filemask used to open the spectrum.
    """

    def __init__(self, dic: dict, data: np.ndarray, path: str = "",
                 uc: Optional[list] = None):
        self.dic = dic
        self.data = data
        self.path = path
        self.uc = uc if uc is not None else make_unit_converters(dic, data)

    # ------------------------------------------------------------------
    # Class method constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_file(cls, path: str | Path) -> "Spectrum":
        """Read an NMRPipe file/filemask or a UCSF/Sparky file."""
        p = str(path)
        if Path(path).suffix.lower() == ".ucsf":
            dic, data = read_ucsf(p)
            return cls(dic, data, path=p, uc=make_unit_converters_ucsf(dic, data))
        dic, data = read_spectrum(p)
        return cls(dic, data, path=p)

    # ------------------------------------------------------------------
    # Shape / dimensionality
    # ------------------------------------------------------------------

    @property
    def ndim(self) -> int:
        return self.data.ndim

    @property
    def shape(self) -> tuple:
        return self.data.shape

    # ------------------------------------------------------------------
    # PPM axes
    # ------------------------------------------------------------------

    @property
    def ppm_x(self) -> np.ndarray:
        """PPM axis for the *direct* (innermost) dimension."""
        return self.uc[-1].ppm_scale()

    @property
    def ppm_y(self) -> np.ndarray:
        """PPM axis for the first *indirect* dimension."""
        if self.ndim < 2:
            raise ValueError("Spectrum has only one dimension")
        return self.uc[-2].ppm_scale()

    @property
    def ppm_z(self) -> Optional[np.ndarray]:
        """PPM axis for the second indirect dimension (3-D only)."""
        if self.ndim < 3:
            return None
        return self.uc[-3].ppm_scale()

    # ------------------------------------------------------------------
    # Label helpers
    # ------------------------------------------------------------------

    def _label(self, axis_index: int) -> str:
        """Return the nucleus label for *axis_index* (0 = outermost).

        Supports both NMRPipe (FDF1LABEL, FDF2LABEL, …) and UCSF/Sparky
        (w1.nucleus, w2.nucleus, …) header formats.
        """
        # NMRPipe format
        try:
            key = f"FDF{axis_index + 1}LABEL"
            raw = self.dic.get(key, b"")
            if isinstance(raw, (bytes, bytearray)):
                label = raw.decode().strip("\x00").strip()
            else:
                label = str(raw).strip()
            if label:
                return label
        except Exception:
            pass

        # UCSF/Sparky format: w1, w2, … each have a 'nucleus' field
        try:
            wn = f"w{axis_index + 1}"
            if wn in self.dic:
                nucleus = str(self.dic[wn].get("nucleus", "")).strip()
                if nucleus:
                    return nucleus
        except Exception:
            pass

        return f"Dim{axis_index}"

    @property
    def label_x(self) -> str:
        return self._label(self.ndim - 1)

    @property
    def label_y(self) -> str:
        return self._label(self.ndim - 2) if self.ndim >= 2 else ""

    @property
    def label_z(self) -> str:
        return self._label(self.ndim - 3) if self.ndim >= 3 else ""

    # ------------------------------------------------------------------
    # Plane extraction
    # ------------------------------------------------------------------

    def get_view(self, mode: str = "XY", iplane: int = 0, ia: int = 0) -> tuple:
        """Return ``(plane, h_ppm, v_ppm, h_label, v_label, h_uc, v_uc)``.

        *mode* selects which pair of axes to display:

        * ``"XY"`` — direct (H) vs first-indirect (V), browse Z.  Works for 2D.
        * ``"XZ"`` — direct (H) vs second-indirect/Z (V), browse Y.  3D only.
        * ``"YZ"`` — first-indirect (H) vs second-indirect/Z (V), browse X. 3D only.

        *iplane* is the index along the browse dimension.
        *ia* is the A-dimension index for 4D spectra (ignored for ≤ 3D).
        The returned *plane* always has shape ``(n_v, n_h)`` to match
        ``ax.contour(h_ppm, v_ppm, plane)``.
        """
        if self.ndim < 3:
            # 2D spectrum — only XY makes sense; iplane is irrelevant
            return (self.get_plane(),
                    self.ppm_x, self.ppm_y,
                    self.label_x, self.label_y,
                    self.uc[-1], self.uc[-2])

        if mode == "XY":
            iz = int(iplane) % self.shape[-3]
            plane = self.get_plane(iz, ia)
            return (plane,
                    self.ppm_x, self.ppm_y,
                    self.label_x, self.label_y,
                    self.uc[-1], self.uc[-2])

        if mode == "XZ":
            iy = int(iplane) % self.shape[-2]
            if self.ndim == 3:
                plane = self.data[:, iy, :]
            else:
                ia_idx = int(ia) % self.shape[0]
                plane = self.data[ia_idx, :, iy, :]
            return (plane,
                    self.ppm_x, self.ppm_z,
                    self.label_x, self.label_z,
                    self.uc[-1], self.uc[-3])

        if mode == "YZ":
            ix = int(iplane) % self.shape[-1]
            if self.ndim == 3:
                plane = self.data[:, :, ix]
            else:
                ia_idx = int(ia) % self.shape[0]
                plane = self.data[ia_idx, :, :, ix]
            return (plane,
                    self.ppm_y, self.ppm_z,
                    self.label_y, self.label_z,
                    self.uc[-2], self.uc[-3])

        raise ValueError(f"Unknown plane mode: {mode!r}")

    def n_planes(self, mode: str = "XY") -> int:
        """Number of planes in the browse dimension for *mode*."""
        if self.ndim < 3:
            return 1
        if mode == "XY":
            return self.shape[-3]
        if mode == "XZ":
            return self.shape[-2]
        if mode == "YZ":
            return self.shape[-1]
        return self.shape[-3]

    def ppm_browse(self, mode: str = "XY") -> Optional[np.ndarray]:
        """PPM axis for the browse (stepped) dimension."""
        if self.ndim < 3:
            return None
        if mode == "XY":
            return self.ppm_z
        if mode == "XZ":
            return self.ppm_y
        if mode == "YZ":
            return self.ppm_x
        return self.ppm_z

    def get_plane(self, iz: int = 0, ia: int = 0) -> np.ndarray:
        """Return the 2-D plane at indices *iz* (Z) and *ia* (A).

        For 2-D spectra, returns the data as-is.
        For 3-D spectra, returns ``data[iz]``.
        For 4-D spectra, returns ``data[ia, iz]``.
        """
        return extract_plane(self.data, iz, ia)

    # ------------------------------------------------------------------
    # Row / column slices (1-D traces)
    # ------------------------------------------------------------------

    def row_slice(self, pt_y: int, iz: int = 0, ia: int = 0) -> np.ndarray:
        """Return the X-axis row at *pt_y* from the current plane."""
        plane = self.get_plane(iz, ia)
        row = int(pt_y) % plane.shape[0]
        return plane[row, :]

    def col_slice(self, pt_x: int, iz: int = 0, ia: int = 0) -> np.ndarray:
        """Return the Y-axis column at *pt_x* from the current plane."""
        plane = self.get_plane(iz, ia)
        col = int(pt_x) % plane.shape[1]
        return plane[:, col]

    # ------------------------------------------------------------------
    # Noise estimate
    # ------------------------------------------------------------------

    def noise_level(self, iz: int = 0, ia: int = 0) -> float:
        """Rough noise estimate via the MAD of the current plane.

        *iz* and *ia* should match the currently displayed plane so that the
        noise estimate reflects the data on screen, not always plane 0.
        """
        plane = self.get_plane(iz, ia)
        return float(np.median(np.abs(plane - np.median(plane)))) * 1.4826

    def __repr__(self) -> str:
        return f"Spectrum(path={self.path!r}, shape={self.shape}, ndim={self.ndim})"
