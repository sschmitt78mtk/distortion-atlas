# Proposal

## Why

There is no tool in this repo — and no convenient tool at all — for finding out *which kind of image distortion a person's eye has* (metamorphopsia, astigmatism axis, halos/glare, monocular ghosting) rather than for measuring visual acuity. Acuity charts are plentiful; distortion references that can be adjusted live and graded are not. A 141 PPI laptop panel at 30–60 cm subtends far more than the classic 20° Amsler field and draws perfectly straight lines, so a Python viewer can act as a self-administered distortion atlas without any long viewing distance or extra hardware.

## What Changes

- New Python application (`main.py` + `distortion_atlas/` package) that renders distortion test patterns directly to a fullscreen window — displayed live, not merely saved.
- Interactive keyboard control of the *reference geometry* (grid pitch, spoke count, source size, ghost offset), line contrast, viewing distance and the eye under test, with an immediate re-render.
- A permanent, toggleable central fixation mark (dot / hollow ring) that anchors the gaze for every pattern.
- Subjective **grading** of the perceived distortion (0–9 per item, M-chart style) so a session produces a score, not just an image.
- Pattern families: Amsler grid variants (black/white, white/black, red/black, blue/yellow, threshold-fade), M-chart dotted straightness lines, astigmatism clock dial with crossed line pairs, and halo / veiling-glare / ghost-offset targets.
- Exact visual-angle geometry: on-screen ruler calibration (px/mm), distance-driven conversion between px, mm, degrees and arcmin, and a solver that picks integer grid pitches and fields that fit the panel.
- Session export: PNG of the displayed buffer plus a JSON report (pattern, parameters, distance, eye, grades, panel identity).
- Pixel-path integrity guard: the viewer asserts a 1:1 unfiltered blit and shows a self-check pattern, because any compositor resampling invalidates every distortion result.

Out of scope for this change: acuity measurement and scoring protocols, field/scotoma and flicker grids, binocular/suppression targets, colour-vision ordering tests, and any diagnostic or medical claim.

## Capabilities

### New Capabilities
- `visual-angle-geometry`: conversion between physical size, viewing distance, pixels, millimetres, degrees and arcmin; on-screen ruler calibration; integer-pitch / field-of-view fitting for a given distance.
- `distortion-test-patterns`: pure rendering functions for the Amsler variants, M-chart dotted lines, astigmatism dial and halo/glare/ghost targets, each parameterised and free of GUI dependencies.
- `interactive-viewer`: fullscreen live presentation with 1:1 pixel integrity guard, central fixation mark, parameter HUD and keyboard control of pattern and geometry.
- `distortion-session-report`: per-item grading, eye under test, and PNG + JSON export of exactly what was displayed.

### Modified Capabilities
<!-- None: no capabilities exist in this project yet. -->

## Impact

- New files: `main.py`, `distortion_atlas/` (geometry, calibration, params, patterns, fixation, ui, backends/qt, export), `tests/`.
- New runtime dependency: PyQt6 (already installed on this machine; used for a native-Wayland, pixel-exact `QImage` blit) plus numpy (already installed) and Pillow for export.
- Repository is otherwise greenfield: no existing code, APIs or specs are modified.
- Environment assumption recorded by the tool: Linux/Wayland desktop, single monitor, display scaling disabled (asserted at runtime rather than trusted).
