# Spec Delta

## Purpose

A dot-by-dot detection session on the `lines` dot lattice: one dot is presented at a time, the observer reports whether it was seen, and the session records which positions were seen, which were blind, and which were never reached.

## ADDED Requirements

### Requirement: Starting and ending the mode

The viewer SHALL offer a scotoma test mode that replaces the displayed pattern with a test field built from the current session context (eye, correction, viewing distance, pixel-path reliability). The mode SHALL start on `b` while a pattern is displayed, end on `q` with a results frame, and SHALL leave `Esc` as the application quit key. Outside the mode, `x` SHALL keep its fixation-toggle meaning.

#### Scenario: Start from a displayed pattern

- **WHEN** the observer presses `b` while any pattern is displayed
- **THEN** the static pattern is replaced by the test field with fixation visible and no dot lit
- **AND** the session eye, correction and viewing distance are carried into the test unchanged

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

### Requirement: Trial plan

The mode SHALL test every position of the inner 5×5 ring around fixation, excluding the exact centre position occupied by the fixation mark (24 positions), and SHALL additionally test a random sample of the remaining field positions. No position SHALL be presented before its turn in the randomised order, and the total number of presentations SHALL be capped. Positions that are queued but never presented SHALL appear in the results as untested.

#### Scenario: Inner ring is always covered

- **WHEN** a test runs to completion without the cap being reached
- **THEN** all 24 inner-ring positions have been presented at least once

#### Scenario: Random outside sample without repetition

- **WHEN** the outside sample is built
- **THEN** every sampled position lies outside the inner ring
- **AND** no position appears twice in the initial queue
- **AND** the sample is drawn from a recorded seed so the run can be reproduced

#### Scenario: Trial cap reached

- **WHEN** the configured presentation cap is reached before the queue is empty
- **THEN** the test ends and the results frame is shown
- **AND** the remaining positions are reported as untested

### Requirement: Presentation timing and response

Exactly one dot SHALL be lit at a time, for the whole response window of 1500 ms measured from onset. The gap between presentations SHALL be sampled uniformly between 500 ms and 3000 ms. A response (`Space`) inside the window SHALL mark the position seen, end the presentation immediately, and record the latency from onset. Expiry of the window without a response SHALL mark a miss. Responses outside an open window SHALL NOT be attributed to any position.

#### Scenario: Dot seen

- **WHEN** the observer presses `Space` 400 ms after a dot lights
- **THEN** that position is marked seen
- **AND** the dot goes dark immediately
- **AND** a latency of 400 ms is recorded for that attempt

#### Scenario: Dot missed

- **WHEN** no response arrives within 1500 ms of onset
- **THEN** the dot goes dark and the attempt is marked a miss
- **AND** the next gap is sampled from 500–3000 ms

#### Scenario: Response in the gap

- **WHEN** the observer presses `Space` while no dot is lit
- **THEN** the press is ignored for scoring
- **AND** it is counted in the run's late/anticipatory response total

#### Scenario: Gap bounds

- **WHEN** a gap is sampled
- **THEN** it is at least 500 ms and at most 3000 ms

### Requirement: Retry and adaptive probing

A miss SHALL be retried exactly once, no sooner than five other presentations later. Two misses at the same position SHALL mark it blind. A blind position SHALL add its eight neighbouring positions to the queue when they lie inside the test field and have not been queued or presented, so a confirmed blind region is mapped outward until its surround is seen. A position seen on any attempt SHALL be marked seen and SHALL NOT be presented again.

#### Scenario: Miss then seen

- **WHEN** a position misses and the retry is seen
- **THEN** the position is marked seen
- **AND** it is not presented again

#### Scenario: Miss twice

- **WHEN** a position misses on both attempts
- **THEN** the position is marked blind
- **AND** its eight neighbours are queued subject to the field and duplication rules

#### Scenario: Retry spacing

- **WHEN** a position misses
- **THEN** at least five other presentations occur before the retry

#### Scenario: Probing respects the field edges

- **WHEN** a blind position lies on the edge of the test field
- **THEN** neighbours outside the field are not queued
- **AND** already presented or already queued neighbours are not queued twice

### Requirement: Pause

`p` SHALL pause and resume the test. While paused no presentation SHALL advance and the clock SHALL be frozen. Pausing while a dot is lit SHALL abort that presentation and re-queue the position as an ordinary untested trial; it SHALL NOT be recorded as a miss. Resuming SHALL start a fresh gap.

#### Scenario: Pause during a gap

- **WHEN** the observer presses `p` during a gap
- **THEN** no dot appears until `p` is pressed again
- **AND** the remaining gap continues from where it stopped

