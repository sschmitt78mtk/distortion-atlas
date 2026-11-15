# Design: On-screen key bar

## Context

See `proposal.md` - Why. The constraints that shape this design come from the
current code:

- `distortion_atlas/ui.py` is toolkit-free. A `Session` owns parameters, grades,
  buffers and the display-flag `fullscreen`; the backend only hands buffers to
  the screen and forwards key strings.
- `Session.presented()` returns a copy of the rendered buffer whose top
  `OVERLAY_HEIGHT_PX` (24) rows are darkened, and `backends/qt.py` paints the
  readout text over that strip at `OVERLAY_TEXT_ORIGIN` (8, 18) in 11 pt. The
  pattern buffer itself is never touched, which is what keeps exports clean.
- `QtPresenter.check_surface()` compares `widget.width()/height()` with the
  rendered buffer, and `Session.update_pixel_path()` marks the session
  unreliable on any mismatch. Surface geometry is therefore load-bearing.
- The window sets `Qt.CursorShape.BlankCursor` and has no mouse handling.
- `params.CONTROLS` is the single source of truth: 26 controls, 36 key strings,
  including ten grade digits and one quit control bound to two keys.
- `--self-check` puts the one-pixel checkerboard on screen and calls
  `presenter.hold(None)`, which sets `hold_until_key` and waits for the observer
  to judge a uniform grey by eye.

## Goals / Non-Goals

**Goals:**

- Every mapped key becomes a clickable button with a caption and a key hint.
- Reveal on pointer movement, hide after 3 s idle, so observation stays
  chrome-free.
- One dispatch path: a click is indistinguishable from its key press.
- Zero effect on the rendered buffer, the export, or the pixel-path check.

**Non-Goals:**

- No touch input, gestures, or on-screen keyboard.
- No new key bindings and no change to `params.CONTROLS` semantics.
- No re-layout of the top readout strip, and no pinning/toggle key for the bar.
- No accessibility tree or Qt widget focus model for the buttons.

## Decisions

### D1 - Visibility is session state, pointer plumbing is backend state

`Session` gains `key_bar_visible` plus `show_key_bar()` / `hide_key_bar()` and a
`key_bar_state()` snapshot, mirroring how `Session.fullscreen` is a session flag
that the backend reads. Rationale: keeps `ui.py` importable without a GUI
toolkit, lets headless tests assert visibility, and keeps the decision "is the
bar allowed right now" next to the clinical state (`family`). Alternative: keep
everything on the `QWidget` - untestable under `QT_QPA_PLATFORM=offscreen` and
puts a clinical rule inside paint code.

### D2 - Paint the bar over the image; never reserve space for it

The bar is drawn on top of the image, like the readout strip, and hit-tested
against rectangles computed for the current widget size. Reserving a docked
strip would change `widget.width()/height()` relative to the buffer and trip the
pixel-path guard; weakening that guard to allow for chrome would remove the only
evidence that the pattern reaches the panel 1:1. Alternatives: real
`QPushButton` children - they take keyboard focus and would swallow the arrow
keys that drive geometry, need a translucent background, and multiply Qt state
to test; compositing into `presented()` - puts chrome into the presentation
pipeline and breaks the existing invariant that `presented()` differs from the
buffer only in the top strip.

### D3 - A pure layout module, four fixed rows, equal slots

New `distortion_atlas/keybar.py`, no Qt imports: `BarButton` (action, key, caption,
hint, rectangle, active, repeatable), a caption map keyed by `Control.action`,
`build(width, height, state)` and `hit_test(...)`.

Rows are semantic and fixed:

| Row | Contents | Buttons |
| --- | --- | --- |
| 1 | the seven pattern families | 7 |
| 2 | variant back/forward, four nudge keys, contrast down/up, distance down/up | 10 |
| 3 | grades 0-9, eye, correction | 12 |
| 4 | HUD, fixation, export, fullscreen, reset, quit | 6 |

35 buttons: one per key string, with the quit control's two keys (`q`, `Esc`)
folded into one button whose hint reads `q / Esc`. Slots are equal width within
a row, so nothing needs font measurement: `slot = (width - 2·margin -
(count-1)·gap) // count`, row height clamped from the screen height (30-44 px).
Captions longer than the slot are elided by the model, and the key hint is
dropped below a minimum slot width - both pure integer arithmetic, identical in
every environment. Alternatives: measured flow layout (`QFontMetrics`) - pushes
text measurement into the backend, pads unpredictably across fonts/DPI and
cannot be verified headless; hand-written coordinates - breaks at 800x800 and
4K alike.

### D4 - Reveal on pointer activity, hide after 3 s, never on key press

