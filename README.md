# distortion-atlas — visual-distortion patterns for a high-PPI panel

__STILL IN DEVELOPMENT__

A live, fullscreen viewer for **image distortion** rather than acuity: Amsler
grid variants, M-chart dotted straightness lines, an astigmatism clock dial and
halo / veiling-glare / ghost-edge targets, all driven from the keyboard or the
pointer, all with exact visual-angle readouts and a per-item 0–9 grade that
exports as PNG + JSON.

**distortion-atlas supports observation of visual distortion. It is not a medical
device and its output is not a diagnosis.** All current patterns are static; any
future flashing content would carry a photosensitivity risk.

**AI-generated note:** everything in this repository is AI-generated — the code
and tests as well as the OpenSpec artifacts under `openspec/` (proposals,
designs, capability specs and task lists) and this README. It was written by an
agent through the OpenSpec workflow only; no human has authored or reviewed it
line by line. Treat all of it as unverified: confirm behaviour by reading and
running the code and tests rather than trusting this documentation.

## Install

Python 3.12 or newer. From a checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

Use `pip install -e .` for development. `requirements.txt` pins the exact runtime
versions the target panel is validated with (numpy, Pillow, PyQt6); the
`PyQt6-Qt6` wheel has to match the `PyQt6` bindings. The same versions are also
installed for `/usr/bin/python3` on the development machine, so the commands
below work with or without an active venv.

## Quick start

```bash
distortion-atlas --self-check           # readout + checkerboard, closes on a key press
distortion-atlas --self-check --hold 0  # same readout, no wait (scripted runs)
distortion-atlas                        # fullscreen viewer
```

The installed console script, `python3 -m distortion_atlas` and
`python3 main.py` are equivalent; the last one works from a checkout without
installing.

`--self-check` prints the panel, scale, field fit and pixel-path readout, then
keeps the checkerboard on screen so the presented pixels can actually be judged:
any key closes it, `--hold SECONDS` bounds the wait, `--hold 0` returns straight
away.

All commands print the non-diagnostic and photosensitivity notice before anything
is drawn. On this desktop Qt 6.6 needs a GLib schema shim; `main.py` detects that
and applies it itself, so no environment variable is required (see
**Troubleshooting**).

## First-run walkthrough

1. **Turn display scaling off.** `distortion-atlas` forces `QT_SCALE_FACTOR=1`
   and asserts a 1:1 surface-versus-buffer match, but a compositor that still
   resamples will be reported as unreliable rather than silently trusted.
2. `distortion-atlas --self-check` first: it names the panel from EDID
   (`/sys/class/drm/card1-eDP-1/edid`, `B156HAN12.H` on the target), the
   pixels-per-millimetre value, whether that value is `calibrated` or
   `panel_derived`, and the field that will fit (`20 squares @ 39 px = 19.7°`).
   The checkerboard then stays on screen until a key press, so the readout strip
   and the grey field can be read without hurrying; `--hold 5` bounds it to five
   seconds.
3. Start the viewer with `distortion-atlas`, then press `x` twice to watch the
   fixation mark disappear and return, and `c` to show the one-pixel
   checkerboard. At 1:1 it reads as uniform mid-grey; a moiré or a visible
   pattern means the pixel path is being scaled.
4. **Calibrate.** Measure 100 mm on the screen with a ruler and store the value
   that matches it, e.g.
   `python3 -c "from distortion_atlas import calibration; calibration.save_calibration(5.6, reference=5.666)"`.
   The stored value lives in `$XDG_CONFIG_HOME/distortion-atlas/config.json`
   (`~/.config/distortion-atlas/config.json` by default). A value differing from
   the panel-derived pitch by more than 25 % is refused unless it is confirmed
   with `confirm=True`. A calibration stored under the pre-rename
   `~/.config/visiontest/config.json` is still read; the next save writes the new
   path.
5. Set the working distance with `[` / `]` (50 mm steps, 200–1000 mm), then press
   `m` until the readout names the eye you are testing and cover the other one;
   the reminder stays in the readout.
6. Choose a family (`a`, `l`, `d`, `n`, `v`, `e`, `c`), adjust it, and grade each
   item with `0`–`9`.
7. Export with `s` (or start with `--export-dir PATH`).

## Key map

`Shift` coarsens the arrow keys; `Ctrl` coarsens `+` `-` `[` `]`.

| key | action |
|---|---|
| `a` `l` `d` `n` `v` `e` `c` | Amsler grid / M-chart lines / astigmatism dial / halo / veiling glare / ghost edge / pixel-path self-check |
| `Tab` `Shift+Tab` | next / previous variant in the family (for the lines family this also selects the line you are grading) |
| `↑` `↓` | primary geometry: squares, dot pitch, spoke count, source size, surround size, ghost offset (±1, coarse ±5) |
| `←` `→` | secondary: field of view (Amsler, ±1°/±5°), line count, dial rotation (±15°/±75°), ghost direction |
| `+` `-` | contrast (±5, coarse ±20); for the halo family this is the source luminance and for the veil family the target/surround ratio |
| `[` `]` | viewing distance (50 mm, coarse 200 mm) |
| `m` | eye under test: left → right → both |
| `w` | correction worn (toggle) |
| `0`–`9` | grade the item on screen |
| `h` | readout overlay on/off |
| `x` | fixation mark on/off |
| `s` | export PNG + JSON |
| `f` | fullscreen / windowed |
| `r` | reset the active family's parameters (keeps distance, eye, correction, ambient) |
| `q` `Esc` | quit |

