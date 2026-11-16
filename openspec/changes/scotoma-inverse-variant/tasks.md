# Tasks

## 1. Variant setting, blink flag and record

- [x] 1.1 Add `STANDARD`/`INVERSE` constants, a `variant` field and a `blink_ms` field on `BlindSpotSettings` with validation, and `variant`/`settings.blink_ms` in `BlindSpotTest.record()`; verify with `python3 -m unittest tests.test_blindspot` including default-standard, inverse-accepted, invalid-variant, invalid-blink and record tests.
- [x] 1.2 Add `tests/test_blindspot.py` coverage that the inverse variant uses the same initial queue as the standard variant for the same seed and geometry; verify the new test passes.
- [x] 1.3 Add `probe_shown` to `BlindSpotTest`, derive the blink phase from the presentation onset in `_probe_shown`, set it in `_start_presentation`, clear it in `_clear_presentation`, and return `True` from `tick()` on a phase flip; verify with `python3 -m unittest tests.test_blindspot` that the signal starts on, flips every 500 ms, requests no repaint inside a half-period, and stays steady for the standard variant.

## 2. Inverse renderer

- [x] 2.1 Add inverse palette constants and variant selection to `render_lattice`/`render_test_frame`; in inverse, draw a white field with black dots and erase the probed dot with the background colour. Verify with `python3 -m unittest tests.test_patterns_blindspot` including white-background, black-dot, exactly-one-omitted and standard-pixel-unchanged tests.
- [x] 2.2 Add the variant label and variant-specific warning line to `render_results_frame` captions. Verify an inverse results frame contains `INVERSE`, the blinking-dot warning and the non-diagnostic statement, and the standard caption is unchanged.
- [x] 2.3 Add a renderer test that the probe-on and probe-off frames differ only inside the probed dot's pixel box, so the blink cannot disturb the rest of the lattice.

## 3. Session, control and key bar

- [x] 3.1 Add `Control("blindspot_inverse", ("i",), ...)` to `distortion_atlas/params.py`, add the `inverse` caption and final-row action to `distortion_atlas/keybar.py`, and update the key-bar/params tests for 8 final-row buttons and 37 total buttons; verify with `python3 -m unittest tests.test_params tests.test_keybar`.
- [x] 3.2 Add the `blindspot_inverse` action to `Session.handle_key`, start inverse runs through `Session.scotoma_settings(INVERSE)` (variant plus 500 ms blink), render from `test.probe_shown`, and make the start message, live overlay, results readout and restart hint variant-aware (`dot appears` vs `dot blinks`, `INVERSE` label, `b` vs `i` restart). Verify with `python3 -m unittest tests.test_ui_blindspot` including `i` start, `b` standard, mid-run `i` ignored, inverse results label and restart-from-results tests.
- [x] 3.3 Add session-level blink coverage: the probed pixel alternates between background and lattice colour, the HUD strip stays suppressed for the whole window, and a `Space` press inside the blink scores the position. Verify with `python3 -m unittest tests.test_ui_blindspot`.
- [x] 3.4 Extend the Qt/backend tests to cover `key_name` mapping for `i` and confirm the sampling timer and click-to-respond path work with an inverse run; verify with `QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_viewer`.
- [x] 3.5 Keep the centre identifiable on the inverse bright field: add `fixation.size_for_dot` and an `apply_fixation(..., min_size_px=...)` override, pass it for inverse scotoma runs (test and results frames), record `context.fixation.effective_size_px`, and cover the clearance, the honoured larger user size, the unchanged standard ring and the record fields in `tests/test_fixation.py`, `tests/test_ui_blindspot.py` and `tests/test_export.py`.

## 4. Export and safety

- [x] 4.1 Add an inverse photosensitivity warning and a combined startup warning in `distortion_atlas/export.py`, select the warning by `blindspot.variant` in `build_record`, and point `ui.STARTUP_NOTICE` at the combined warning. Verify with `python3 -m unittest tests.test_export tests.test_ui_blindspot` that standard records keep the lit-dot warning, inverse records name the bright field and blinking dark dot, and startup names both variants.
- [x] 4.2 Add export coverage that an inverse results run writes PNG plus JSON with `blindspot.variant == "inverse"`, `settings.blink_ms == 500`, the inverse warning and the existing non-diagnostic statement; verify the PNG equals the displayed buffer and the results frame stays dark.

## 5. Documentation

- [x] 5.1 Update the README key map (`i`), add an inverse-variant section covering the white field, the 1 Hz blink, shared trial logic, results/export variant and `blink_ms` fields and bright-field safety, and adjust the scotoma safety paragraph for both variants. Verify every documented key still exists in `CONTROL_BY_KEY` and the documented key-bar count matches the layout tests.

## 6. Integration verification

- [x] 6.1 Run `python3 -m unittest discover -s tests` and fix all failures; verify the full suite passes.
- [x] 6.2 Run `python3 -m compileall -q distortion_atlas tests` and `openspec validate scotoma-inverse-variant --strict`; verify both succeed.
- [x] 6.3 Run `QT_QPA_PLATFORM=offscreen python3 main.py` as a headless startup smoke check; verify no traceback and a running event loop.
- [ ] 6.4 Manual fullscreen run at 400 mm for both variants: confirm the inverse field is black dots on white, the probed dot blinks every 500 ms starting absent, exactly one dot differs at a time, the red fixation is visible, `Space`/click scoring, `p`, `q`, the `INVERSE` results label and the exported JSON/PNG. Record comfort/brightness observations and stop if the bright field or the blink causes discomfort.

## Workflow follow-up

- Archive `scotoma-inverse-variant` after review and the manual fullscreen check.
- Verify `openspec/specs/scotoma-test/spec.md` contains both the standard and inverse requirements, including the inverse blink, after archive.
