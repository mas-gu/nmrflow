"""NMRDrawWindow — main application window."""

from __future__ import annotations
import argparse
import os
import re
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QDockWidget, QStatusBar, QFileDialog, QMenuBar,
    QMenu, QSplitter, QLabel,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QKeySequence

from ..core.spectrum import Spectrum, extract_plane
from ..core.pipe_reader import detect_filemask, find_filemask_in_folder
from ..core.contour import ContourParams, compute_levels
from ..core.peak_table import PeakTable
from ..core.phase import apply_phase, autophase_2d
from .components.spectrum_widget import SpectrumWidget
from .components.contour_panel import ContourPanel
from .components.phase_panel import PhasePanel
from .components.file_browser import FileBrowser
from .components.slice_controls import SliceControls
from .components.autophase_dialog import AutoPhaseResultDialog
from .components.com_panel import ComPanel
from ..core.com_parser import find_com_script


class NMRDrawWindow(QMainWindow):
    """Main application window mimicking nmrDraw's layout.

    Layout
    ------
    Left dock:  ContourPanel + PhasePanel + SliceControls
    Right dock: FileBrowser
    Centre:     SpectrumWidget (matplotlib canvas)
    Bottom:     status bar (cursor PPM coordinates)
    """

    def __init__(self, args: argparse.Namespace, parent=None):
        super().__init__(parent)
        self._args = args
        self._spectrum: Optional[Spectrum] = None
        self._peak_table: Optional[PeakTable] = None
        self._original_data = None   # unphased data kept for re-application
        self._plane_mode: str = "XY"  # mirrors SpectrumWidget._plane_mode
        # Accumulated phase corrections on top of baked-in ft*.com values
        self._phase_correction_x: tuple[float, float] = (0.0, 0.0)
        self._phase_correction_y: tuple[float, float] = (0.0, 0.0)

        self.setWindowTitle("nmrflow — NMR Spectrum Viewer")
        self.resize(1200, 800)

        self._build_central()
        self._build_docks()
        self._build_menus()
        self._build_status_bar()
        self._connect_signals()

        # Apply initial CLI args to panels
        self._apply_initial_args()

    # ------------------------------------------------------------------
    # Widget construction
    # ------------------------------------------------------------------

    def _build_central(self):
        self._spectrum_widget = SpectrumWidget(self)
        self.setCentralWidget(self._spectrum_widget)

    def _build_docks(self):
        # Left dock — controls
        left_dock = QDockWidget("Controls", self)
        left_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea |
                                   Qt.DockWidgetArea.RightDockWidgetArea)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.setSpacing(4)

        self._contour_panel = ContourPanel()
        self._phase_panel = PhasePanel()
        self._slice_controls = SliceControls()

        left_layout.addWidget(self._contour_panel)
        left_layout.addWidget(self._phase_panel)
        left_layout.addWidget(self._slice_controls)
        left_layout.addStretch()

        left_dock.setWidget(left_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, left_dock)

        # Right dock — file browser
        right_dock = QDockWidget("Files", self)
        right_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea |
                                    Qt.DockWidgetArea.RightDockWidgetArea)
        self._file_browser = FileBrowser()
        right_dock.setWidget(self._file_browser)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, right_dock)
        right_dock.hide()   # hidden by default, user opens from menu

        self._right_dock = right_dock

        # Right dock — Script Editor (ft2d.com / ft3d.com viewer + runner)
        script_dock = QDockWidget("Script Editor", self)
        script_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._com_panel = ComPanel()
        script_dock.setWidget(self._com_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, script_dock)
        script_dock.hide()   # shown automatically when a .com is found
        self._script_dock = script_dock

    def _build_menus(self):
        mb = self.menuBar()

        # File menu
        file_menu = mb.addMenu("&File")
        act_open = QAction("&Open…", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._open_file_dialog)
        file_menu.addAction(act_open)

        act_open_folder = QAction("Open &Folder (3D)…", self)
        act_open_folder.setShortcut("Ctrl+Shift+O")
        act_open_folder.triggered.connect(self._open_folder_dialog)
        file_menu.addAction(act_open_folder)

        file_menu.addSeparator()
        act_ps = QAction("Save PostScript…", self)
        act_ps.triggered.connect(self._save_postscript)
        file_menu.addAction(act_ps)

        act_png = QAction("Save PNG…", self)
        act_png.triggered.connect(self._save_png)
        file_menu.addAction(act_png)

        file_menu.addSeparator()
        act_quit = QAction("&Quit", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # View menu
        view_menu = mb.addMenu("&View")
        act_files = QAction("Show &File Browser", self)
        act_files.setCheckable(True)
        act_files.triggered.connect(self._right_dock.setVisible)
        view_menu.addAction(act_files)

        act_peaks = QAction("Show &Peaks", self)
        act_peaks.setCheckable(True)
        act_peaks.triggered.connect(self._toggle_peaks)
        view_menu.addAction(act_peaks)
        self._act_peaks = act_peaks

        act_reset = QAction("&Reset Zoom", self)
        act_reset.setShortcut("Ctrl+0")
        act_reset.triggered.connect(self._reset_zoom)
        view_menu.addAction(act_reset)

        act_script = QAction("Show &Script Editor", self)
        act_script.setCheckable(True)
        act_script.setChecked(False)
        act_script.triggered.connect(self._script_dock.setVisible)
        self._script_dock.visibilityChanged.connect(act_script.setChecked)
        view_menu.addAction(act_script)

        # Peak menu
        peak_menu = mb.addMenu("&Peaks")
        act_load_peaks = QAction("&Load Peak Table…", self)
        act_load_peaks.triggered.connect(self._load_peak_dialog)
        peak_menu.addAction(act_load_peaks)

    def _build_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._cursor_label = QLabel("x: –  y: –")
        self._status_bar.addPermanentWidget(self._cursor_label)
        self._file_label = QLabel("No file loaded")
        self._status_bar.addWidget(self._file_label)

    def _connect_signals(self):
        self._spectrum_widget.cursor_moved.connect(self._on_cursor_moved)
        self._spectrum_widget.pivot_clicked.connect(self._on_pivot_clicked)
        self._spectrum_widget.slice_mode_changed.connect(self._on_slice_mode_changed)
        self._spectrum_widget.draw_error.connect(
            lambda msg: self._status_bar.showMessage(msg, 5000)
        )
        self._contour_panel.params_changed.connect(self._on_contour_params_changed)
        self._phase_panel.phase_changed.connect(self._on_phase_changed)
        self._phase_panel.phase_apply_2d.connect(self._on_phase_apply_2d)
        self._phase_panel.phase_auto_requested.connect(self._on_phase_auto_requested)
        self._file_browser.file_selected.connect(self.open_spectrum)
        self._slice_controls.plane_changed.connect(self._on_plane_changed)
        self._slice_controls.plane_mode_changed.connect(self._on_plane_mode_changed)
        self._com_panel.run_finished.connect(self._on_script_run_finished)
        self._com_panel.status_message.connect(
            lambda msg: self._status_bar.showMessage(msg, 5000)
        )

    def _apply_initial_args(self):
        args = self._args
        # Contour panel
        self._contour_panel.set_from_args(args)
        # Phase panel
        self._phase_panel.set_p0(args.p0)
        self._phase_panel.set_p1(args.p1)
        # Peak display
        if getattr(args, "show_peaks", False):
            self._act_peaks.setChecked(True)
            self._spectrum_widget.set_show_peaks(True)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def open_spectrum(self, path: str):
        """Load a spectrum file (or filemask) and redraw the canvas.

        When *path* points to a single numbered plane (e.g. ``test001.ft3``)
        and sibling planes exist in the same directory, the full 3D filemask
        is detected automatically so the whole series is loaded at once.
        """
        # Auto-upgrade a single numbered plane to the full 3D filemask
        if "%" not in path and Path(path).suffix in (".ft3", ".ft4"):
            mask = detect_filemask(path)
            if mask:
                path = mask

        try:
            self._spectrum = Spectrum.from_file(path)
        except Exception as exc:
            self._status_bar.showMessage(f"Error loading {path}: {exc}", 5000)
            return

        self._file_label.setText(Path(path).name)
        self.setWindowTitle(f"nmrflow — {Path(path).name}")

        # Release previous copy before allocating the new one to avoid
        # briefly holding two large arrays simultaneously.
        self._original_data = None
        self._original_data = self._spectrum.data.copy()

        # Update slice controls for 3D/4D
        self._slice_controls.configure(self._spectrum)

        # Build initial contour params from current panel state
        params = self._contour_panel.get_params()

        # Apply initial phase if non-zero
        args = self._args
        if args.p0 != 0.0 or args.p1 != 0.0:
            self._apply_phase_to_spectrum(args.p0, args.p1, dim=-1)

        self._spectrum_widget.load_spectrum(self._spectrum, params)

        # Auto-load peak table if -peak flag and companion .tab exists.
        # Strip filemask format specifiers (e.g. %03d) before inferring the .tab path.
        if getattr(args, "show_peaks", False) and args.infile:
            p = Path(args.infile)
            clean_stem = re.sub(r"%[0-9]*d", "", p.stem)
            tab_path = str(p.parent / (clean_stem + ".tab"))
            if os.path.exists(tab_path):
                self._load_peak_table(tab_path)
        if getattr(args, "peak_file", None) and os.path.exists(args.peak_file):
            self._load_peak_table(args.peak_file)

        # Auto-detect companion ft*.com script
        self._load_com_script_for(path)

    def _load_com_script_for(self, spectrum_path: str):
        """Find and load a ft*.com script alongside the spectrum, if present."""
        # Reset accumulated corrections whenever a new spectrum is opened
        self._phase_correction_x = (0.0, 0.0)
        self._phase_correction_y = (0.0, 0.0)
        com_path = find_com_script(spectrum_path)
        if com_path is None:
            return
        self._com_panel.load_file(com_path)
        self._script_dock.show()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(float, float)
    def _on_cursor_moved(self, x: float, y: float):
        self._cursor_label.setText(f"x: {x:.3f} ppm  y: {y:.3f} ppm")

    @Slot(str)
    def _on_slice_mode_changed(self, mode: str):
        """Slot kept for future use; slice clicks no longer change the phasing dim."""

    @Slot(object)
    def _on_contour_params_changed(self, params: ContourParams):
        self._spectrum_widget.set_contour_params(params)

    def _apply_phase_to_spectrum(self, p0: float, p1: float, dim: int = -1):
        """Apply phase to a fresh copy of the original data (non-destructive)."""
        self._spectrum.data = apply_phase(self._original_data.copy(), p0, p1, dim=dim)

    def _compute_p0_eff(self, p0: float, p1: float,
                         pivot_ppm: float, dim: int) -> float:
        """Return P0 adjusted so phase is fixed at the pivot point."""
        ndim = self._spectrum.data.ndim
        # Resolve negative index and reject out-of-range dims (e.g. dim=-2 on 1D)
        resolved = dim if dim >= 0 else ndim + dim
        if resolved < 0 or resolved >= ndim:
            return p0
        try:
            uc = self._spectrum.uc[dim]
            n  = self._spectrum.data.shape[dim]
            fraction = float(uc(pivot_ppm, "ppm")) / n
            return p0 - p1 * fraction
        except Exception:
            return p0

    @Slot(float, float, float, int)
    def _on_phase_changed(self, p0: float, p1: float, pivot_ppm: float, dim: int):
        """Live 1D-trace-only phase preview (Phasing On/Off)."""
        if self._spectrum is None or self._original_data is None:
            return
        p0_eff = self._compute_p0_eff(p0, p1, pivot_ppm, dim)
        try:
            self._apply_phase_to_spectrum(p0_eff, p1, dim=dim)
        except Exception as exc:
            self._status_bar.showMessage(f"Phase error: {exc}", 3000)
            return
        # Update the 1D trace only — contours stay at the previous phase
        self._spectrum_widget.update_slice_only(self._spectrum)

    @Slot(float, float, float, int)
    def _on_phase_apply_2d(self, p0: float, p1: float, pivot_ppm: float, dim: int):
        """Full 2D contour redraw (Update 2D button)."""
        if self._spectrum is None or self._original_data is None:
            return
        p0_eff = self._compute_p0_eff(p0, p1, pivot_ppm, dim)
        try:
            self._apply_phase_to_spectrum(p0_eff, p1, dim=dim)
        except Exception as exc:
            self._status_bar.showMessage(f"Phase error: {exc}", 3000)
            return
        params = self._contour_panel.get_params()
        self._spectrum_widget.redraw_data(self._spectrum, params)
        self._update_com_for_phase(p0_eff, p1, dim)

    def _update_com_for_phase(self, p0_eff: float, p1: float, dim: int):
        """Push current phase correction into the Script Editor's PS values.

        Tracks corrections per-dimension so that phasing X then Y accumulates
        correctly in the .com text.  Only fires when a .com file is loaded.
        """
        if self._com_panel.com_path is None:
            return
        if dim == -1:
            self._phase_correction_x = (p0_eff, p1)
        elif dim == -2:
            self._phase_correction_y = (p0_eff, p1)
        else:
            return
        self._com_panel.update_ps_from_panel(
            p0_x_correction=self._phase_correction_x[0],
            p1_x_correction=self._phase_correction_x[1],
            p0_y_correction=self._phase_correction_y[0],
            p1_y_correction=self._phase_correction_y[1],
        )

    @Slot()
    def _on_script_run_finished(self):
        """After a successful ft*.com run: reload spectrum and reset phase panel."""
        if self._spectrum is None:
            return
        # Reset accumulated corrections — the new .ft file is already fully phased
        self._phase_correction_x = (0.0, 0.0)
        self._phase_correction_y = (0.0, 0.0)
        self._phase_panel.set_p0(0.0)
        self._phase_panel.set_p1(0.0)
        self.open_spectrum(self._spectrum.path)

    @Slot()
    def _on_phase_auto_requested(self):
        """Auto-phase both X and Y dimensions sequentially."""
        if self._spectrum is None or self._original_data is None:
            return
        iz = self._spectrum_widget.current_iz()
        ia = self._spectrum_widget.current_ia()
        phased, p0_x, p1_x, p0_y, p1_y = autophase_2d(self._original_data, iz, ia)

        dlg = AutoPhaseResultDialog(p0_x, p1_x, p0_y, p1_y, parent=self)
        if dlg.exec() != AutoPhaseResultDialog.DialogCode.Accepted:
            return  # user cancelled — data left unchanged

        self._spectrum.data = phased
        self._phase_panel.set_p0(p0_x)
        self._phase_panel.set_p1(p1_x)
        self._phase_panel.set_autophase_result(p0_x, p1_x, p0_y, p1_y)
        params = self._contour_panel.get_params()
        self._spectrum_widget.redraw_data(self._spectrum, params)
        self._status_bar.showMessage(
            f"Auto-phase — X: P0={p0_x:.1f}°  P1={p1_x:.1f}° | "
            f"Y: P0={p0_y:.1f}°  P1={p1_y:.1f}°", 6000
        )

    @Slot(float, float)
    def _on_pivot_clicked(self, x_ppm: float, y_ppm: float):
        """Middle-click on canvas: set pivot PPM from cursor position."""
        dim = self._phase_panel.current_dim()
        # Pick coordinate based on which dimension we're phasing
        if dim == -2:   # Y (indirect) → horizontal pivot
            pivot_ppm = y_ppm
            vertical = False
        else:           # X (direct) or Z → vertical pivot
            pivot_ppm = x_ppm
            vertical = True
        self._phase_panel.set_pivot_ppm(pivot_ppm)
        self._spectrum_widget.draw_pivot_line(pivot_ppm, vertical=vertical)

    @Slot(str)
    def _on_plane_mode_changed(self, mode: str):
        """XY / XZ / YZ button clicked — switch displayed axes and redraw."""
        self._plane_mode = mode
        if self._spectrum is None:
            return
        self._spectrum_widget.set_plane_mode(mode)
        params = self._contour_panel.get_params()
        self._spectrum_widget.redraw_data(self._spectrum, params)

    @Slot(int, int)
    def _on_plane_changed(self, iz: int, ia: int):
        self._spectrum_widget.set_plane(iz, ia)
        if self._spectrum is not None:
            ppm_z = self._spectrum.ppm_z
            if ppm_z is not None and 0 <= iz < len(ppm_z):
                label_z = self._spectrum.label_z or "Z"
                fname = Path(self._spectrum.path).name
                nz = len(ppm_z)
                self._file_label.setText(
                    f"{fname}  │  {label_z}: {ppm_z[iz]:.3f} ppm"
                    f"  [{iz + 1}/{nz}]"
                )

    @Slot(bool)
    def _toggle_peaks(self, checked: bool):
        self._spectrum_widget.set_show_peaks(checked)

    def _reset_zoom(self):
        if self._spectrum is None:
            return
        self._spectrum_widget.reset_view()

    # ------------------------------------------------------------------
    # File dialogs
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        """Page Up / Page Down step through planes of a 3D spectrum."""
        if self._spectrum is not None and self._spectrum.ndim >= 3:
            key = event.key()
            if key == Qt.Key.Key_PageUp:
                self._slice_controls.step_iz(-1)
                return
            if key == Qt.Key.Key_PageDown:
                self._slice_controls.step_iz(+1)
                return
        super().keyPressEvent(event)

    def _open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open NMRPipe Spectrum", "",
            "NMR spectra (*.ft *.ft2 *.ft3 *.ft4 *.fid *.dat *.ucsf);;All files (*)"
        )
        if path:
            self.open_spectrum(path)

    def _open_folder_dialog(self):
        """Browse for a directory containing a 3D NMRPipe plane series."""
        folder = QFileDialog.getExistingDirectory(
            self, "Open 3D Spectrum Folder", ""
        )
        if not folder:
            return
        mask = find_filemask_in_folder(folder)
        if mask:
            self.open_spectrum(mask)
        else:
            self._status_bar.showMessage(
                f"No NMRPipe plane series found in {folder}", 4000
            )

    def _load_peak_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Peak Table", "", "Peak tables (*.tab);;All files (*)"
        )
        if path:
            self._load_peak_table(path)

    def _load_peak_table(self, path: str):
        try:
            self._peak_table = PeakTable.from_file(path)
            self._spectrum_widget.set_peak_table(self._peak_table)
            self._act_peaks.setChecked(True)
            self._spectrum_widget.set_show_peaks(True)
            self._status_bar.showMessage(
                f"Loaded {len(self._peak_table)} peaks from {Path(path).name}", 3000
            )
        except Exception as exc:
            self._status_bar.showMessage(f"Error loading peaks: {exc}", 5000)

    def _save_postscript(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PostScript", "spectrum.ps", "PostScript (*.ps)"
        )
        if path:
            self._spectrum_widget.export_postscript(path)
            self._status_bar.showMessage(f"Saved {path}", 3000)

    def _save_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PNG", "spectrum.png", "PNG images (*.png)"
        )
        if path:
            self._spectrum_widget.export_png(path)
            self._status_bar.showMessage(f"Saved {path}", 3000)
