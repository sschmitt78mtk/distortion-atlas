# Proposal: scotoma test mode

## Why

The atlas can show a static pattern, but it cannot answer the one question a static pattern raises: *did the observer actually see this dot?* A dot that falls into a non-working retinal region is indistinguishable from a dot that was simply not noticed, because nothing is ever expected of the observer.

The earlier `vision-distortion-atlas` proposal deliberately left "field/scotoma and flicker grids" out of scope. This change adds that missing mode for the `lines` dot lattice: dots are presented one at a time in random order, the observer presses a key when one appears, and the session records per-dot detection. The output is a map of seen versus blind dots rather than another static pattern.

The mode observes a self-reported visual field. It is not perimetry and it is not a diagnosis.

## What Changes

- **New modal test session**, started with `b` while any pattern is displayed. The static pattern is replaced by the test field; the mode keeps the current eye, correction and viewing distance from the session.
- **Single dot presentation.** One dot is lit for a 1500 ms window; `Space` inside that window marks it seen and ends the trial early. No response in the window is a miss.
- **Random inter-trial gap** of 0.5–3.0 s, uniformly sampled, so the observer cannot anticipate the next onset.
- **Deterministic trial plan.** All 24 dots of the inner 5×5 ring around fixation are tested (the exact centre is skipped because the fixation mark sits there), plus a random sample of dots outside that ring.
- **One retry per miss**, re-queued at least five trials later so the answer is not a reflex repeat.
- **Battleship probing.** A dot that misses twice is marked blind and its eight neighbours are queued, so a confirmed blind region is mapped outward until the surround is seen.
- **Controls.** `p` pauses/resumes, `q` ends the test and shows the results, `Esc` still quits the application, `x` keeps its fixation role. The on-screen key bar is hidden for the duration of a run.
- **Results frame and export.** Seen dots are green circles, blind dots red circles, untested dots grey; blind dots that touch are summarised as clusters with size, centre and extent. `s` exports the results PNG plus a JSON record with a new `blindspot` block.
- **Safety copy.** The session record's photosensitivity statement changes from "all current patterns are static" to a warning that names this mode's flashing content.

## Capabilities

### New Capabilities

- `scotoma-test`: the dot-by-dot detection session — trial plan and adaptive probing, timing and response rules, mode controls, live presentation, results frame, and its record block.

### Modified Capabilities

None. No capability spec has been archived into `openspec/specs/` yet, so this change owns the complete behaviour contract for the new mode instead of patching a main spec that does not exist.

## Impact

| Area | Files |
|---|---|
| New pure logic | `distortion_atlas/blindspot.py` |
| New renderers | `distortion_atlas/patterns/blindspot.py` |
| Session integration | `distortion_atlas/ui.py` (`Session`, key precedence, render/overlay branch, export branch, key-bar gate) |
| Presenter | `distortion_atlas/backends/qt.py` (`Space` key name, sampling timer, click as response) |
| Controls | `distortion_atlas/params.py`, `distortion_atlas/keybar.py` (`b`, key-bar row) |
| Record | `distortion_atlas/export.py` (`blindspot` block, results PNG, photosensitivity text) |
| Docs | `README.md` |
| Tests | `tests/test_blindspot.py`, `tests/test_patterns_blindspot.py`, `tests/test_ui_blindspot.py` |

No new third-party dependency: timing uses `time.monotonic`, randomness uses `random.Random`, rendering reuses the existing numpy/PIL helpers.
