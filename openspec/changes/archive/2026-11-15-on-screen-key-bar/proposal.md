# Proposal: On-screen key bar

## Why

The viewer is keyboard-only. `distortion_atlas/params.py` maps 26 controls onto 36 key
strings, the fullscreen window hides the cursor, and nothing on screen says which
key does what. Observers lose the less obvious chords (`Shift+Tab`, `Ctrl`-arrow
coarse steps, `[`/`]` distance, `m`/`w`/`x`/`h`/`s`/`f`/`r`/`q`), and a pointer
user cannot drive a session at all — there is no mouse handling anywhere in
`distortion_atlas/backends/qt.py`.

The obvious fix — a permanent toolbar — would cost about 11 % of a 1080p screen
along the bottom edge of an Amsler field, which is exactly where peripheral
distortions are judged. A bar that only exists while the pointer is in play, and
then disappears, gives the whole control surface back without paying that cost
during observation.

## What Changes

- Add a key bar along the bottom of the viewer in which **every mapped key is a
  button**: four semantic rows (pattern families; geometry and contrast; eye,
  correction and the ten grades; session actions).
- Each button carries a short caption plus its key as a hint, and reflects live
  state (active family, current eye, correction, HUD, fixation, recorded grade).
- The bar is hidden while observing. Pointer movement reveals it; 3 s without
  pointer activity hides it again. Keyboard input never reveals it.
- Clicking a button dispatches the same key string to `Session.handle_key`, so
  messages, grading, export, fullscreen and quit are byte-for-byte the same paths
  as the keyboard.
- Holding a step button repeats it at the keyboard's auto-repeat cadence;
  `Shift`+click applies the coarse step; `quit` acts immediately.
- The bar is chrome only: it never enters `Session.buffer`, the exported PNG or
  the pixel-path comparison, and it stays hidden while the one-pixel checkerboard
  is on screen (including the `--self-check` hold), because that frame is judged
  by eye.
- The cursor stays hidden while the bar is hidden and becomes the pointer only
  while it is visible. No touch input is required or handled.
- Document the pointer controls in the README next to the key map.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `interactive-viewer`: adds the requirement that every keyboard control is also
  reachable as a pointer-revealed button, that a click is equivalent to its key,
  and that this chrome never alters the presented or exported pixels.

`interactive-viewer` currently exists only as a delta of the in-progress
`vision-distortion-atlas` change (`openspec/specs/` is still empty), so this
change contributes `ADDED Requirements` for that same capability path; both
deltas merge when the two changes are archived.

## Impact

- **Code**: new toolkit-free `distortion_atlas/keybar.py` (layout, captions,
  hit-testing); `Session` gains key-bar visibility state and a state snapshot;
  `distortion_atlas/backends/qt.py` gains mouse tracking, bar painting, hover, click
  dispatch, repeat and idle timers; `README.md` gains a pointer-controls
  paragraph.
- **Tests**: new `tests/test_keybar.py` (pure layout and hit-testing) and new
  pointer scenarios in `tests/test_viewer.py` (offscreen `QTest` mouse events).
- **Compatibility**: the keyboard path is untouched, no new dependency is added,
  the export format is unchanged, and windowed mode keeps working because layout
  is recomputed from the live widget size.
