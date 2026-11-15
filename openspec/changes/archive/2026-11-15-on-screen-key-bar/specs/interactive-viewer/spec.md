# interactive-viewer delta

## ADDED Requirements

### Requirement: Pointer-revealed key bar

The viewer SHALL draw a bar along the bottom edge of the window in which every
key in the control map is a separate button carrying a short caption and its key
as a hint, SHALL keep that bar hidden until the pointer moves, and SHALL hide it
again after 3 seconds without pointer activity. Keyboard input SHALL NOT reveal
the bar, and no touch input SHALL be required.

#### Scenario: Pointer reveals the bar

- **WHEN** the observer moves the pointer over the viewer
- **THEN** the key bar appears along the bottom edge with one button for every
  key in the control map, including the ten grade digits

#### Scenario: Idle hides the bar

- **WHEN** 3 seconds pass without pointer activity after the bar was revealed
- **THEN** the bar is removed, the cursor is hidden and the pattern underneath is
  repainted unaltered

#### Scenario: Keyboard leaves the bar hidden

- **WHEN** the observer presses control keys without touching the pointer
- **THEN** the bar stays hidden and the readout strip reflects the change

### Requirement: Buttons show live state

Each button SHALL show the current value of the control it stands for, so the bar
doubles as a status display: the active pattern family, the eye under test, the
correction state, the HUD and fixation toggles and the grade recorded for the
item on screen.

#### Scenario: Active family and toggles

- **WHEN** the amsler family is displayed with the HUD and fixation mark on
- **THEN** the amsler button, the HUD button and the fixation button are shown as
  active

#### Scenario: Recorded grade

- **WHEN** the observer has graded the current item 3
- **THEN** the button for key 3 shows that grade as the active digit

#### Scenario: Eye and correction captions

- **WHEN** the session view is set to the left eye with correction worn
- **THEN** the eye button reads the current eye and the correction button reads
  the current correction state

### Requirement: A click is equivalent to its key

Clicking a button SHALL dispatch the identical key string through the same
session dispatch used by the keyboard, so the parameter change, message, grade,
export, fullscreen switch or quit is indistinguishable from pressing that key.

#### Scenario: Family button

- **WHEN** the observer clicks the dial button
- **THEN** the session switches to the dial family, re-renders and names the
  change in the readout strip exactly as key `d` does

#### Scenario: Grade and export buttons

- **WHEN** the observer clicks grade 7 and then the export button
- **THEN** a grade of 7 is stored for the item on screen and the PNG plus JSON are
  written as if keys `7` and `s` had been pressed

#### Scenario: Quit button

- **WHEN** the observer clicks the quit button
- **THEN** the session ends immediately, with no confirmation step

#### Scenario: Fullscreen button

- **WHEN** the observer clicks the fullscreen button
- **THEN** the window switches between fullscreen and the calibrated window size
  exactly as key `f` does

### Requirement: Key bar is chrome only

The bar, its highlight and its captions SHALL be presentation chrome: they SHALL
NOT change the rendered buffer, the exported PNG, the session record or the
pixel-path comparison, and the bar SHALL be suppressed while the one-pixel
self-check pattern is on screen, including the self-check frame held for visual
judgement.

#### Scenario: Export is pixel-identical

- **WHEN** the observer exports while the bar is visible
- **THEN** the exported PNG is pixel-identical to the rendered pattern and the
  session remains reported as reliable

#### Scenario: Self-check suppression

- **WHEN** the self-check pattern is displayed, including the held frame of
  `--self-check`
- **THEN** the bar is never drawn, whatever the pointer does

#### Scenario: Self-check dismissal by click

- **WHEN** the observer clicks while the held self-check frame is displayed
- **THEN** the frame closes just as it does for a key press

### Requirement: Cursor follows the bar

The cursor SHALL be hidden while the bar is hidden, SHALL be visible as the
pointer while the bar is visible, and SHALL use the pointing-hand shape while it
is over a button.

#### Scenario: Hidden while observing

- **WHEN** the bar has auto-hidden
- **THEN** no cursor is drawn over the pattern

#### Scenario: Hover feedback

- **WHEN** the pointer rests on a button
- **THEN** the button is highlighted and the cursor shows the pointing-hand shape

### Requirement: Held buttons repeat and Shift coarsens

Holding a step button SHALL repeat that step at the keyboard's auto-repeat
cadence and SHALL stop when the button is released; `Shift`+click SHALL apply
the coarse step of the same control; grading, toggles, export, fullscreen, reset
and quit SHALL NOT repeat.

#### Scenario: Holding a geometry button

- **WHEN** the observer presses and holds the geometry plus button
- **THEN** the primary geometry parameter keeps increasing until release, with
  the readout strip naming each step

#### Scenario: Coarse pointer step

- **WHEN** the observer Shift-clicks the distance plus button
- **THEN** the viewing distance moves by the coarse step instead of the single
  step

#### Scenario: Grade button does not repeat

- **WHEN** the observer presses and holds a grade digit
- **THEN** exactly one grade is recorded for that item
