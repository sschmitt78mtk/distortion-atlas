# Design

## Context

See `proposal.md` — Why. Two constraints shape every decision here.

**The panel.** Target machine: 1920×1080 at 340×190 mm reported, single eDP panel, ~0.178 mm pixel pitch (≈141 PPI), Python 3.12 with numpy 1.26, Pillow 10.2, PyQt6 and PyQt5 present, pygame absent. Session is Wayland (GNOME/mutter, `scaling-factor 0`, no fractional-scaling experimental feature), so X11-only toolkits are presented through XWayland and are subject to compositor resampling if scaling is ever enabled.

**The observer.** Working distance 30–60 cm, one eye covered, keyboard within reach, patterns static. At 400 mm one pixel subtends 1.53 arcmin and a 20° Amsler field needs 785 px, so the panel comfortably beats a printed card — but line widths must be whole pixels and the whole path must be unfiltered, because anything else injects geometric error of the same order as the distortion being looked for.

## Goals / Non-Goals

**Goals**

- Deterministic, testable pattern generation that is independent of any GUI.
- A single source of truth for scale: `pixels_per_mm × distance` drives every reported dimension.
- A presentation path that can prove it is 1:1 instead of assuming it.
- Session output that a second person can read without the application: image plus JSON.

**Non-Goals**

- No acuity measurement, no thresholding protocols, no scoring beyond the observer's own 0–9 grade.
- No field/scotoma, flicker, binocular or colour-vision patterns in this change.
- No motion stimuli: everything is static, so no frame loop and no vsync requirement.
- No persistence beyond the exported JSON; no history database, no network.

## Decisions

### D1 — PyQt6 `QImage` presentation, not tkinter or pygame

Qt is already installed, runs natively on Wayland (no XWayland resampling), and gives explicit control over scaling policy (`QT_SCALE_FACTOR=1`, `AA_DisableHighDpiScaling`, and a `QImage` → `QPixmap` blit at 1:1). tkinter would have been dependency-free but is X11-only (Tk 8.6 has no Wayland backend) and gives no scaling hook; pygame would need an install and offers nothing extra for static patterns.

*Alternative rejected:* matplotlib — it is a plotting library; axes, resampling and its own event loop actively fight pixel exactness.

The renderer is kept backend-agnostic behind a `Presenter` protocol (`show(buffer)`, `size`, `on_key`), so a tkinter fallback stays a small addition later.

### D2 — Patterns are pure numpy functions over a parameter dataclass

`render(params, width, height) -> np.ndarray[(h, w, 3), uint8]` with no imports from the UI layer. This is what makes the tool testable headlessly: stroke widths, grid pitch, symmetry, centre anchoring and measured Michelson contrast can all be asserted without a display, and the same function feeds both the window and the PNG export (guaranteeing the exported image is the displayed image).

Two render classes are needed because the pattern families want opposite things:

| | bilevel renderer | continuous renderer |
|---|---|---|
| families | Amsler, M-chart, dial, self-check | halo, veiling glare |
| method | draw at whole pixels, no anti-aliasing | float luminance with spatial dithering |
| why | a 1.5-px-wide "straight" line is itself a distortion | hard edges would band and fake halos |

*Alternative rejected:* one supersampled renderer for everything — supersampling makes Amsler lines grey (halving perceived contrast) and buys nothing for targets that must land on pixel boundaries.

### D3 — Centre-anchored, parity-aware geometry

Coordinates are computed as `x - cx` with integer offsets, and grid lines use a parity rule (even counts place lines at even indices, odd counts at integer centres) so the field's outer boundary never shifts when the square count changes. Fixation mark, grid centre and dial centre all derive from the same anchor. This satisfies the "field does not move" requirement structurally rather than by careful coding.

### D4 — Distance and calibration are one mutable `Scale` object

