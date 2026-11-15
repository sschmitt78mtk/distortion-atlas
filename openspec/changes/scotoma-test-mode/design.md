# Design: scotoma test mode

## Context

`ui.Session` owns all state, renders a numpy frame, and forwards key names; `backends/qt.py` is a thin blit shell with no pattern logic. Tests drive `Session` headlessly (230 `unittest` cases), so any behaviour that only exists inside Qt is effectively untestable. Today the shell has only two `QTimer`s (key-bar idle hide, key repeat) — there is no animation clock and no notion of a timed stimulus.

Facts that shaped the design, measured on the reference setup (1920×1080, 400 mm, 39.55 px/deg):

- `grids.render_lines` draws 3 px dots (`grids.DOT_PX = 3` ≈ 4.6′) on a **square** field `extent = min(w, h) − 16 = 1064 px`, i.e. ±13.45°. A scotoma anywhere in the visual field needs the full screen, not that square.
- The current lines lattice at `dot_pitch = 50` over the full width would be 39 × 25 = 975 positions ≈ 53 min of trials at ~3.25 s each — unusable.
- The HUD strip is baked into the top rows of `Session.presented()`, so it must be suppressed deliberately during a stimulus.
- `key_name()` maps letters and digits but **not** `Space`; `x` is fixation, `q`/`Esc` are quit.
- `export.py` hard-codes "All current patterns are static", which this mode makes false.

## Goals / Non-Goals

**Goals**

- A timed, self-paced detection session that yields a per-position seen/blind verdict.
- Deterministic, headlessly testable timing and queueing.
- A readable results graphic and an additive JSON record.
- No new dependency, no change to existing pattern rendering.

**Non-Goals**

- No clinical perimetry (no threshold ramps, no stimulus size/contrast bracketing, no normative data).
- No automated detection of the physiological blind spot.
- No adaptive grid refinement beyond the eight-neighbour probe ring.
- No persistence of results between runs beyond the exported PNG/JSON.

## Decisions

### D1 — Timing lives in a pure state machine, not in Qt

`BlindSpotTest` takes `now_ms` as an argument on every call (`tick`, `respond`, inspections) and never reads the clock itself. `ui.Session` supplies `time.monotonic() * 1000`; `qt.py` starts a 20 ms `QTimer` that only calls `session.tick()` and repaints when it reports a frame change.

Why: the 1500 ms window and the 500–3000 ms gaps become testable with a fake clock, and a late paint can never stretch a window — the window is derived from timestamps, not from frame counting. Rejected: a state machine driven by `QTimer.timeout` counts (drifts, untestable, jitter-dependent).

### D2 — The mode owns a rectangular lattice aligned to the lines lattice

- Origin: `patterns.anchor(width, height)` (same fixation centre as the static pattern).
- Spacing default: `2 × params.dot_pitch` (100 px with the reference settings ≈ 2.53°). Every test position is therefore also a position of the lines lattice — the mode reads as "every second dot of the lines pattern".
- Field: x half = `width // 2 − margin`, y half = `height // 2 − margin` (margin 8 px), so the field is 1904 × 1064 px ≈ 48° × 27° at 400 mm.
- Dot size default: 8 px ≈ 12′, because a 3 px dot is close to the peripheral resolution limit at 15–20° eccentricity and would produce false blind reports.
- Default lattice: 19 columns × 11 rows = 209 positions; inner 5 × 5 = 25; outside sample 75 → 99 initial presentations ≈ 5 min.

Why not reuse `render_lines` geometry as-is: the square extent stops at ±13.45° and the 3 px dots are too small for peripheral detection. Both would corrupt the measurement rather than just look different.

### D3 — The dot is lit for the whole 1500 ms window

Chosen by the user. Onset → window; `Space` inside the window marks seen and ends the presentation immediately (latency recorded); window expiry marks a miss. There is no separate flash interval, so there is no race between "flash ended" and "response arrived".

### D4 — Queue: one retry, then battleship probing

State per position: `verdict ∈ {untested, seen, blind}`, `attempts` list. Queue entries are `(position, attempt_number)`.

