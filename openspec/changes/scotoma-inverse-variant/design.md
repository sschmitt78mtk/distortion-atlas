# Design: scotoma inverse variant

## Context

See `proposal.md` - Why. The standard scotoma mode is implemented in `distortion_atlas/blindspot.py` (clock-injected state machine), `distortion_atlas/patterns/blindspot.py` (numpy renderers), and `distortion_atlas/ui.py` (session/key/readout integration). The archived `scotoma-test` spec owns the trial plan, timing, pause, results, export and safety contract. The standard field is a dim lattice on black with one lit dot; the results frame is a dark green/red/grey data view.

The inverse variant is a presentation change, not a second experiment. It must keep the same queue, seeded sample, 1500 ms window, 500–3000 ms gaps, retry-at-five, second-miss blind rule, neighbour probing and cluster summary so both variants remain directly comparable.

## Goals / Non-Goals

**Goals:**

- Add an inverse field: black dots on a bright background, with the probed dot blinking between absent and present.
- Keep the standard variant byte-for-byte unchanged.
- Make the variant explicit in the live readout, results frame and exported record.
- Add a separate `i` start control and key-bar button without changing the standard `b` control.

**Non-Goals:**

- No new timing, queue, probing or scoring rules.
- No adjustable background luminance or dot contrast in this change.
- No replacement of the dark results data frame with a bright one.
- No automatic comparison between standard and inverse runs.

## Decisions

### D1 - Reuse `BlindSpotTest`; add only a presentation variant

Add `variant: str = "standard"` to `BlindSpotSettings`, validate it against `standard`/`inverse`, and record it in the `blindspot` block. The state machine's timing and queue code stay untouched.

Why: the experimental variables that matter for comparability are already controlled by the existing settings. A second class would duplicate the retry/probing logic and risk divergence. Rejected: a subclass that overrides rendering terms but keeps the same clock; the renderer is already a separate module, so a variant field is enough.

### D2 - Inverse palette and target erasure

`render_lattice` and `render_test_frame` already receive `settings`. They select a palette from `settings.variant`:

- Standard: `BLACK` background, `LATTICE_COLOUR` dots, `LIT_COLOUR` target.
- Inverse: `WHITE` background, `BLACK` dots, target drawn in the background colour to erase it.

Drawing the target with the background colour is simpler than teaching the lattice loop to skip a position and still supports an `(x, y)` pair target. The fixation mark is applied afterwards by the existing red ring, which D8 enlarges so it clears the black centre dot. The standard palette and pixel output do not change.

Because the target is drawn with the background colour, the renderer needs no
notion of a blink: passing `lit=None` shows the full lattice (probe off) and
passing `lit=<position>` erases the dot (probe on). The presenter chooses which
of the two to pass from `BlindSpotTest.probe_shown` (D7).

### D3 - Results frame stays dark and is labelled

Keep the results frame on black with the existing green/red/grey rings. Add a variant line (`INVERSE - DARK DOTS ON BRIGHT FIELD`) and the mode-specific warning to the caption.

Why: the results frame is a data view, not a stimulus. Making it bright would add a full-screen luminance step after the run and reduce the contrast of the verdict colours. The label is enough to prevent a reader from confusing an inverse run with a standard one.

### D4 - `i` starts inverse; `b` stays standard

Add a `blindspot_inverse` control (`i`) and a key-bar button with the caption `inverse`. Both controls start a new run from a displayed pattern or from the results frame. During a run `i` is ignored like every other non-test key.

Why: a separate key is discoverable, works from the results frame, and avoids introducing a persistent "next scotoma variant" state that the observer could forget. Rejected: a Tab-cycled scotoma variant, which would conflict with the existing per-family variant control and add hidden state; rejected: a modifier on `b`, which the key-name layer does not preserve consistently across layouts.

### D5 - Mode-aware record and safety copy

Add `variant` to the `blindspot` block. Keep the existing standard warning, add an inverse warning that names the bright field and its blinking dark dot, and use a combined warning for the startup notice because the startup text is shown before a variant is chosen. The results frame uses the variant-specific short warning.

Why: an inverse record that reused the "lit dot on black" warning would be factually wrong. A combined startup statement avoids promising that only one presentation exists.

### D6 - No changes to the sampling timer or click path

The Qt presenter's 20 ms clock sampler and its click-as-`Space` behaviour remain unchanged. The inverse variant still has one open presentation window, so the existing `lit` gate (documented as "presentation open") suppresses the HUD and routes clicks correctly.

