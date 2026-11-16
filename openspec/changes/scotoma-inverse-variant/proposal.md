# Proposal: scotoma inverse variant

## Why

In the standard scotoma test a bright dot appears against a dark field, which makes detection an onset task and can be too easy: a bright transient is salient even well outside a scotoma. The observer asked for the complementary task — black dots on a bright field where the probed dot **disappears** — so detection depends on noticing a missing element rather than a bright flash. Blinking that dot keeps the disappearance visible for the whole response window instead of offering a single moment to catch it. The standard mode must remain available unchanged.

## What Changes

- **Second presentation variant.** A new inverse variant draws the test field as a bright background with full-contrast black lattice dots; during a trial the probed dot blinks between absent and present with a 500 ms half-period (absent at onset) for the same 1500 ms response window, then the lattice is whole again.
- **Same trial logic.** The inverse variant reuses the existing trial plan, seeded outside sample, random gaps, retry-at-five, second-miss blind rule, neighbour probing, pause, results summary and export structure. Only the visual polarity and mode identity change.
- **New start key.** `i` starts the inverse variant while a pattern or results frame is displayed. `b` continues to start the standard variant; neither replaces the other.
- **Mode-aware readouts.** The live overlay and start message say “dot blinks” for inverse, the results frame is labelled `INVERSE`, and both results variants still use the green/red/grey verdict colours on the dark data frame.
- **Mode-aware record and safety.** The exported `blindspot` block gains a `variant` field (`standard` / `inverse`) and the `settings.blink_ms` half-period, and selects a warning that names the inverse bright field and its blinking dark dot. The startup notice warns about both variants.
- **Control and key bar.** Add an `inverse` button for `i` beside the existing `scotoma test` button; the final key-bar row grows from seven to eight buttons.

No **BREAKING** changes: existing records and the standard mode keep their current shape and behaviour.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `scotoma-test`: adds the inverse presentation variant with its 1 Hz blinking probe, its `i` start control, variant-aware live/results text, `variant` and `blink_ms` record fields, and mode-specific safety copy while preserving every existing standard-mode requirement.

## Impact

| Area | Files |
|---|---|
| Pure logic | `distortion_atlas/blindspot.py` (`BlindSpotSettings.variant`, validation, record variant) |
| Renderers | `distortion_atlas/patterns/blindspot.py` (inverse palette, omitted-dot frame, results caption) |
| Session | `distortion_atlas/ui.py` (`i` action, inverse start/messages, overlay and results labels) |
| Controls | `distortion_atlas/params.py`, `distortion_atlas/keybar.py` (`i`, `inverse` button, row counts) |
| Record and safety | `distortion_atlas/export.py` (variant-aware warning, startup copy) |
| Docs | `README.md` (key map, inverse variant section, safety note) |
| Tests | `tests/test_blindspot.py`, `tests/test_patterns_blindspot.py`, `tests/test_ui_blindspot.py`, `tests/test_export.py`, `tests/test_params.py`, `tests/test_keybar.py`, `tests/test_viewer.py` |

No new third-party dependency. The inverse variant uses the same numpy/PIL rendering helpers and the same clock-injected state machine.