`Scale` holds `px_per_mm`, `source` (`calibrated` | `panel_derived`), `distance_mm`, and exposes `deg_per_px`, `arcmin_per_px`, `px_for_degrees`, `field_for_px`. Every readout and every export reads from it, so a distance change is a single mutation. Calibration is stored in `~/.config/visiontest/config.json` (stdlib `json`, no new dependency) with a plausibility check at ±25 % against the panel-derived value, as required by `visual-angle-geometry`.

### D5 — Event-driven redraw with a latency budget

All patterns are static, so there is no animation loop: a key event mutates `Params`, the pattern is re-rendered, and the presenter blits. Budget: full 1080p grid render plus blit under ~30 ms so key repeat feels continuous. Coordinate index grids (`xx`, `yy`, radial `r`) are cached per buffer size in `float32`; that is the only optimisation worth doing up front.

### D6 — One status line, no chrome

The overlay is a single semi-transparent text strip at the top plus the grading state, drawn into the *presented* buffer only, never into the buffer that is exported. This keeps the "exported image matches the display" requirement true by construction.

### D7 — Tests with stdlib `unittest`

`pytest` is not installed and the project has no tooling yet; `unittest` runs with a bare interpreter. Pattern and geometry tests are headless. A single viewer smoke test uses `QT_QPA_PLATFORM=offscreen`, skipped when Qt is unavailable.

### Control map (the documented key steps the viewer spec refers to)

| key | action | step |
|---|---|---|
| `a` `l` `d` `n` `v` `e` `c` | Amsler / Lines (M-chart) / Dial / halo / veil / edge-ghost / self-check | — |
| `Tab` `Shift+Tab` | next / previous variant in family | — |
| `↑` `↓` | primary geometry (squares, dot pitch, spokes, source size, surround, ghost offset) | 1 (coarse ×5) |
| `←` `→` | pitch / rotation / direction | 1 px or 15° |
| `+` `-` | contrast or luminance | 5 code values (coarse ×4) |
| `[` `]` | viewing distance | 50 mm |
| `m` | eye under test | L → R → Both |
| `w` | correction worn | toggle |
| `0`–`9` | grade current item | — |
| `h` `x` | HUD / fixation mark | toggle |
| `s` | export PNG + JSON | — |
| `f` `r` `q`/`Esc` | fullscreen / reset params / quit | — |

## Risks / Trade-offs

- **Compositor resampling silently blurs every target** → start-up 1-px checkerboard self-check plus a surface-size versus buffer-size comparison; mismatch marks the session unreliable and is written into the record. `QT_SCALE_FACTOR=1` is asserted before window creation.
- **Uncalibrated `px_per_mm` gives plausible but wrong angular sizes** → values derived from panel reports are labelled uncalibrated everywhere they appear, including the JSON record, and calibration is prompted before grading.
- **8-bit panel limits genuine contrast resolution to roughly 1 % Michelson** → the veil/glare family uses ordered dithering to extend the effective resolution, and the record states which contrast values are display-limited.
- **Subjective grading is noisy** → regrading replaces the value but is counted in the record, so inconsistent answers are visible rather than hidden.
- **The fixation mark masks the very centre being inspected** → hollow ring by default, toggling it off is recorded with any grade taken while it was hidden.
- **Panel brightness or ambient light changes invalidate a comparison between sessions** → brightness and ambient note are session fields in the JSON; the tool cannot control them.
- **Photosensitive risk if a future change adds flashing patterns** → the warning is shown at start-up now, before any such pattern exists.

## Migration Plan

Greenfield: no migration, no rollback concerns beyond deleting the new files. `openspec/changes/vision-distortion-atlas` archives into `openspec/specs/{visual-angle-geometry,distortion-test-patterns,interactive-viewer,distortion-session-report}`.

## Open Questions

- Whether the calibration default should come from EDID (`/sys/class/drm/card1-eDP-1/edid`) or a constant fallback — the guard makes a wrong default harmless, so this can be settled during implementation.
- Whether a second grading pass per item (repeatability check) is worth a key — deferrable without changing the specs.
