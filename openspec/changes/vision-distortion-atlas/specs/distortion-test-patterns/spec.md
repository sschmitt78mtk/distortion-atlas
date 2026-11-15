# distortion-test-patterns

## Purpose

Define the adjustable visual references whose straightness, symmetry, density and contrast reveal how an eye distorts an image: Amsler grids, graded dotted straightness lines, astigmatism dials and halo, glare and ghosting targets.

## ADDED Requirements

### Requirement: Amsler grid variants

The system SHALL render an Amsler grid with an adjustable square count, a selectable colour pairing among black-on-white, white-on-black, red-on-black and blue-on-yellow, and a line-contrast control that can fade the lines toward the background without changing their geometry.

#### Scenario: Switching colour pairing

- **WHEN** the observer cycles the Amsler colour pairing from black-on-white to red-on-black
- **THEN** the same grid geometry is redrawn in the new pairing and the parameter readout names the pairing in use

#### Scenario: Threshold fade for early scotoma

- **WHEN** the observer lowers the line contrast toward the background level
- **THEN** the grid lines remain whole-number pixel widths while their luminance approaches the background, so that a visual field defect appears before the lines vanish entirely

### Requirement: Graded dotted straightness lines

The system SHALL render a set of parallel dotted lines in M-chart style with adjustable line count, dot pitch and orientation, displayed together with a visible grading reference so that each line can be judged and scored on its own.

#### Scenario: Grading one line

- **WHEN** the observer selects a line and assigns a distortion grade to it
- **THEN** the grade is stored together with the line index, the line count, the dot pitch and the orientation used for that judgement

#### Scenario: Changing pitch keeps the field centred

- **WHEN** the dot pitch or line count is changed while the pattern is displayed
- **THEN** the line set stays centred on the fixation mark and no line moves by a fraction of a pixel

### Requirement: Astigmatism clock dial

The system SHALL render a radial dial of line pairs at regular angular steps with an adjustable spoke count and rotation, together with a crossed-line target at the same orientations so the sharpest and darkest direction can be identified.

#### Scenario: Identifying the darkest direction

- **WHEN** the observer selects the spoke that appears darkest or sharpest
- **THEN** the system records the selected angle together with the dial rotation and spoke count in use

#### Scenario: Rotating the dial

- **WHEN** the rotation control is used
- **THEN** the spokes are redrawn at the next angular step without changing their length or width

### Requirement: Halo, veiling glare and ghost targets

The system SHALL render a point source on a black field with adjustable size and luminance, a bright surround containing a dim central target, and a high-contrast edge with adjustable ghost separation and direction.

#### Scenario: Estimating halo size

- **WHEN** the observer raises the point-source size or luminance
- **THEN** the readout shows the source diameter in pixels and millimetres so the perceived halo can be compared against a known source

#### Scenario: Separating a ghost image

- **WHEN** the ghost separation and direction controls are used
- **THEN** a second copy of the edge is displaced by whole pixels in the chosen direction while the primary edge stays fixed

### Requirement: Centre-anchored, whole-pixel geometry

Every pattern SHALL be anchored to the central fixation position and SHALL use whole-pixel line widths, pitches and offsets, so that changing a parameter never shifts the reference field or introduces sub-pixel blur that would be mistaken for a visual distortion.

#### Scenario: Minimum line width

- **WHEN** a pitch or line count would require a line thinner than one pixel
- **THEN** the system keeps the line at one pixel and reports the pitch that was actually drawn

#### Scenario: Pattern parameter changes do not move the field

- **WHEN** the observer changes any geometric parameter
- **THEN** the outer boundary and centre of the pattern stay fixed and only the internal geometry changes
