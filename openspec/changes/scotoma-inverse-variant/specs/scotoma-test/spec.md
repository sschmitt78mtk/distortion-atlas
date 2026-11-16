# Spec Delta

## ADDED Requirements

### Requirement: Inverse presentation variant

The mode SHALL offer an inverse presentation variant that draws black lattice dots on a bright background and indicates the probed position by alternating its dot between absent and present at a fixed half-period for the response window, while preserving the standard variant's trial plan, timing, retry and probing rules, results summary and export structure. The centre dot SHALL remain present and SHALL be marked by a red fixation ring that clears it with background pixels.

#### Scenario: Inverse field starts on i

- **WHEN** the observer presses `i` while a pattern is displayed
- **THEN** the test field shows black lattice dots on a bright background
- **AND** the fixation mark is visible
- **AND** no dot is omitted before the first presentation

#### Scenario: Centre stays identifiable

- **WHEN** the inverse test field is shown
- **THEN** the black lattice dot at the fixation anchor is present
- **AND** the red fixation ring leaves a background gap around that dot
- **AND** the ring is no smaller than the observer's fixation size

#### Scenario: Probed dot blinks

- **WHEN** an inverse presentation is open
- **THEN** the probed dot starts absent at onset
- **AND** it alternates between absent and present every 500 ms for the rest of the window
- **AND** at any instant at most one lattice dot differs from the rest of the lattice
- **AND** every lattice dot is present once the presentation window closes

#### Scenario: Blink does not change the trial plan

- **WHEN** an inverse run is compared with a standard run of the same seed and geometry
- **THEN** both queues, presentation windows, gaps, retries and neighbour probes are identical

#### Scenario: Standard variant is preserved

- **WHEN** the observer presses `b`
- **THEN** the test field shows a dim lattice on black
- **AND** the probed position is a dot at full contrast for the whole window

## MODIFIED Requirements

### Requirement: Starting and ending the mode

The viewer SHALL offer a scotoma test mode with standard and inverse presentation variants. The standard variant SHALL start on `b` and the inverse variant on `i`. Either variant SHALL start from a displayed pattern or a previous results frame and carry the current eye, correction, viewing distance and pixel-path reliability unchanged. The mode SHALL end on `q` with a results frame and SHALL leave `Esc` as the application quit key. Outside the mode, `x` SHALL keep its fixation-toggle meaning.

#### Scenario: Start from a displayed pattern

- **WHEN** the observer presses `b` while any pattern is displayed
- **THEN** the static pattern is replaced by the standard test field with fixation visible and no dot lit
- **AND** the session eye, correction and viewing distance are carried into the test unchanged

#### Scenario: Start the inverse variant

- **WHEN** the observer presses `i` while any pattern is displayed
- **THEN** the static pattern is replaced by the inverse test field with fixation visible
- **AND** the session eye, correction and viewing distance are carried into the test unchanged

#### Scenario: Restart either variant from the results

- **WHEN** the results frame is displayed and the observer presses `b` or `i`
- **THEN** a new run of the standard or inverse variant starts respectively
- **AND** the previous results frame is replaced

#### Scenario: End early with q

- **WHEN** the observer presses `q` while a test is running
- **THEN** the test stops and the results frame replaces the test field
- **AND** positions that were never presented are reported as untested
- **AND** the application keeps running

#### Scenario: Quit without a record

- **WHEN** the observer presses `Esc` while a test is running
- **THEN** the application quits without writing a record

#### Scenario: Fixation control is unchanged outside the mode

- **WHEN** the observer presses `x` while no test is running
- **THEN** the fixation mark toggles exactly as before

### Requirement: Presentation timing and response

Exactly one position SHALL be in its presentation window at a time for the whole 1500 ms response window. The probed position SHALL be a lit dot in the standard variant and a dot that blinks between absent and present with a 500 ms half-period in the inverse variant. The blink SHALL NOT reset, extend or shorten the response window. The gap SHALL be sampled uniformly from 500–3000 ms. A `Space` response inside the window SHALL mark the position seen, end the presentation and record latency; expiry SHALL mark a miss. Responses outside an open window SHALL NOT be attributed to any position.

#### Scenario: Dot seen

- **WHEN** the observer presses `Space` 400 ms after a dot lights
- **THEN** that position is marked seen
- **AND** the dot goes dark immediately
- **AND** a latency of 400 ms is recorded for that attempt

#### Scenario: Blinking dot detected

- **WHEN** the observer presses `Space` 400 ms after the probed dot first disappears in the inverse variant
- **THEN** that position is marked seen
- **AND** every lattice dot is present immediately
- **AND** a latency of 400 ms is recorded for that attempt

#### Scenario: Blink stops with the window

- **WHEN** an inverse presentation window closes
- **THEN** the probed dot is present for the whole following gap
- **AND** the attempt is recorded exactly as in the standard variant

#### Scenario: Dot missed

- **WHEN** no response arrives within 1500 ms of onset
- **THEN** the presentation closes and the attempt is marked a miss
- **AND** the next gap is sampled from 500–3000 ms

#### Scenario: Response in the gap

- **WHEN** the observer presses `Space` while no presentation is open
- **THEN** the press is ignored for scoring
- **AND** it is counted in the run's late/anticipatory response total

#### Scenario: Gap bounds

- **WHEN** a gap is sampled
- **THEN** it is at least 500 ms and at most 3000 ms

