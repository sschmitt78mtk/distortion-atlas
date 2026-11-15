# Design: scotoma inverse variant

## Context

See `proposal.md` - Why. The standard scotoma mode is implemented in `distortion_atlas/blindspot.py` (clock-injected state machine), `distortion_atlas/patterns/blindspot.py` (numpy renderers), and `distortion_atlas/ui.py` (session/key/readout integration). The archived `scotoma-test` spec owns the trial plan, timing, pause, results, export and safety contract. The standard field is a dim lattice on black with one lit dot; the results frame is a dark green/red/grey data view.

The inverse variant is a presentation change, not a second experiment. It must keep the same queue, seeded sample, 1500 ms window, 500–3000 ms gaps, retry-at-five, second-miss blind rule, neighbour probing and cluster summary so both variants remain directly comparable.

## Goals / Non-Goals

**Goals:**

- Add an inverse field: black dots on a bright background, with the probed dot omitted for its response window.
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

Drawing the target with the background colour is simpler than teaching the lattice loop to skip a position and still supports an `(x, y)` pair target. The fixation mark is applied afterwards by the existing red ring, which remains visible on white. The standard palette and pixel output do not change.

### D3 - Results frame stays dark and is labelled

Keep the results frame on black with the existing green/red/grey rings. Add a variant line (`INVERSE - DARK DOTS ON BRIGHT FIELD`) and the mode-specific warning to the caption.

Why: the results frame is a data view, not a stimulus. Making it bright would add a full-screen luminance step after the run and reduce the contrast of the verdict colours. The label is enough to prevent a reader from confusing an inverse run with a standard one.

### D4 - `i` starts inverse; `b` stays standard

Add a `blindspot_inverse` control (`i`) and a key-bar button with the caption `inverse`. Both controls start a new run from a displayed pattern or from the results frame. During a run `i` is ignored like every other non-test key.

Why: a separate key is discoverable, works from the results frame, and avoids introducing a persistent "next scotoma variant" state that the observer could forget. Rejected: a Tab-cycled scotoma variant, which would conflict with the existing per-family variant control and add hidden state; rejected: a modifier on `b`, which the key-name layer does not preserve consistently across layouts.

### D5 - Mode-aware record and safety copy

Add `variant` to the `blindspot` block. Keep the existing standard warning, add an inverse warning that names the bright field and disappearing dark dots, and use a combined warning for the startup notice because the startup text is shown before a variant is chosen. The results frame uses the variant-specific short warning.

Why: an inverse record that reused the "lit dot on black" warning would be factually wrong. A combined startup statement avoids promising that only one presentation exists.

### D6 - No changes to the sampling timer or click path

The Qt presenter's 20 ms clock sampler and its click-as-`Space` behaviour remain unchanged. The inverse variant still has one open presentation window, so the existing `lit` gate (documented as "presentation open") suppresses the HUD and routes clicks correctly.

## Risks / Trade-offs

- **Bright-field glare or discomfort** -> The test uses a full white field by design; the inverse warning and README tell the observer to stop if uncomfortable. The results frame stays dark to avoid a second bright exposure.
- **Absence detection is a different criterion** -> Same timing makes results comparable in principle, but not identical in difficulty; the variant label in the overlay, results and record prevents mixing them.
- **Red fixation on white** -> The existing red ring should remain visible, but contrast is lower than on black. Manual fullscreen check; if weak, the fallback is a black fixation ring for inverse only.
- **Two start buttons widen the key bar** -> The arithmetic layout already supports eight buttons in the final row; small screens elide captions exactly as they do now.
- **Record confusion** -> The variant field and mode-specific warning are mandatory; exported PNGs remain the displayed results frame, so the caption also carries the label.

## Migration Plan

Additive change with no persisted-state migration. Existing standard records keep their shape; the only record change is the new optional `variant` field, which consumers can ignore. Rollback is removing the inverse control/render branch and the inverse warning; standard rendering and records remain valid throughout.
