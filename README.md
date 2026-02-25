# nmrflow

A Python/PySide6 NMR spectrum viewer for NMRPipe format files, built as a modern replacement for `nmrDraw`.

## Requirements

- Python 3.13+
- PySide6, matplotlib 3.8+, numpy 2.x, nmrglue 0.10, scipy

## Usage

```bash
cd opt/nmrflow64

python3 -m nmrflow                        # blank viewer
python3 -m nmrflow -in spectrum.ft2       # open 2D spectrum
python3 -m nmrflow -in spec%03d.ft3       # open 3D series
python3 -m nmrflow -in spectrum.ft2 -peak # show peak overlay from companion .tab

python3 -m pytest tests/ -q               # run unit tests
```

## Features

### Contour display
- Positive/negative contour levels with adjustable count, base height, and multiplicative factor
- Colour pickers for pos/neg contours

### Phase correction
- Interactive P0/P1 sliders with pivot point (middle-click on canvas)
- Live 1D slice preview while dragging; **Update 2D** redraws contours
- **Auto-phase** (ACME entropy minimisation) for both X and Y dimensions, with a confirmation dialog showing the result before applying

### Script Editor dock (ft*.com integration)
When a spectrum is opened, nmrflow automatically searches for a companion `ft2d.com` / `ft3d.com` (or any `ft*.com`) in the same directory and loads it into the **Script Editor** dock on the right.

- The script is displayed in a monospace editor (fully editable)
- Clicking **Update 2D** in the phase panel also writes the new P0/P1 values back into the script's PS lines (X before TP, Y after TP)
- **Run ft2d.com** saves the editor text to disk, executes the script via `csh` in the background, and reloads the spectrum on success — phase panel resets to zero
- The script can also be loaded manually via **Load…**

### 3D/4D navigation
- Plane mode buttons (XY / XZ / YZ) and a Z-slice spinbox
- Page Up / Page Down step through planes

### Peak overlay
- Load a NMRPipe `.tab` peak table via **Peaks → Load Peak Table…**

## Package layout

```
nmrflow/
  core/
    spectrum.py       — Spectrum class (load, plane extraction, noise level)
    pipe_reader.py    — NMRPipe file I/O via nmrglue
    phase.py          — apply_phase, autophase_1d, autophase_2d
    contour.py        — ContourParams + compute_levels
    peak_table.py     — PeakTable / Peak from .tab files
    com_parser.py     — parse/update PS phases in ft*.com scripts
  gui/
    main_window.py    — NMRDrawWindow (QMainWindow)
    components/
      spectrum_widget.py   — matplotlib canvas
      contour_panel.py     — contour controls
      phase_panel.py       — P0/P1 sliders, auto-phase
      slice_controls.py    — plane-mode buttons + Z spinbox
      file_browser.py      — directory tree
      com_panel.py         — script editor + Run button
      autophase_dialog.py  — autophase result confirmation dialog
  cli/
    args.py           — nmrDraw-compatible CLI argument parser
  processors/
    peak_finder.py    — scipy 2D local-maxima → PPM coordinates
  utils/
    colors.py         — HSV→RGB colour list (nmrDraw colour scheme)
```