### Requirement: Pause

`p` SHALL pause and resume the test. While paused no presentation SHALL advance and the clock SHALL be frozen. Pausing while a presentation is open SHALL abort it and re-queue the position as an ordinary untested trial; it SHALL NOT be recorded as a miss. Resuming SHALL start a fresh gap.

#### Scenario: Pause during a gap

- **WHEN** the observer presses `p` during a gap
- **THEN** no presentation opens until `p` is pressed again
- **AND** the remaining gap continues from where it stopped

#### Scenario: Pause while a dot is lit

- **WHEN** the observer presses `p` while a dot is lit or omitted
- **THEN** the presentation closes and that presentation is discarded
- **AND** the position is queued again and no miss is recorded

### Requirement: Live presentation frame

The test field SHALL show the fixation mark and the lattice throughout. In the standard variant the lattice SHALL be dim on black with the probed dot lit at full contrast; in the inverse variant the lattice SHALL be black on a bright background with the probed dot blinking between absent and present. The status overlay strip SHALL NOT be shown while a presentation is open. The fixation mark SHALL remain visible throughout.

#### Scenario: Overlay suppressed during a presentation

- **WHEN** a presentation is open
- **THEN** the presented frame contains no status overlay strip

#### Scenario: Overlay returns between presentations

- **WHEN** no presentation is open and the test is not paused
- **THEN** the status strip reports progress and the mode controls

#### Scenario: Paused state is announced

- **WHEN** the test is paused
- **THEN** the status strip states that the test is paused and how to resume

#### Scenario: Standard field

- **WHEN** the standard variant is running
- **THEN** the field is a dim lattice on black
- **AND** an open presentation shows one dot at full contrast

#### Scenario: Inverse field

- **WHEN** the inverse variant is running
- **THEN** the field is black dots on a bright background
- **AND** an open presentation starts with exactly one dot omitted
- **AND** that dot returns and disappears once more before the window closes

### Requirement: Results frame

When the test ends the mode SHALL display a results frame that identifies the presentation variant. Seen positions SHALL be drawn as green circles, blind positions as red circles, and untested positions as grey circles.

#### Scenario: Colour encoding

- **WHEN** the results frame is built
- **THEN** every seen position is drawn green
- **AND** every blind position is drawn red
- **AND** every untested position is drawn grey

#### Scenario: Counts reported

- **WHEN** the results frame is built
- **THEN** it states the counts of seen, blind and untested positions

#### Scenario: Inverse results are identified

- **WHEN** an inverse run ends
- **THEN** the results frame identifies the inverse variant
- **AND** it carries the inverse variant's warning that names the bright field and the blinking dark dot

### Requirement: Record contents

The record SHALL contain the presentation variant, its blink half-period, the mode settings and seed, the session context, the lattice geometry, every position with its verdict and attempts, the summary counts and clusters, the existing scale and pixel-path context, and the safety statements.

#### Scenario: Attempts are preserved

- **WHEN** a position is recorded
- **THEN** the record contains each attempt's onset, latency if any, and outcome

#### Scenario: Reproducible run

- **WHEN** a record is read back
- **THEN** its seed and lattice geometry are sufficient to rebuild the initial queue

#### Scenario: Variant is recorded

- **WHEN** an inverse run is recorded
- **THEN** the `blindspot` block states that the variant is inverse
- **AND** it records the 500 ms blink half-period
- **AND** a standard run states that the variant is standard and records no blink

### Requirement: Mode key precedence and key bar

While a test is running, `Space`, `p`, `q` and `Esc` SHALL act as defined by this capability, `f` MAY toggle fullscreen, and every other key SHALL be ignored so that pattern parameters cannot change mid-run. The on-screen key bar SHALL NOT be shown during a run and SHALL be available again once the mode ends.

#### Scenario: Parameter keys ignored

- **WHEN** the observer presses an arrow key, a digit or a family key during a run
- **THEN** the session parameters do not change
- **AND** the run continues

#### Scenario: Inverse key ignored mid-run

- **WHEN** the observer presses `i` while a test is running
- **THEN** the current run continues unchanged
- **AND** no second test starts

#### Scenario: Key bar hidden

- **WHEN** a test is running
- **THEN** pointer movement does not reveal the key bar

### Requirement: Safety statements

Every scotoma-test record and results frame SHALL carry a photosensitivity warning that names the content of the variant in use, and SHALL state that the output is not a diagnosis. The warning SHALL NOT claim that all patterns are static.

#### Scenario: Record carries the warning

- **WHEN** a standard scotoma-test record is written
- **THEN** it contains a photosensitivity warning that mentions the lit-dot presentation
- **AND** it contains the non-diagnostic statement

#### Scenario: Inverse record carries the warning

- **WHEN** an inverse scotoma-test record is written
- **THEN** it contains a photosensitivity warning that mentions the bright field and the blinking dark dot
- **AND** it contains the non-diagnostic statement

#### Scenario: Startup notice names both variants

- **WHEN** the application starts before a variant has been chosen
- **THEN** the startup notice warns about the standard lit dot and the inverse bright field with its blinking dark dot
- **AND** it carries the non-diagnostic disclaimer

#### Scenario: Results frame carries the statement

- **WHEN** the results frame is displayed
- **THEN** it states that the result is not a medical diagnosis