- Initial queue: all 24 inner positions + random outside sample, shuffled with `random.Random(seed)`.
- Miss: re-insert the retry at queue index 5 (or at the end if shorter). Never adjacent, never immediate.
- Second miss: mark blind, then enqueue the eight neighbours (if inside the field and not already queued/presented) at queue index 2. Each neighbour follows the normal rule, so a blind neighbour grows the ring again — the Battleship effect.
- Seen: verdict final, no further presentations.
- Cap: 400 presentations (configurable) and a monotonic deadline of 20 min, both of which stop the run and hand over to results with the rest untested. This bounds a pathological "everything is blind" field.

### D5 — Inner ring is 5 × 5 minus the centre

The fixation mark is drawn at the exact centre, so a dot there would be unmeasurable and would also hide the mark. 24 inner positions remain, and the count is reported as "n/24 seen".

### D6 — Pausing during a lit dot aborts that presentation

Freezing a lit dot would let the observer stare at it while paused and answer after resuming, which would forge a "seen". Instead the presentation is discarded and the position re-queued; nothing is recorded as a miss. Pausing during a gap freezes the remaining gap.

### D7 — Presentation frame: faint lattice, one bright dot, no HUD

`Session.presented()` gains a test branch: while a test is running it returns the test frame unchanged (no overlay blend) when a dot is lit, and the normal blended frame otherwise. The lattice is drawn with the low-contrast pairing of the session (`pairing_colours(0, veil-like contrast)`), the lit dot with full contrast. Fixation is drawn with `apply_fixation` as for every other pattern, so it cannot be "off" during a measurement by accident. `key_bar_allowed` returns `False` while a test runs, the same mechanism already used for the self-check pattern.

### D8 — Results frame: rings, clusters, attention line

Seen = green ring, blind = red ring plus a small red disc, untested = grey ring (all on black, 3 px stroke, radius ≈ half the lattice spacing). Clusters use 8-connectivity flood fill over blind positions; centroid and bounding box are converted to degrees with `Scale.degrees_for_px`. Caption block: counts, cluster lines, inner-ring "n/24 seen", median Space latency, the non-diagnostic line. No diagnostic nouns ("defect", "scotoma grade") anywhere in the image or record.

### D9 — Record is additive

New `blindspot` object in the existing JSON, produced by the existing `export.export_session` path so the file naming, panel identity, scale provenance, pixel-path verdict and disclaimer stay identical to every other record. `s` is refused while the test runs and works on the results frame. PNG = the results buffer, which is also what is on screen minus the HUD.

### D10 — Keys and precedence

`handle_key` checks the test first:

```
while running:  Space → respond   p → pause/resume   q → finish   f → fullscreen
                Esc → quit        everything else → ignored + hint
results shown:  s → export        b → restart        q/Esc → normal quit
                x → fixation toggle (normal meaning everywhere outside a run)
```

`Space` needs one new entry in `qt.py::_special_keys` (`Qt.Key_Space → "Space"`); a left click inside the window is translated to the same action because the key bar is hidden during a run and the cursor is therefore free.

## State machine

```
                    b
                    │
                    ▼
            ┌───────────────┐  gap expired   ┌────────────────┐
            │  waiting      │───────────────▶│   active       │
            │  dot dark     │                │   dot lit      │
            │  gap 0.5–3 s  │◀───────────────│   window 1.5 s │
            └───────────────┘  Space / miss  └────────────────┘
                    ▲                               │ miss → retry at +5
                    │                               │ miss again → blind,
                    │                               │   neighbours at +2
                    │                               ▼
                    │                        ┌───────────────┐
                    └────────────────────────│  finished     │
                                             │  results      │
                                             └───────────────┘

  p (any state) ──▶ paused: clock frozen; a lit presentation is discarded
  q (running)   ──▶ finished (partial results)
  Esc           ──▶ application quit, no record
```

## Data model (module-local, no Qt, no numpy)

