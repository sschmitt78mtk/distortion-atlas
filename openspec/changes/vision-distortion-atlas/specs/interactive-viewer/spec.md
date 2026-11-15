# interactive-viewer

## Purpose

Present the distortion references live on screen in a way the observer can drive from the keyboard, while guaranteeing that what reaches the panel is exactly the rendered reference and nothing else.

## ADDED Requirements

### Requirement: Live fullscreen presentation

The system SHALL present the active pattern in a fullscreen window that is generated at run time and re-rendered as soon as a control changes it, without requiring the image to be saved and reopened first.

#### Scenario: Parameter change during viewing

- **WHEN** the observer changes the grid pitch while a pattern is displayed fullscreen
- **THEN** the window shows the new pattern before the next key event is processed and the window stays fullscreen

#### Scenario: Switching pattern family

- **WHEN** the observer selects a different pattern family
- **THEN** the new pattern appears centred on the same fixation position and the previous family's parameters are retained for when it is selected again

### Requirement: Central fixation mark

The system SHALL draw a central fixation mark on every pattern, small enough not to mask the pattern centre, and SHALL allow it to be toggled off and back on without leaving the pattern.

#### Scenario: Mark is present by default

- **WHEN** any pattern is shown
- **THEN** a fixation mark is visible at the pattern centre and the readout names its type and size

#### Scenario: Mark is hidden for a centre check

- **WHEN** the observer toggles the fixation mark off
- **THEN** the mark disappears from the displayed image and the pattern itself is unchanged

#### Scenario: Grade is tied to a visible fixation

- **WHEN** the observer submits a grade while the fixation mark is hidden
- **THEN** the system still records the grade and notes in the record that the fixation mark was hidden for that judgement

### Requirement: Pixel path integrity guard

The system SHALL verify at start-up that the rendered buffer is presented one pixel per screen pixel with no filtering or scaling, and SHALL warn the observer when that cannot be guaranteed.

#### Scenario: Self-check pattern

- **WHEN** start-up verification runs
- **THEN** the system shows a one-pixel checkerboard whose average appearance is uniform grey only if the path is unscaled, and states the result

#### Scenario: Scaling detected

- **WHEN** the presented surface size does not match the rendered buffer size
- **THEN** the system names the mismatch, marks subsequent measurements as unreliable, and offers to continue or abort

### Requirement: Keyboard control of pattern and geometry

The system SHALL provide keyboard control for pattern selection, geometry, contrast, viewing distance, eye under test and grading, with defined step sizes and a modifier for coarse adjustment, and SHALL keep quit and fullscreen exit reachable from every state.

#### Scenario: Stepping a parameter

- **WHEN** the observer presses the increase key for the primary geometry parameter
- **THEN** the parameter advances by one documented step and the readout shows the new value in pixels and degrees

#### Scenario: Coarse adjustment

- **WHEN** the observer presses the same key with the coarse modifier held
- **THEN** the parameter advances by the larger documented step for that parameter

#### Scenario: Escape from any state

- **WHEN** the observer presses the quit key or Escape
- **THEN** the application exits cleanly from fullscreen and restores the previous display state

### Requirement: Readout overlay

The system SHALL offer a toggleable overlay showing the active pattern, its parameters, the viewing distance, the eye under test and the resulting angular sizes, and SHALL exclude the overlay from exported images.

#### Scenario: Overlay hidden for judgement

- **WHEN** the observer hides the overlay
- **THEN** the pattern remains fully visible and unchanged, with no residual text drawn into the image

#### Scenario: Export without overlay

- **WHEN** an image is exported while the overlay is visible
- **THEN** the exported image contains only the pattern and fixation mark, and the overlay content is written to the session record instead
