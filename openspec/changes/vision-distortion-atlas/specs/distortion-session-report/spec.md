# distortion-session-report

## Purpose

Turn a viewing session into a record: what was shown, to which eye, at what distance, and how distorted the observer judged it to be, so that findings can be compared across eyes and over time.

## ADDED Requirements

### Requirement: Per-item distortion grading

The system SHALL let the observer assign an integer distortion grade from 0 to 9 to the currently displayed item and SHALL store each grade with the identity of the item it belongs to.

#### Scenario: Recording a grade

- **WHEN** the observer presses a grade key from 0 to 9 while an Amsler or M-chart item is displayed
- **THEN** the grade is stored with the pattern family, the item index and the geometry and colour parameters in force at that moment

#### Scenario: Regrading an item

- **WHEN** the observer assigns a second grade to an item that already has one
- **THEN** the latest grade replaces the earlier value and the record notes that the item was graded more than once

#### Scenario: Grading without a visible pattern

- **WHEN** the observer presses a grade key before any pattern has been shown
- **THEN** no grade is recorded and the system states that a pattern must be visible first

### Requirement: Eye under test and session context

The system SHALL record which eye is under test, whether the observer is wearing their correction, and the ambient condition note for the session, and SHALL remind the observer to cover one eye when a single eye is selected.

#### Scenario: Selecting one eye

- **WHEN** the observer selects the left or right eye as the eye under test
- **THEN** the reminder to cover the other eye is shown in the readout and the selection is stored with every grade that follows

#### Scenario: Context captured once per session

- **WHEN** the session is exported
- **THEN** the exported record names the eye under test, the correction state and the ambient note together with every grade

### Requirement: Session export

The system SHALL export, on request, a PNG image of the pattern exactly as displayed and a machine-readable record of the session containing the pattern parameters, geometry values and all grades.

#### Scenario: Exporting a session

- **WHEN** the observer requests an export
- **THEN** a PNG of the current rendered buffer and a JSON record are written to the export location under a timestamped name, and the written paths are reported back

#### Scenario: Export fails

- **WHEN** the export location is not writable
- **THEN** the system reports the failure with the attempted path and leaves the session state unchanged and still usable

#### Scenario: Exported image matches the display

- **WHEN** the PNG is compared with what was on screen at export time
- **THEN** the pixel dimensions and pattern content are identical, excluding the readout overlay

### Requirement: Non-diagnostic framing

The system SHALL state that it supports observation of visual distortion and is not a medical device, and SHALL repeat that statement in the exported record together with a warning about flashing content.

#### Scenario: Start-up notice

- **WHEN** a session starts
- **THEN** the non-diagnostic notice and the photosensitivity warning are shown before any pattern is displayed

#### Scenario: Record carries the notice

- **WHEN** a session record is exported
- **THEN** it contains the same non-diagnostic statement so a result cannot be read as a diagnosis
