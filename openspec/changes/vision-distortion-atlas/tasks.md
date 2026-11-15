# Tasks

## 1. Scaffold and dependencies

- [x] 1.1 Create the package layout `main.py`, `visiontest/{__init__.py,geometry.py,calibration.py,params.py,fixation.py,ui.py,export.py}`, `visiontest/patterns/{__init__.py,grids.py,dials.py,glare.py,targets.py}`, `visiontest/backends/{__init__.py,qt.py}` and `tests/`; verify with `find visiontest -name '*.py' | sort` and `python3 -c "import visiontest; print(visiontest.__name__)"`
- [x] 1.2 Add `requirements.txt` pinning numpy, Pillow and PyQt6 at the installed versions and record the interpreter; verify `python3 -c "import numpy, PIL, PyQt6.QtWidgets; print('ok')"` succeeds using only what `requirements.txt` names
- [x] 1.3 Add `tests/__init__.py` and a `python3 -m unittest discover -s tests -v` invocation that runs green with zero tests, so later groups have a working entry point; verify the command exits 0

## 2. Visual-angle geometry and calibration

- [x] 2.1 Implement `Scale` in `visiontest/geometry.py` (`px_per_mm`, `distance_mm`, `deg_per_px`, `arcmin_per_px`, `px_for_degrees`, `field_for_px`) and cover it with tests; verify `python3 -m unittest tests.test_geometry -v` asserts 1.53 arcmin/px at 400 mm with 0.178 mm pitch and the proportional shrink at 500 mm
- [x] 2.2 Add margin-aware field fitting to `geometry.py` that snaps a requested field to a whole-pixel pitch and returns the maximum field that fits the buffer; verify tests cover the 600 mm / 20° / 20-square overflow case and the 39.3 px → 39 px snap
- [x] 2.3 Implement calibration persistence in `visiontest/calibration.py` (load/save `~/.config/visiontest/config.json`, `panel_derived` fallback, ±25 % plausibility check) against a temporary `XDG_CONFIG_HOME`; verify `python3 -m unittest tests.test_calibration -v` covers calibrated load, missing file, and rejected implausible value

## 3. Pattern renderers

- [x] 3.1 Implement `visiontest/patterns/grids.py`: Amsler variants (black-on-white, white-on-black, red-on-black, blue-on-yellow) with whole-pixel pitch, adjustable square count and line contrast; verify tests assert symmetry, exact pitch, unchanged outer boundary across square counts, and that line luminance moves toward the background with lowered contrast
- [x] 3.2 Implement M-chart dotted straightness lines in `grids.py` (line count, dot pitch, orientation, grading reference) and verify tests assert dot spacing in whole pixels, centring on the fixation anchor, and no fractional shift when pitch or count changes
- [x] 3.3 Implement the astigmatism dial in `visiontest/patterns/dials.py` (adjustable spoke count and rotation, crossed line pairs) and verify tests assert spoke angles follow the rotation, spoke length/width are constant, and the crossed target shares the dial orientations
- [x] 3.4 Implement halo, veiling-glare and ghost-edge targets in `visiontest/patterns/glare.py` with ordered dithering for low-contrast luminances; verify tests measure the requested mean code value within tolerance, assert ghost displacement is an exact pixel offset in the chosen direction, and assert the source diameter matches the readout
- [x] 3.5 Implement the one-pixel checkerboard self-check and flat-field helper in `visiontest/patterns/targets.py`; verify tests assert exact 1-px alternation, exact 50 % mean code value, and that a two-pixel block average equals the expected grey

## 4. Interactive viewer

- [x] 4.1 Implement `visiontest/params.py` with the parameter dataclass, per-family defaults and the control map from `design.md` (documented step sizes, coarse modifier, reset); verify `python3 -m unittest tests.test_params -v` covers each key's step, the coarse multiplier, reset, and that no key is mapped twice
- [x] 4.2 Implement `visiontest/fixation.py` (hollow ring and dot variants, small sizes, toggle) and verify tests assert the mark is symmetric about the anchor, that hiding it leaves every other pixel unchanged, and that the default ring does not cover the centre pixel
- [x] 4.3 Implement `visiontest/backends/qt.py` and `visiontest/ui.py`: fullscreen `QImage` → `QPixmap` presentation at 1:1, `QT_SCALE_FACTOR=1` before window creation, key dispatch, and an event-driven redraw; verify `QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_viewer -v` renders a pattern, dispatches a key, and re-renders without error
- [x] 4.4 Add the pixel-path integrity guard (surface-size versus buffer-size comparison plus the checkerboard self-check state) and the toggleable single-line overlay drawn only into the presented buffer; verify tests assert a detected mismatch yields the unreliable-session flag and that the exported buffer contains no overlay pixels
- [x] 4.5 Add the start-up notice and monocular reminder, and document the full key map plus a first-run walkthrough in `README.md`; verify every command shown in `README.md` runs as written and the offscreen viewer test still passes

## 5. Grading and session export

- [x] 5.1 Implement grading capture in `visiontest/ui.py`/`params.py` (grades 0–9 bound to family, item index, geometry, colour pairing, eye, fixation state) including regrade counting and the "no pattern shown yet" rejection; verify `python3 -m unittest tests.test_grading -v` covers store, replace, count, and rejection
- [x] 5.2 Implement `visiontest/export.py`: PNG of the rendered buffer without overlay plus a JSON record (pattern parameters, `Scale` values including calibrated/uncalibrated source, eye, correction, ambient note, distances, grades, display-limited contrast flags, disclaimer); verify tests round-trip the JSON, assert the PNG dimensions match the buffer, and assert unwritable paths report failure without losing session state
- [x] 5.3 Export the panel identity (EDID-derived name/resolution when readable, otherwise "unknown") and the self-check result into the record; verify tests use a fake EDID path and assert both the readable and unreadable cases produce a complete record

## 6. Integration on the real panel

- [ ] 6.1 Run `main.py` fullscreen on the target panel and confirm the self-check reports an unscaled 1:1 path; verify by eye that the checkerboard reads as uniform mid-grey and by readout that surface size equals buffer size
- [ ] 6.2 Walk the calibration flow with a ruler against the screen and confirm all reported millimetre and degree values change consistently afterwards; verify a 100 mm bar measures 100 mm on the ruler and that the JSON record marks the scale as calibrated
- [ ] 6.3 Exercise every pattern family at 300–600 mm with one eye covered, grading at least one item per family, and confirm each satisfies its scenario in `openspec/changes/vision-distortion-atlas/specs/`; verify `openspec validate vision-distortion-atlas --strict` passes alongside the visual check
- [ ] 6.4 Export a session and compare the PNG against the on-screen image; verify identical dimensions, identical pattern content, no overlay, and a JSON record that names the eye, distance, scale source and every grade

## Workflow follow-up

- Archive the change after review with `openspec archive vision-distortion-atlas`, then verify the four specs appear under `openspec/specs/` and `openspec validate --all --strict` passes.
