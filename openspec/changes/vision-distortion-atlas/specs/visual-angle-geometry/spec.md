# visual-angle-geometry

## Purpose

Translate between what a pattern occupies on the panel and what it occupies in the observer's visual field, so that distortion targets can be specified, verified and reported in pixels, millimetres, degrees and arcmin at a stated viewing distance.

## ADDED Requirements

### Requirement: Angular scale from pixel pitch and viewing distance

The system SHALL derive the angular size of one pixel in arcmin from the physical pixel pitch and the active viewing distance, and SHALL report each pattern dimension in pixels, millimetres and degrees or arcmin.

#### Scenario: Scale at a working distance

- **WHEN** the pixel pitch is 0.178 mm and the viewing distance is set to 400 mm
- **THEN** the system reports 1.53 arcmin per pixel, and a target 39 pixels wide is reported as 1.0 degree and 6.95 mm

#### Scenario: Distance change rescales the report only

- **WHEN** the viewing distance is changed from 400 mm to 500 mm
- **THEN** the reported angular size of the unchanged pixel target shrinks proportionally and the readout shows the new arcmin-per-pixel value

### Requirement: Physical scale calibration on the panel

The system SHALL let the observer match an on-screen reference bar to a known physical length and SHALL use the resulting pixels-per-millimetre value for all size reporting, in preference to panel-reported dimensions.

#### Scenario: Calibrating against a ruler

- **WHEN** the observer enters calibration and adjusts the reference bar until it matches 100 mm measured on a ruler held against the screen
- **THEN** the system stores the resulting pixels-per-millimetre value and uses it for millimetre, degree and arcmin values in that and later sessions

#### Scenario: Starting uncalibrated

- **WHEN** a session starts and no calibration is stored
- **THEN** the system derives a provisional pitch from the reported panel size, marks the derived values as uncalibrated, and prompts the observer to calibrate before grading

#### Scenario: Rejecting an implausible calibration

- **WHEN** the entered reference length would imply a pixels-per-millimetre value differing from the panel-derived value by more than 25 percent
- **THEN** the system warns that the value is implausible and requires confirmation before storing it

### Requirement: Field and pitch fitting for the panel

The system SHALL compute, for a requested field of view and grid count at the active distance, a whole-pixel pitch that fits inside the window, and SHALL NOT silently present a truncated or fractionally pitched grid.

#### Scenario: Requested field exceeds the panel

- **WHEN** a 20-degree grid of 20 squares is requested at 600 mm and the required pixels exceed the window height
- **THEN** the system reports the largest field that fits and either reduces the square count or asks the observer before cropping

#### Scenario: Fractional pitch is snapped

- **WHEN** the computed pitch for the requested field is 39.3 pixels
- **THEN** the grid is drawn with a whole-pixel pitch and the reported field is recomputed from that integer pitch

### Requirement: Declared viewing distance per session

The system SHALL expose the viewing distance as an explicit session value that can be changed with a single control, and SHALL record the value in every exported result.

#### Scenario: Distance is part of the record

- **WHEN** a session is exported
- **THEN** the exported record contains the viewing distance, the pixels-per-millimetre value and whether that value was calibrated or panel-derived