`Window` enables mouse tracking. `mouseMoveEvent` and every press reveal the
bar and restart a single-shot `QTimer` (3 s). On timeout the bar hides, the
cursor blanks and the frame is repainted. Key presses deliberately do not reveal
it: chrome must not flash while an observer grades. The idle interval is
injectable (`QtPresenter(..., key_bar_idle_ms=3000)`) so tests can shorten it
instead of sleeping. Alternatives: reveal on key press - rejected as visual
noise; a pin/toggle key - deferred, not needed for the stated workflow.

### D5 - Cursor follows visibility only

`BlankCursor` while hidden (today's behaviour), `ArrowCursor` while visible. The
hovered button additionally shows `PointingHandCursor`. Shape changes happen only
on visibility and hover transitions, never per frame. Alternative: leave the
cursor visible always - it would hover over the stimulus unrestricted, which the
current design avoids on purpose.

### D6 - One dispatch helper for keys and clicks

`Window` grows `_dispatch(key, coarse)`, holding the post-processing that
`keyPressEvent` does today (quit/`running` -> close, `toggle_fullscreen` ->
`showFullScreen`/`resize`, then `set_buffer`). `mousePressEvent` resolves a
button and calls the same helper with the button's key, so messages, grading,
export and quit are literally the same code. Coarse step for the pointer is
`Shift`+click for every step control (the keyboard splits modifiers between
arrows and the rest; a pointer user gets one modifier, documented in the README).

### D7 - Hold to repeat, limited to step controls

Pressing a step button starts a single-shot 400 ms timer that then repeats every
80 ms until release, matching keyboard auto-repeat. Only the ten step actions
(primary/secondary/contrast/distance up/down) repeat. Grades, toggles, export,
fullscreen, reset and quit never repeat, because a held mouse button must not
emit a second clinical grade.

### D8 - Suppress the bar for the pixel-path judgement

`Session.key_bar_allowed` is false while `params.family == "selfcheck"`, and the
backend additionally suppresses the bar while `hold_until_key` is set. A click
in that state still closes the `--self-check` frame, exactly like a key press,
but the bar is never painted: the observer is judging a one-pixel checkerboard
for uniform grey, and chrome over the bottom band would corrupt that judgement.

### D9 - State shown on the buttons

`key_bar_state()` snapshots family, eye, correction, HUD, fixation and the grade
for the current item. The active family, `overlay`, `fixation` and the recorded
digit render as active buttons; `eye` and `correction` carry their current value
in the caption (`eye: both`, `correction: worn`). `Session.grade` already
refuses to grade before a pattern is shown with a message, which lands in the
readout strip, so the bar needs no extra guard.

### D10 - Documentation and the superseded D6

The README key map gains a pointer-controls paragraph, and its
"pixel-identical" claim gets the same caveat the readout strip already has.
`vision-distortion-atlas` design decision "D6 - One status line, no chrome" is
superseded by this change's D2/D4 and is amended to "one status line, plus a
transient pointer-only key bar", so the two in-progress changes do not leave
contradictory design records.

## Risks / Trade-offs

- **The bar covers the bottom ~11 % of the field while visible, which is where
  peripheral metamorphopsia gets judged** -> it exists only during pointer
  activity, disappears after 3 s, and never appears for the self-check pattern.
- **Captions drift when a control is added to `params.CONTROLS`** -> a test
  asserts that every key in `CONTROL_BY_KEY` yields exactly one button and that
  every action has a caption.
- **Long captions overflow narrow windows (800x800 in tests, small windowed
  sizes)** -> model-side elision plus dropping the key hint below a minimum slot
  width; the layout still exposes every button.
- **A stray click on `quit` ends the session instantly (user decision)** -> the
  bar is transient and never sits on screen while the observer is not using the
  pointer; keyboard `q` already behaves the same way.
- **Timer-driven flakiness in tests** -> the idle interval is injectable, hide
  and reveal are also callable directly, and `QTest.mouseClick` press+releases
  immediately so the repeat timer never fires.
- **Hover repaints during viewing** -> repaint touches only chrome; `render()` is
  never called from bar interactions, so the pattern buffer and the export stay
  byte-identical.

## Migration Plan

None: no data, format or dependency changes. Implementation order is model ->
session state -> backend painting/pointer/timers -> README and tests, and the
change is reversible by deleting the new module and the backend additions.

## Open Questions

- Discoverability for a keyboard-only observer: with no key-press flash and no
  pin key, nothing on screen advertises the bar. The README and the start-up
  notice cover it for now; a one-off "move the mouse for controls" hint in the
  readout strip can be added later without changing these specs.
