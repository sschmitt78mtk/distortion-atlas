# Tasks

## 1. Key bar layout model

- [ ] 1.1 Add `visiontest/keybar.py` with `BarButton`, a caption map keyed by
  `Control.action`, `build(width, height, state)` laying out the four fixed rows
  and `hit_test(...)`; no Qt imports. Verify: `python3 -c "import
  visiontest.keybar"` works with no display and `python3 -m unittest
  tests.test_keybar -v` passes.
- [ ] 1.2 Expand the grade control into ten digit buttons and fold the quit
  control's `q` / `Esc` keys into one button whose hint reads `q / Esc`. Verify:
  the keybar test asserts 35 buttons and that the digit keys `0`-`9` each own one
  button.
- [ ] 1.3 Compute equal-width slots per row, elide captions longer than a slot
  and drop the key hint below the minimum slot width. Verify: keybar tests at
  800x800 and 1920x1080 assert every rectangle is inside the bar area, within
  the screen and non-overlapping.
- [ ] 1.4 Mark only the ten step actions repeatable and derive `active` from the
  state snapshot (family, HUD, fixation, recorded grade). Verify: keybar test
  asserts exactly the step actions carry `repeatable` and that an active family
  is flagged for the matching state.

## 2. Session state

- [ ] 2.1 Add `key_bar_visible`, `show_key_bar()`, `hide_key_bar()`,
  `key_bar_allowed` (false for the `selfcheck` family) and `key_bar_state()` to
  `Session`. Verify: `python3 -m unittest tests.test_viewer -v` passes and a new
  session reports the bar hidden and allowed.
- [ ] 2.2 Test that the state snapshot reports the live eye, correction, HUD,
  fixation and grade values and that `show_key_bar()` is refused while the
  self-check family is displayed. Verify: `python3 -m unittest tests.test_viewer
  -v`.

## 3. Qt backend: pointer, painting and timers

- [ ] 3.1 Enable mouse tracking on the viewer window and drive the cursor from
  bar visibility (`BlankCursor` hidden, arrow visible, pointing hand over a
  button). Verify: offscreen test asserts `widget.cursor().shape()` follows
  reveal and hide.
- [ ] 3.2 Refactor `keyPressEvent`'s post-processing into `Window._dispatch(key,
  coarse)` and route `mousePressEvent` through the same helper. Verify: existing
  keyboard tests still pass and the click-parity tests dispatch identical
  actions.
- [ ] 3.3 Paint the bar in `paintEvent` after the readout: panel background, one
  slot per button, caption, key hint, active and hover highlights, reusing
  `OVERLAY_BACKGROUND`, `OVERLAY_ALPHA`, `OVERLAY_TEXT_COLOUR` and the HUD font
  size. Verify: offscreen test grabs the widget and finds darker pixels in the
  bar band only while the bar is visible.
- [ ] 3.4 Reveal the bar on `mouseMoveEvent` and on every press, hide it when the
  idle timer fires, and restart that timer on pointer activity; accept the idle
  delay as a `QtPresenter` argument (default 3000 ms). Verify: offscreen test
  reveals with `QTest.mouseMove`, then observes the bar hide after a short
  injected delay without sleeping for 3 s.
- [ ] 3.5 Resolve clicks with `hit_test`, dispatch `Shift` as the coarse step and
  ignore clicks that hit no button (revealing the bar instead). Verify: offscreen
  test clicks the distance plus and geometry plus buttons and compares the
  resulting parameters with the equivalent key presses, including one coarse
  click.
- [ ] 3.6 Add press-and-hold repeat for step buttons (400 ms, then 80 ms; stop on
  release) and never repeat grades, toggles, export, fullscreen, reset or quit.
  Verify: offscreen test holds a geometry button across several timer ticks and
  asserts more than one step, and holds a grade digit and asserts one grade.
- [ ] 3.7 Suppress the bar while `hold_until_key` is set or the self-check family
  is displayed, while a click still dismisses the held frame. Verify: offscreen
  `presenter.hold(None)` test moves the pointer, sees no bar, clicks, and the
  frame closes.

## 4. Documentation and design consistency

- [ ] 4.1 Add a pointer-controls paragraph to the README next to the key map:
  pointer reveals the bar, 3 s idle hides it, click equals key, `Shift`+click is
  the coarse step, hold repeats a step. Verify: README renders the new section
  and no longer claims the exported PNG matches the screen in the bar band.
- [ ] 4.2 Amend `vision-distortion-atlas` design "D6 - One status line, no
  chrome" to record the transient pointer-only key bar. Verify: the amended
  decision no longer contradicts this change's D2/D4.
- [ ] 4.3 Run the full suite: `python3 -m unittest discover -s tests -v` and
  `QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_viewer -v`. Verify:
  both commands pass with no skipped viewer test.

## 5. Manual acceptance on hardware

- [ ] 5.1 On the target display, confirm the bar is absent while observing,
  appears on pointer movement, disappears after 3 s, and that clicking family,
  grade, export and quit buttons behaves like the keys. Verify: observed on
  hardware at 1:1, with no "PIXEL PATH UNRELIABLE" warning appearing after bar
  use.