#### Scenario: Pause while a dot is lit

- **WHEN** the observer presses `p` while a dot is lit
- **THEN** the dot goes dark and that presentation is discarded
- **AND** the position is queued again and no miss is recorded

### Requirement: Live presentation frame

The test field SHALL show the dot lattice at reduced contrast with the fixation mark visible, SHALL show the lit dot as the only high-contrast element, and SHALL NOT show the status overlay strip while a dot is lit. The fixation mark SHALL remain visible throughout.

#### Scenario: Overlay suppressed during a presentation

- **WHEN** a dot is lit
- **THEN** the presented frame contains no status overlay strip

#### Scenario: Overlay returns between presentations

- **WHEN** no dot is lit and the test is not paused
- **THEN** the status strip reports progress and the mode controls

#### Scenario: Paused state is announced

- **WHEN** the test is paused
- **THEN** the status strip states that the test is paused and how to resume

### Requirement: Results frame

When the test ends the mode SHALL display a results frame. Seen positions SHALL be drawn as green circles, blind positions as red circles, and untested positions as grey circles.

#### Scenario: Colour encoding

- **WHEN** the results frame is built
- **THEN** every seen position is drawn green
- **AND** every blind position is drawn red
- **AND** every untested position is drawn grey

#### Scenario: Counts reported

- **WHEN** the results frame is built
- **THEN** it states the counts of seen, blind and untested positions

### Requirement: Blind clusters

The results frame SHALL group blind positions that touch horizontally, vertically or diagonally into clusters, and SHALL report each cluster with its dot count, its centre in degrees and its extent in degrees.

#### Scenario: Cluster summary

- **WHEN** two or more blind positions touch
- **THEN** they are reported as one cluster with a dot count, centre and extent in degrees

### Requirement: Attention check

The results frame SHALL report the number of seen inner-ring positions out of 24 as a fixation and attention check.

#### Scenario: Attention check reported

- **WHEN** the results frame is built
- **THEN** the number of seen inner-ring positions out of 24 is reported

#### Scenario: Uninterpretable run

- **WHEN** two or fewer of the 24 inner-ring positions are seen
- **THEN** the results frame states that the run is not interpretable rather than presenting a scotoma map

### Requirement: Record export

`s` SHALL export the results frame as PNG plus a JSON record when the results frame is displayed, and SHALL refuse while a test is running.

#### Scenario: Export results

- **WHEN** the observer presses `s` on the results frame
- **THEN** a PNG and a JSON file are written to the export directory
- **AND** the JSON contains a `blindspot` block with the per-position attempts

#### Scenario: Export refused mid-run

- **WHEN** the observer presses `s` while a test is running
- **THEN** no file is written
- **AND** the status strip explains that the test must end first

#### Scenario: Export matches the display

- **WHEN** the results PNG is written
- **THEN** it is the displayed results frame with the status strip removed

### Requirement: Record contents

The record SHALL contain the mode settings and seed, the session context, the lattice geometry, every position with its verdict and attempts, the summary counts and clusters, the existing scale and pixel-path context, and the safety statements.

#### Scenario: Attempts are preserved

- **WHEN** a position is recorded
- **THEN** the record contains each attempt's onset, latency if any, and outcome

#### Scenario: Reproducible run

- **WHEN** a record is read back
- **THEN** its seed and lattice geometry are sufficient to rebuild the initial queue


### Requirement: Mode key precedence and key bar

While a test is running, `Space`, `p`, `q` and `Esc` SHALL act as defined by this capability, `f` MAY toggle fullscreen, and every other key SHALL be ignored so that pattern parameters cannot change mid-run. The on-screen key bar SHALL NOT be shown during a run and SHALL be available again once the mode ends.

#### Scenario: Parameter keys ignored

- **WHEN** the observer presses an arrow key, a digit or a family key during a run
- **THEN** the session parameters do not change
- **AND** the run continues

#### Scenario: Key bar hidden

- **WHEN** a test is running
- **THEN** pointer movement does not reveal the key bar

### Requirement: Safety statements

Every scotoma-test record and results frame SHALL carry a photosensitivity warning that names this mode's flashing content, and SHALL state that the output is not a diagnosis. The warning SHALL NOT claim that all patterns are static.

#### Scenario: Record carries the warning

- **WHEN** a scotoma-test record is written
- **THEN** it contains a photosensitivity warning that mentions the flashing dot presentation
- **AND** it contains the non-diagnostic statement

#### Scenario: Results frame carries the statement

- **WHEN** the results frame is displayed
- **THEN** it states that the result is not a medical diagnosis