Families without a secondary control (halo, veil, self-check) say so in the
readout instead of moving something silently.

## Pointer controls

Moving the pointer reveals a key bar along the bottom edge: one button for every
key above, captioned with its action and hinting the key it stands for. The bar
disappears after 3 seconds without pointer activity, and pressing a key never
reveals it, so observation stays chrome-free. A click dispatches the same key
string as the keyboard, `Shift`+click applies the coarse step and holding a step
button repeats it at the keyboard's auto-repeat cadence. The bar is never drawn
for the pixel-path self-check (`c`), so that frame can still be judged by eye
without chrome. No touch input is required or handled.

## What gets exported

`s` writes `<tool>-<YYYYmmdd-HHMMSS>.png` and `.json` into `exports/` (or
`--export-dir`). The PNG is the rendered buffer **without** the readout strip or
the transient pointer-only key bar, so it is pixel-identical to the rendered
pattern itself. The only on-screen pixels that differ from the exported image are
the readout strip and, while the bar is revealed, the bottom band it covers.
The JSON record contains the
pattern parameters, every scale value with its `calibrated`/`panel_derived`
source, the eye, correction state, ambient note, viewing distance, all grades
(with regrade counts), display-limited contrast flags, the panel identity, the
pixel-path result and the non-diagnostic statement. A write failure is reported
with the attempted path and leaves the session usable.

## Tests

```bash
python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python3 -m unittest tests.test_viewer -v
```

CPython 3.12 returns exit code 5 when a discovery run finds no tests at all,
which is why `tests/test_package.py` exists as the entry-point smoke test.

## Troubleshooting

Both problems below are environment issues that hit every Qt 6.6 application on
this machine, not distortion-atlas bugs.

### `undefined symbol: _ZN5QFont11tagToStringEj`

```
PyQt6/QtGui.abi3.so: undefined symbol: _ZN5QFont11tagToStringEj, version Qt_6
screen: unavailable (…); using 1920×1080 for the readout
```

`PyQt6` (the bindings) and `PyQt6-Qt6` (the Qt runtime) are separate wheels, and
the runtime must stay in the same minor series. A venv that resolved
`PyQt6==6.6.1` against `PyQt6-Qt6==6.12.0` builds no window at all;
`--self-check` still completes because the presenter degrades to a headless
readout. Fix and pin:

```bash
pip install "PyQt6==6.6.1" "PyQt6-Qt6==6.6.3" "PyQt6-sip==13.13.1"
pip list | grep -i pyqt
```

`requirements.txt` now pins all three so a fresh install cannot drift apart.

### `Settings schema … does not contain a key named 'antialiasing'`

```
GLib-GIO-ERROR: Settings schema 'org.gnome.settings-daemon.plugins.xsettings'
does not contain a key named 'antialiasing'
```

gnome-settings-daemon moved the font keys to
`org.gnome.settings-daemon.plugins.xsettings.deprecated`, but Qt 6.6 still reads
them from the old schema id and GLib turns the missing key into an abort that no
Python handler can catch. `distortion-atlas` probes for the key before Qt is
imported and, if it is missing, compiles the shim packaged in
`distortion_atlas/qtshim/` and points `GSETTINGS_SCHEMA_DIR` at it, printing one
line:

```
note: GLib schema shim applied for Qt 6.6 (GSETTINGS_SCHEMA_DIR=…/distortion_atlas/qtshim); see README troubleshooting
```

The shim also works manually, and is not needed at all with PyQt6 6.7 or newer:

```bash
glib-compile-schemas distortion_atlas/qtshim
GSETTINGS_SCHEMA_DIR=distortion_atlas/qtshim python3 main.py --self-check --hold 0
```

If the installed package directory is not writable (a system-wide wheel install),
point `DISTORTION_ATLAS_SCHEMA_DIR` at a writable copy of that directory instead,
or install PyQt6 6.7 or newer.

With the shim, `--self-check` reports
`1:1 pixel path: surface 1920×1080 equals buffer 1920×1080 at scale factor 1`
on the target panel. Nothing in `distortion-atlas` imports Qt in a way that
depends on the shim; `tests/test_backend_shim.py` covers both the rescue and the
no-op path.

## Geometry notes

- One pixel subtends `atan(mm_per_px / distance)`; at 0.178 mm and 400 mm that
  is 1.53 arcmin per pixel, so a 20° Amsler field needs ≈785 px.
- The Amsler field is anchored to the centre and its outer boundary is
  bit-identical for every square count: the pitch is recomputed from the field
  (`divide_positions`), so a cell is at most one pixel wider than nominal instead
  of the grid drifting.
- All strokes, pitches and offsets are whole pixels; only luminance is
  sub-code-value, and only in the halo/veil family, where a 4×4 ordered dither
  extends the effective contrast resolution.
- Reported sizes add up the per-pixel angle (`arcmin_per_px`, as the spec
  defines it). Over a full 20° field that linear model reads about 1 % wider
  than `2·atan(width/2/distance)`, so a wide field is reported a few tenths of a
  degree larger than the exact geometric angle; single targets such as a 39 px
  dot agree to better than 0.01°.
