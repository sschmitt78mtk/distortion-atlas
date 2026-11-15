# Tasks

## 1. Variant setting and record

- [ ] 1.1 Add `STANDARD`/`INVERSE` constants, a `variant` field on `BlindSpotSettings` with validation, and a `variant` key in `BlindSpotTest.record()`; verify with `python3 -m unittest tests.test_blindspot` including default-standard, inverse-accepted, invalid-variant and record tests.
- [ ] 1.2 Add `tests/test_blindspot.py` coverage that the inverse variant uses the same initial queue as the standard variant for the same seed and geometry; verify the new test passes.

## 2. Inverse renderer

- [ ] 2.1 Add inverse palette constants and variant selection to `render_lattice`/`render_test_frame`; in inverse, draw a white field with black dots and erase the probed dot with the background colour. Verify with `python3 -m unittest tests.test_patterns_blindspot` including white-background, black-dot, exactly-one-omitted and standard-pixel-unchanged tests.
- [ ] 2.2 Add the variant label and variant-specific warning line to `render_results_frame` captions. Verify an inverse results frame contains `INVERSE`, the bright-field warning and the non-diagnostic statement, and the standard caption is unchanged.

## 3. Session, control and key bar

- [ ] 3.1 Add `Control("blindspot_inverse", ("i",), ...)` to `distortion_atlas/params.py`, add the `inverse` caption and final-row action to `distortion_atlas/keybar.py`, and update the key-bar/params tests for 8 final-row buttons and 37 total buttons; verify with `python3 -m unittest tests.test_params tests.test_keybar`.
- [ ] 3.2 Add the `blindspot_inverse` action to `Session.handle_key`, start inverse runs with `BlindSpotSettings(variant=INVERSE)`, and make the start message, live overlay and results readout variant-aware (`dot appears` vs `dot disappears`, `INVERSE` label, restart hints). Verify with `python3 -m unittest tests.test_ui_blindspot` including `i` start, `b` standard, mid-run `i` ignored, inverse results label and restart-from-results tests.
- [ ] 3.3 Extend the Qt/backend tests to cover `key_name` mapping for `i` and confirm the sampling timer and click-to-respond path work with an inverse run; verify with `python3 -m unittest tests.test_viewer`.

## 4. Export and safety

- [ ] 4.1 Add an inverse photosensitivity warning and a combined startup warning in `distortion_atlas/export.py`, select the warning by `blindspot.variant` in `build_record`, and point `ui.STARTUP_NOTICE` at the combined warning. Verify with `python3 -m unittest tests.test_export tests.test_ui_blindspot` that standard records keep the lit-dot warning, inverse records name the bright field and disappearing dots, and startup names both variants.
- [ ] 4.2 Add export coverage that an inverse results run writes PNG plus JSON with `blindspot.variant == "inverse"`, the inverse warning and the existing non-diagnostic statement; verify the PNG equals the displayed buffer.

## 5. Documentation

- [ ] 5.1 Update the README key map (`i`), add an inverse-variant section covering the white field, disappearing dot, shared trial logic, results/export variant field and bright-field safety, and adjust the scotoma safety paragraph for both variants. Verify every documented key still exists in `CONTROL_BY_KEY` and the documented key-bar count matches the layout tests.

## 6. Integration verification

- [ ] 6.1 Run `python3 -m unittest discover -s tests` and fix all failures; verify the full suite passes.
- [ ] 6.2 Run `python3 -m compileall -q distortion_atlas tests` and `openspec validate scotoma-inverse-variant --strict`; verify both succeed.
- [ ] 6.3 Run `QT_QPA_PLATFORM=offscreen python3 main.py` as a headless startup smoke check; verify no traceback and a running event loop.
- [ ] 6.4 Manual fullscreen run at 400 mm for both variants: confirm the inverse field is black dots on white, exactly one dot disappears at a time, the red fixation is visible, `Space`/click scoring, `p`, `q`, the `INVERSE` results label and the exported JSON/PNG. Record comfort/brightness observations and stop if the bright field causes discomfort.

## Workflow follow-up

- Archive `scotoma-inverse-variant` after review and the manual fullscreen check.
- Verify `openspec/specs/scotoma-test/spec.md` contains both the standard and inverse requirements after archive.