### D7 - The inverse probe blinks at 1 Hz, phased in the state machine

The inverse variant alternates the probed dot between absent and present with a
500 ms half-period: absent at onset, present 500 ms later, absent again at
1000 ms, and the 1500 ms window closes with every dot present. `blink_ms` on
`BlindSpotSettings` carries the half-period (0 = steady, which is what the
standard variant keeps), `BlindSpotTest.probe_shown` is the derived flag that
means "the probe signal is on screen" (a lit dot in standard, an erased dot in
inverse), and `tick()` returns `True` on a phase flip so the existing 20 ms
sampler repaints without a new timer.

Why: the inverse field's whole point is that detection depends on noticing a
change in a dot, and a single disappearance at onset gives the observer no
second chance to locate it. A 1 Hz blink is one small dot, far below the
3-30 Hz photosensitive band, and it makes the existing "flashing" safety claim
factually true. Deriving the phase from `onset_ms` keeps every presentation of
a position identical and keeps the clock out of the renderer; storing the flag
on the test object is what lets `render()` and `presented()` agree even if a
paint lands exactly on a phase boundary. Rejected: sampling the wall clock
inside the renderer (two paints of one frame could disagree); rejected: a
renderer-side timer (breaks the clock-injection rule that makes the test
headless); rejected: per-run adjustable rate (strobe risk, extra state, and no
experimental question it answers).

### D8 - The inverse field clears the centre dot with the fixation ring

The inverse test field keeps the black centre dot and raises the fixation ring
until its inner edge clears that dot: `fixation.size_for_dot(dot_px)` returns
the smallest odd ring size that leaves a 2 px background gap (17 px for the
8 px dot), and `Session.render()` passes it as `apply_fixation(...,
min_size_px=...)` for inverse scotoma runs only, for both the test field and
their results frame. The user's `fixation_px` still sets the size everywhere
else and is still recorded; `context.fixation.effective_size_px` states the
size actually drawn.

Why: measured on the default field, an 11 px ring around an 8 px dot puts 34 of
its 52 red pixels on top of the black dot, leaving a thin ragged fringe that is
impossible to find among ~1300 black dots on white - the exact failure the
manual fullscreen check looks for. Enlarging the ring (rather than switching it
to black, or painting a halo under it) keeps the red fixation convention,
changes no other pattern and leaves the standard variant pixel-identical.
Rejected: a black ring for inverse only (loses the convention and reads as
another lattice element); rejected: a background halo disc (repaints stimulus
pixels around the centre and needs palette knowledge in the fixation module).

## Risks / Trade-offs

- **Bright-field glare or discomfort** -> The test uses a full white field by design; the inverse warning and README tell the observer to stop if uncomfortable. The results frame stays dark to avoid a second bright exposure.
- **Blinking dot and photosensitivity** -> One 8 px dot at 1 Hz is a weak stimulus, but it is still flashing content; the inverse warning names it and the startup notice covers both variants.
- **Blink changes the detection criterion further** -> A blinking element provides a transient cue that a static absence does not, and the response latency includes up to one half-period of waiting for the next transition. Same timing keeps the runs comparable in structure, not in difficulty; the variant label and recorded `blink_ms` prevent mixing them.
- **Absence detection is a different criterion** -> Same timing makes results comparable in principle, but not identical in difficulty; the variant label in the overlay, results and record prevents mixing them.
- **Red fixation on white** -> Resolved in D8: the inverse field raises the ring until it clears the black centre dot by a 2 px background gap, so the centre stays identifiable without changing the red convention or any other pattern. The manual fullscreen check (task 6.4) still confirms it on the panel.
- **Two start buttons widen the key bar** -> The arithmetic layout already supports eight buttons in the final row; small screens elide captions exactly as they do now.
- **Record confusion** -> The variant field and mode-specific warning are mandatory; exported PNGs remain the displayed results frame, so the caption also carries the label.

## Migration Plan

Additive change with no persisted-state migration. Existing standard records keep their shape; the record changes are the new `variant` field, the `settings.blink_ms` value and the `context.fixation.effective_size_px` field, all of which consumers can ignore (standard runs record `blink_ms: 0` and `effective_size_px` equal to `size_px`). The blink half-period is fixed at 500 ms, so there is no per-run tuning state to migrate. Rollback is removing the inverse control, the render branch, the blink flag and the inverse warning; standard rendering and records remain valid throughout.
