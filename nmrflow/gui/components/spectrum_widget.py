"""Matplotlib-backed spectrum canvas embedded in PySide6."""

from __future__ import annotations
from typing import Optional
import numpy as np

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QSizePolicy

from ...core.spectrum import Spectrum
from ...core.contour import ContourParams, compute_levels
from ...core.peak_table import PeakTable

# Fraction of visible axis range used as full-scale amplitude for 1D traces
_TRACE_SCALE = 0.18


class SpectrumWidget(FigureCanvas):
    """Matplotlib canvas: contour plot + live 1D slice + peak overlay.

    Slice modes
    -----------
    Left-click or H key  → horizontal mode: trace anchored at click Y-PPM,
                           follows mouse horizontally as mouse moves.
    Right-click or V key → vertical mode:   trace anchored at click X-PPM,
                           follows mouse vertically as mouse moves.
    Escape or middle-click → cancel slice mode.

    Signals
    -------
    cursor_moved(x_ppm, y_ppm)
    """

    cursor_moved = Signal(float, float)
    pivot_clicked = Signal(float, float)   # (x_ppm, y_ppm) on middle-click
    slice_mode_changed = Signal(str)       # "H" or "V" when a trace is activated
    draw_error = Signal(str)               # emitted when a draw operation fails

    def __init__(self, parent=None):
        self._fig = Figure(figsize=(6, 6), tight_layout=True)
        super().__init__(self._fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.updateGeometry()

        self._ax = self._fig.add_subplot(111)
        self._style_axes()

        # Spectrum state
        self._spectrum: Optional[Spectrum] = None
        self._peak_table: Optional[PeakTable] = None
        self._contour_params = ContourParams()
        self._plane_mode: str = "XY"   # "XY" | "XZ" | "YZ"
        self._iplane: int = 0          # browse index (Z for XY, Y for XZ, X for YZ)
        self._iz = 0                   # kept in sync with _iplane for XY compat
        self._ia = 0
        self._show_peaks = False

        # Slice state
        # _slice_mode: None | "H" | "V"
        self._slice_mode: Optional[str] = None
        # Anchor position (PPM) — the coordinate that stays fixed while mouse moves
        self._slice_anchor: float = 0.0
        self._last_x_ppm: float = 0.0
        self._last_y_ppm: float = 0.0

        # Drawn artist handles
        self._contour_collections: list = []
        self._peak_scatter = None
        self._peak_labels: list = []
        self._slice_lines: list = []   # [data_line] or [data_line, zero_line]
        self._pivot_line = None        # vertical or horizontal pivot indicator
        self._pivot_ppm: Optional[float] = None
        self._pivot_vertical: bool = True

        self.mpl_connect("motion_notify_event", self._on_motion)
        self.mpl_connect("button_press_event", self._on_press)
        self.mpl_connect("key_press_event", self._on_key)
        self.mpl_connect("scroll_event", self._on_scroll)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_spectrum(self, spectrum: Spectrum,
                      contour_params: Optional[ContourParams] = None):
        self._spectrum = spectrum
        if contour_params is not None:
            self._contour_params = contour_params
        self._slice_mode = None
        self._redraw_all()

    def redraw_data(self, spectrum: Optional[Spectrum] = None,
                    contour_params: Optional[ContourParams] = None):
        """Redraw contours (and slice) without resetting the slice mode/anchor.

        Use this for phase corrections and contour param changes so the
        1D trace stays in place.
        """
        if spectrum is not None:
            self._spectrum = spectrum
        if contour_params is not None:
            self._contour_params = contour_params
        if self._spectrum is None:
            return
        self._ax.cla()
        self._style_axes()
        self._contour_collections.clear()
        self._peak_scatter = None
        self._peak_labels.clear()
        self._slice_lines.clear()
        self._pivot_line = None   # artist removed by cla(); reset handle
        if self._spectrum.ndim == 1:
            self._draw_1d_spectrum()
        else:
            self._setup_axes()
            self._redraw_contours()
            self._redraw_peaks()
            self._redraw_slice()
            self._redraw_pivot_line()
        self.draw_idle()

    def update_slice_only(self, spectrum: Optional[Spectrum] = None):
        """Redraw only the 1D trace with new spectrum data.

        Contours, peaks, and the pivot line are left untouched — only the
        slice lines are removed and redrawn.  Used for live 1D phase preview.
        """
        if spectrum is not None:
            self._spectrum = spectrum
        if self._spectrum is None or self._slice_mode is None:
            return
        self._redraw_slice()
        self.draw_idle()

    def set_contour_params(self, params: ContourParams):
        self._contour_params = params
        if self._spectrum:
            self.redraw_data()

    def set_plane(self, iplane: int, ia: int = 0):
        self._iplane = iplane
        self._iz = iplane   # keep in sync for autophase / backward compat
        self._ia = ia
        if self._spectrum:
            self._redraw_all()

    def set_plane_mode(self, mode: str):
        """Switch the displayed axis pair.  Caller is responsible for redraw."""
        if mode != self._plane_mode:
            self._plane_mode = mode
            self._iplane = 0
            self._iz = 0
            self._slice_mode = None   # reset 1D trace — it belongs to the old view

    def set_peak_table(self, table: Optional[PeakTable]):
        self._peak_table = table
        self._redraw_peaks()
        self.draw_idle()

    def set_show_peaks(self, show: bool):
        self._show_peaks = show
        self._redraw_peaks()
        self.draw_idle()

    def export_postscript(self, path: str):
        self._fig.savefig(path, format="ps", dpi=150)

    def export_png(self, path: str):
        self._fig.savefig(path, format="png", dpi=150)

    def current_iz(self) -> int:
        """Return the current Z-browse (or XY-equivalent) plane index."""
        return self._iz

    def current_ia(self) -> int:
        """Return the current A-dimension index (4D spectra)."""
        return self._ia

    def reset_view(self):
        """Reset axis limits to the full spectrum range and redraw."""
        self._setup_axes()
        self.draw_idle()

    def unload(self):
        """Release the loaded spectrum and peak table, then clear the canvas."""
        self._spectrum = None
        self._peak_table = None
        self._slice_mode = None
        self._pivot_ppm = None
        self._redraw_all()

    # ------------------------------------------------------------------
    # Full redraw
    # ------------------------------------------------------------------

    def _style_axes(self):
        self._ax.set_facecolor("#1a1a2e")
        self._fig.patch.set_facecolor("#1a1a2e")
        self._ax.tick_params(colors="white")
        for spine in self._ax.spines.values():
            spine.set_edgecolor("#555")

    def _redraw_all(self):
        self._ax.cla()
        self._style_axes()
        self._contour_collections.clear()
        self._peak_scatter = None
        self._peak_labels.clear()
        self._slice_lines.clear()
        self._pivot_line = None
        self._pivot_ppm = None

        if self._spectrum is None:
            self.draw_idle()
            return

        if self._spectrum.ndim == 1:
            self._draw_1d_spectrum()
        else:
            self._setup_axes()
            self._redraw_contours()
            self._redraw_peaks()
            self._redraw_slice()
        self.draw_idle()

    def _view(self):
        """Return ``(plane, h_ppm, v_ppm, h_label, v_label, h_uc, v_uc)``."""
        if self._spectrum is None:
            return None
        return self._spectrum.get_view(self._plane_mode, self._iplane, self._ia)

    def _draw_1d_spectrum(self):
        sp = self._spectrum
        ppm_x = sp.ppm_x
        self._ax.plot(ppm_x, sp.data.ravel(), color="#4fc3f7", lw=0.8)
        self._ax.set_xlim(ppm_x.max(), ppm_x.min())
        self._ax.axhline(0, color="#555", lw=0.5)
        self._ax.set_xlabel(sp.label_x + " (ppm)", color="white", fontsize=9)
        self._ax.set_ylabel("Intensity", color="white", fontsize=9)

    def _setup_axes(self):
        v = self._view()
        if v is None:
            return
        _, h_ppm, v_ppm, h_label, v_label, _, _ = v
        self._ax.set_xlim(h_ppm.max(), h_ppm.min())
        self._ax.set_ylim(v_ppm.max(), v_ppm.min())
        self._ax.set_xlabel(h_label + " (ppm)", color="white", fontsize=9)
        self._ax.set_ylabel(v_label + " (ppm)", color="white", fontsize=9)

    def _redraw_contours(self):
        for cs in self._contour_collections:
            try:
                cs.remove()
            except Exception:
                pass
        self._contour_collections.clear()

        v = self._view()
        if v is None:
            return
        plane, h_ppm, v_ppm, _, _, _, _ = v
        noise = self._spectrum.noise_level(self._iplane, self._ia)
        levels = compute_levels(self._contour_params, noise)

        if len(levels.pos):
            try:
                cs = self._ax.contour(h_ppm, v_ppm, plane,
                                      levels=levels.pos, colors=levels.pos_color,
                                      linewidths=0.6, alpha=0.9)
                self._contour_collections.append(cs)
            except Exception as exc:
                self.draw_error.emit(f"Contour draw error (pos): {exc}")
        if len(levels.neg):
            try:
                cs = self._ax.contour(h_ppm, v_ppm, plane,
                                      levels=levels.neg, colors=levels.neg_color,
                                      linewidths=0.6, alpha=0.7, linestyles="dashed")
                self._contour_collections.append(cs)
            except Exception as exc:
                self.draw_error.emit(f"Contour draw error (neg): {exc}")

    def _redraw_peaks(self):
        if self._peak_scatter is not None:
            try:
                self._peak_scatter.remove()
            except Exception:
                pass
            self._peak_scatter = None
        for lbl in self._peak_labels:
            try:
                lbl.remove()
            except Exception:
                pass
        self._peak_labels.clear()

        if not self._show_peaks or self._peak_table is None:
            return
        xs, ys = self._peak_table.x_ppms(), self._peak_table.y_ppms()
        if not xs:
            return
        self._peak_scatter = self._ax.scatter(
            xs, ys, marker="+", s=80, c="#ff4444", linewidths=1.2, alpha=0.85, zorder=5)
        for peak in self._peak_table.peaks:
            if peak.label:
                lbl = self._ax.annotate(
                    peak.label, (peak.x_ppm, peak.y_ppm),
                    textcoords="offset points", xytext=(4, 4),
                    fontsize=6, color="#ffaaaa", zorder=6)
                self._peak_labels.append(lbl)

    # ------------------------------------------------------------------
    # Live 1D slice
    # ------------------------------------------------------------------

    def _clear_slice_lines(self):
        for ln in self._slice_lines:
            try:
                ln.remove()
            except Exception:
                pass
        self._slice_lines.clear()

    # ------------------------------------------------------------------
    # Pivot indicator
    # ------------------------------------------------------------------

    def draw_pivot_line(self, ppm: float, vertical: bool = True):
        """Draw (or move) the pivot indicator line. Called by the main window."""
        self._pivot_ppm = ppm
        self._pivot_vertical = vertical
        self._redraw_pivot_line()
        self.draw_idle()

    def _redraw_pivot_line(self):
        """Re-draw the pivot line from stored state (survives redraw_data)."""
        if self._pivot_ppm is None or self._spectrum is None:
            if self._pivot_line is not None:
                self._remove_artist(self._pivot_line)
                self._pivot_line = None
            return

        kw = dict(color="white", lw=0.8, alpha=0.5, linestyle="--", zorder=5)

        if self._pivot_line is not None:
            # Update in place — avoids remove() which raises NotImplementedError
            # on Line2D objects in some matplotlib versions.
            xd = self._pivot_line.get_xdata()
            line_is_vertical = len(xd) == 2 and xd[0] == xd[1]
            if line_is_vertical == self._pivot_vertical:
                if self._pivot_vertical:
                    self._pivot_line.set_xdata([self._pivot_ppm, self._pivot_ppm])
                else:
                    self._pivot_line.set_ydata([self._pivot_ppm, self._pivot_ppm])
                return   # done — no need to recreate
            # Orientation flipped: must replace the artist
            self._remove_artist(self._pivot_line)
            self._pivot_line = None

        if self._pivot_vertical:
            self._pivot_line = self._ax.axvline(self._pivot_ppm, **kw)
        else:
            self._pivot_line = self._ax.axhline(self._pivot_ppm, **kw)

    def _remove_artist(self, artist) -> None:
        """Remove *artist* from its axes as robustly as possible."""
        try:
            artist.remove()
        except Exception:
            pass
        try:
            if artist in self._ax.lines:
                self._ax.lines.remove(artist)
        except Exception:
            pass

    def _ppm_to_pt(self, uc, ppm: float) -> int:
        """Convert PPM to the nearest integer point index."""
        return int(round(float(uc(ppm, "ppm"))))

    def _redraw_slice(self):
        """Draw (or update) the 1D trace for the current slice mode/anchor."""
        self._clear_slice_lines()
        if self._slice_mode is None or self._spectrum is None:
            return

        v = self._view()
        if v is None:
            return
        plane, h_ppm, v_ppm, _, _, h_uc, v_uc = v

        if self._slice_mode == "H":
            # Horizontal slice: anchor = v_ppm coordinate, trace along h axis
            anchor_ppm = self._slice_anchor
            pt_v = max(0, min(plane.shape[0] - 1, self._ppm_to_pt(v_uc, anchor_ppm)))
            trace = plane[pt_v, :]       # row → trace along horizontal axis
            ppm_axis = h_ppm

            # Positive peaks go upward on screen (Y axis inverted)
            ylim = self._ax.get_ylim()
            y_range = abs(ylim[1] - ylim[0])
            max_amp = float(np.max(np.abs(trace))) if trace.size else 0.0
            max_amp = max_amp or 1.0
            scaled = trace / max_amp * y_range * _TRACE_SCALE
            y_values = anchor_ppm - scaled

            line, = self._ax.plot(ppm_axis, y_values,
                                  color="#ffcc00", lw=0.9, alpha=0.9, zorder=4)
            zero, = self._ax.plot(
                [ppm_axis.min(), ppm_axis.max()], [anchor_ppm, anchor_ppm],
                color="#ffcc00", lw=0.4, alpha=0.4, linestyle="--", zorder=3)
            self._slice_lines = [line, zero]

        else:  # "V"
            # Vertical slice: anchor = h_ppm coordinate, trace along v axis
            anchor_ppm = self._slice_anchor
            pt_h = max(0, min(plane.shape[1] - 1, self._ppm_to_pt(h_uc, anchor_ppm)))
            trace = plane[:, pt_h]       # column → trace along vertical axis
            ppm_axis = v_ppm

            # Positive peaks go rightward on screen (X axis inverted)
            xlim = self._ax.get_xlim()
            x_range = abs(xlim[1] - xlim[0])
            max_amp = float(np.max(np.abs(trace))) if trace.size else 0.0
            max_amp = max_amp or 1.0
            scaled = trace / max_amp * x_range * _TRACE_SCALE
            x_values = anchor_ppm - scaled

            line, = self._ax.plot(x_values, ppm_axis,
                                  color="#00ffcc", lw=0.9, alpha=0.9, zorder=4)
            zero, = self._ax.plot(
                [anchor_ppm, anchor_ppm], [ppm_axis.min(), ppm_axis.max()],
                color="#00ffcc", lw=0.4, alpha=0.4, linestyle="--", zorder=3)
            self._slice_lines = [line, zero]

    def _update_live_slice(self, x_ppm: float, y_ppm: float):
        """Update slice anchor from current mouse position and redraw."""
        if self._slice_mode == "H":
            self._slice_anchor = y_ppm   # horizontal → anchor moves with Y
        else:
            self._slice_anchor = x_ppm   # vertical → anchor moves with X
        self._redraw_slice()
        self.draw_idle()

    # ------------------------------------------------------------------
    # Mouse / keyboard handlers
    # ------------------------------------------------------------------

    def _set_slice_mode(self, mode: Optional[str]):
        """Set slice mode and emit slice_mode_changed when activating H or V."""
        self._slice_mode = mode
        if mode is not None:
            self.slice_mode_changed.emit(mode)

    def _on_key(self, event):
        key = (event.key or "").lower()
        if key == "h":
            self._set_slice_mode("H")
            self._slice_anchor = self._last_y_ppm
            self._redraw_slice()
            self.draw_idle()
        elif key == "v":
            self._set_slice_mode("V")
            self._slice_anchor = self._last_x_ppm
            self._redraw_slice()
            self.draw_idle()
        elif key in ("escape", "e"):
            self._slice_mode = None
            self._clear_slice_lines()
            self.draw_idle()

    def _on_motion(self, event):
        if event.inaxes != self._ax or event.xdata is None or event.ydata is None:
            return
        self._last_x_ppm = event.xdata
        self._last_y_ppm = event.ydata
        self.cursor_moved.emit(event.xdata, event.ydata)

    def _on_press(self, event):
        # Middle-click: set pivot using event coords if inside axes,
        # otherwise fall back to last known cursor position.
        if event.button == 2:
            in_axes = event.inaxes == self._ax and event.xdata is not None
            x = event.xdata if in_axes else self._last_x_ppm
            y = event.ydata if in_axes else self._last_y_ppm
            self.pivot_clicked.emit(x, y)
            return

        if event.inaxes != self._ax or event.xdata is None:
            return
        if event.button == 1:
            # Left click: move the trace in whichever dimension is already active.
            # If no slice is active yet, default to horizontal.
            mode = self._slice_mode or "H"
            self._set_slice_mode(mode)
            self._slice_anchor = event.ydata if mode == "H" else event.xdata
            self._redraw_slice()
            self.draw_idle()
        elif event.button == 3:     # right click → vertical slice
            self._set_slice_mode("V")
            self._slice_anchor = event.xdata
            self._redraw_slice()
            self.draw_idle()

    def _on_scroll(self, event):
        if event.inaxes != self._ax:
            return
        factor = 0.85 if event.step > 0 else 1.0 / 0.85
        cx, cy = event.xdata, event.ydata
        xlim = self._ax.get_xlim()
        ylim = self._ax.get_ylim()
        self._ax.set_xlim([cx + (x - cx) * factor for x in xlim])
        self._ax.set_ylim([cy + (y - cy) * factor for y in ylim])
        # Rescale trace to new axis limits
        if self._slice_mode:
            self._redraw_slice()
        self.draw_idle()