```
BlindSpotSettings: window_ms=1500, gap=(500,3000), retries=1, retry_spacing=5,
                   probe_offset=2, inner=5, outside_sample=75, spacing_px=100,
                   dot_px=8, trial_cap=400, deadline_ms=1_200_000, seed=None
Position:          col, row, x_px, y_px, verdict, attempts[]
Attempt:           onset_ms, response_ms, outcome ∈ {seen, miss, aborted}
BlindSpotTest:     tick(now_ms) -> bool (frame changed)
                   respond(now_ms) -> bool (counted)
                   pause(now_ms) / resume(now_ms) / stop(now_ms)
                   verb, current, progress, results(), clusters(scale)
```

## Record sketch

```
"blindspot": {
  "settings": {"window_ms": 1500, "gap_ms": [500, 3000], "spacing_px": 100,
               "dot_px": 8, "inner": 5, "outside_sample": 75, "retries": 1,
               "trial_cap": 400, "seed": 20261115},
  "lattice": {"origin_px": [960, 540], "columns": 19, "rows": 11,
              "x_half_px": 952, "y_half_px": 532},
  "context": {"eye": "right", "correction": "worn", "distance_mm": 400.0},
  "positions": [{"col": 10, "row": 5, "x_px": 1060, "y_px": 640,
                 "verdict": "blind",
                 "attempts": [{"onset_ms": 41230, "response_ms": null, "outcome": "miss"},
                              {"onset_ms": 60110, "response_ms": null, "outcome": "miss"}]}],
  "summary": {"seen": 102, "blind": 8, "untested": 8, "central_seen": "22/24",
              "late_responses": 1, "median_latency_ms": 430,
              "clusters": [{"dots": 8, "centre_deg": [4.1, 0.8], "extent_deg": [7.2, 4.8]}]},
  "caveat": "Not a medical device — this record is an observation aid only."
}
```

`photosensitivity` and `non_diagnostic` keep their existing top-level keys, with the warning text updated to name the flashing presentation.

## Testing strategy

- `tests/test_blindspot.py` — fake clock: gap bounds, 1500 ms expiry, early response, late/anticipatory press, retry spacing of five, second miss → blind, neighbour probing and edge/duplicate suppression, trial cap, deadline, pause during gap and during a lit dot, seed reproducibility.
- `tests/test_patterns_blindspot.py` — lattice alignment to `anchor` and to a multiple of `dot_pitch`, rectangular clipping, one lit dot only, green/red/grey pixel assertions on the results frame, cluster centroid/extent in degrees.
- `tests/test_ui_blindspot.py` — `b` starts, `q` finishes (and does not quit), `Esc` quits, `p` pauses, Space counts once, other keys do not change parameters, key bar hidden while running, overlay suppressed while lit, export refused mid-run, export writes the `blindspot` block, new safety text present.
- Manual smoke: `QT_QPA_PLATFORM=offscreen python3 main.py` plus a real fullscreen run at 400 mm.

## Risks / Trade-offs

- **Random outside sampling can miss a small scotoma.** A 75-dot sample of 184 outside positions is a scan, not a guarantee; the battleship ring only helps after the first hit. Mitigation: the record states the sample size and seed, and the spacing/count are settings so a denser run is possible.
- **Peripheral dots near threshold.** 8 px ≈ 12′ is visible at 15–20° for most observers, but not for everyone; a run with many isolated red dots at high eccentricity should be read as "too small / not attended", which is why the inner-ring attention check exists.
- **Binocular viewing hides scotomas.** With `eye: both` the fellow eye fills in; the mode records the eye but cannot enforce covering it. The pre-run message must say so.
- **Response criterion drift.** With a lit dot for the full window, a hesitant observer can answer late; the window bounds this, and `late_responses` surfaces it.
- **Clock granularity.** A 20 ms sampling timer plus `monotonic` timestamps means worst-case ~20 ms of measurement error on onsets — far below the 1500 ms window.

## Migration Plan

No data migration. Existing records are unaffected (new key only). The only changed existing string is the photosensitivity warning, which is a wording correction, not a schema change. Rollback = remove the mode and restore the warning string; no persisted state depends on it.

## Open Questions

- Should the outside sample default grow for a second pass on the same eye, or is one 75-dot scan per run the intended workflow? (Currently: one scan; restarting with `b` draws a new seed.)
- Should the record also capture the exact monitor refresh behaviour that `qt.py` measured for the pixel-path check? (Currently the existing `pixel_path` block is reused unchanged.)


