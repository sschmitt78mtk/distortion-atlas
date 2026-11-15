# Tasks

## 1. Pure test state machine (`distortion_atlas/blindspot.py`)

- [x] 1.1 Add `BlindSpotSettings` with the defaults from design D2/D4 (`window_ms=1500`, `gap=(500, 3000)`, `retries=1`, `retry_spacing=5`, `probe_offset=2`, `inner=5`, `outside_sample=75`, `trial_cap=400`, `deadline_ms=1_200_000`, `seed=None`).
- [x] 1.2 Add `Position` and `Attempt` dataclasses (`verdict`, `attempts`, `onset_ms`, `response_ms`, `outcome`).
- [x] 1.3 Implement lattice construction: origin from `patterns.anchor`, spacing `2 × dot_pitch`, rectangular x/y half extents with the standard margin, row/column indices centred on the fixation position.
- [x] 1.4 Implement the initial queue: all inner 5×5 positions except the centre plus a seeded `random.Random` outside sample, shuffled once.
- [x] 1.5 Implement the clock-driven state machine: `waiting` (random gap), `active` (1500 ms window), `paused`, `finished`; `tick(now_ms)` returns whether the frame changed.
- [x] 1.6 Implement `respond(now_ms)`: score only inside an open window, mark seen, end the presentation, record latency; count presses outside a window as late/anticipatory.
- [x] 1.7 Implement the miss path: re-insert the retry at queue index `retry_spacing`; on the second miss mark blind and enqueue the eight neighbours at index `probe_offset`, skipping out-of-field, already queued and already presented positions.
- [x] 1.8 Implement pause/resume with a frozen clock; pausing while active discards the presentation and re-queues the position without recording a miss.
- [x] 1.9 Implement `stop()` for `q` and the trial cap/deadline; leave the queue remainder untested.
- [x] 1.10 Implement `results()` and cluster analysis (8-connectivity, dot count, centre and extent in degrees via `Scale.degrees_for_px`) plus the `central_seen` attention count.

## 2. Renderers (`distortion_atlas/patterns/blindspot.py`)

- [x] 2.1 Add `render_lattice(params, width, height, positions)` drawing the faint lattice on black with the fixation mark applied by the caller.
- [x] 2.2 Add `render_test_frame(...)` that lights exactly one position at full contrast and dims all others.
- [x] 2.3 Add `render_results_frame(...)` with green seen rings, red blind rings + disc, grey untested rings, and a caption block with counts, clusters and the non-diagnostic line.
- [x] 2.4 Add a circle/ring drawing helper that works on the existing numpy frame helpers (`fill_rect`, `blank`) without a new dependency.

## 3. Session integration (`distortion_atlas/ui.py`)

- [x] 3.1 Add the test member and start/stop lifecycle (`start_scotoma_test`, `tick_scotoma_test`) using `time.monotonic() * 1000`.
- [x] 3.2 Branch `render()` to the test frame while running and to the results frame when finished.
- [x] 3.3 Branch `presented()` so the HUD strip is not blended while a dot is lit.
- [x] 3.4 Intercept `Space`, `p`, `q`, `f` and `Esc` in `handle_key` before `params.lookup`; ignore other keys with a hint while running.
- [x] 3.5 Bare `q` after a run still quits; `x` keeps its fixation meaning outside the mode.
- [x] 3.6 Extend `overlay_text()` with the test progress line, the paused announcement and the "cover one eye" reminder when `eye == both`.
- [x] 3.7 Gate `key_bar_allowed` on "no test running or finished".
- [x] 3.8 Route the export action: refuse while running, export the results frame when finished.

## 4. Presenter (`distortion_atlas/backends/qt.py`)

- [x] 4.1 Map `Qt.Key_Space` to `"Space"` in `key_name()`.
- [x] 4.2 Add a 20 ms sampling `QTimer` started with a run and stopped on finish/quit; repaint only when `tick` reports a change.
- [x] 4.3 Translate a left click inside an open window into the `Space` action.
- [x] 4.4 Keep the key bar inert and the cursor untouched while a run is active.

## 5. Controls (`distortion_atlas/params.py`, `distortion_atlas/keybar.py`)

- [x] 5.1 Add a `Control(action="blindspot", keys=("b",), label="scotoma test")` entry.
- [x] 5.2 Add the control to the key-bar row layout and its hit-testing tests.

## 6. Record and safety copy (`distortion_atlas/export.py`)

- [x] 6.1 Add the `blindspot` block (settings, seed, lattice, context, positions with attempts, summary, clusters) to the exported record.
- [x] 6.2 Export the results frame as the PNG for a finished test, matching the display minus the HUD.
- [x] 6.3 Replace the "All current patterns are static" warning with a photosensitivity warning that names the flashing dot presentation; keep the non-diagnostic statement.

## 7. Documentation (`README.md`)

- [x] 7.1 Document the mode, its keys (`b`, `Space`, `p`, `q`, `Esc`), the trial plan and the results colours.
- [x] 7.2 Document the safety note: monocular viewing, photosensitivity, non-diagnostic output.

## 8. Tests

- [x] 8.1 `tests/test_blindspot.py`: gap bounds, window expiry, early/late responses, retry spacing, second miss, neighbour probing and edge/duplicate suppression, cap, deadline, both pause cases, seed reproducibility.
- [x] 8.2 `tests/test_patterns_blindspot.py`: lattice alignment with `anchor` and `dot_pitch`, rectangular clipping, single lit dot, green/red/grey pixel assertions, cluster centroid/extent.
- [x] 8.3 `tests/test_ui_blindspot.py`: start/end/pause/quit keys, ignored parameter keys, hidden key bar, HUD suppression, export refusal and record contents, safety text.
- [x] 8.4 Extend the key-bar and export tests for the new control and block.

## 9. Verification

- [x] 9.1 Run `python3 -m unittest discover -s tests -v` and fix failures.
- [x] 9.2 Run `QT_QPA_PLATFORM=offscreen python3 main.py` as a headless smoke check.
- [x] 9.3 Run `openspec validate scotoma-test-mode --strict`.
- [x] 9.4 Manual fullscreen run at 400 mm: confirm one dot at a time, Space scoring, `p`, `q`, results graphic and exported JSON.
