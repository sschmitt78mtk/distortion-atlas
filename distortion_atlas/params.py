"""Pattern parameters, per-family defaults and the keyboard control map.

One mutable :class:`Params` object holds every family's settings at once, so
switching family keeps the other family's parameters for the next visit while
the fixation anchor, distance and eye stay untouched. The control map is data,
not scattered ``if key == ...`` code: the table below is what ``README.md``
documents and what the tests check for duplicate keys and step sizes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields

from .patterns.glare import GHOST_DIRECTIONS
from .patterns.grids import LINE_ORIENTATIONS, PAIRING_NAMES

FAMILIES: tuple[str, ...] = (
    "amsler",
    "lines",
    "dial",
    "halo",
    "veil",
    "ghost",
    "selfcheck",
)

EYES: tuple[str, ...] = ("left", "right", "both")
FIXATION_KINDS: tuple[str, ...] = ("ring", "dot")

#: Variants cycled with Tab inside each family.
VARIANTS: dict[str, tuple[str, ...]] = {
    "amsler": PAIRING_NAMES,
    "lines": LINE_ORIENTATIONS,
    "dial": ("pairs",),
    "halo": ("standard",),
    "veil": ("standard",),
    "ghost": ("edge",),
    "selfcheck": ("standard",),
}

#: Inclusive limits for every adjustable numeric parameter.
LIMITS: dict[str, tuple[float, float]] = {
    "field_deg": (2.0, 45.0),
    "squares": (2, 60),
    "line_count": (1, 25),
    "dot_pitch": (4, 120),
    "spoke_count": (4, 72),
    "rotation_deg": (0, 345),
    "source_px": (3, 600),
    "surround_px": (40, 1000),
    "surround_luminance": (1.0, 255.0),
    "ghost_offset": (0, 120),
    "contrast": (0, 100),
    "veil_contrast": (0, 100),
    "luminance": (0, 255),
    "distance_mm": (200.0, 1000.0),
    "fixation_px": (3, 40),
}

#: Per-family defaults; the values a family falls back to on reset.
FAMILY_DEFAULTS: dict[str, dict[str, object]] = {
    "amsler": {"field_deg": 20.0, "squares": 20, "contrast": 100},
    "lines": {"line_count": 7, "dot_pitch": 20, "contrast": 100},
    "dial": {"spoke_count": 24, "rotation_deg": 0, "contrast": 100},
    "halo": {"source_px": 49, "luminance": 255},
    "veil": {"source_px": 49, "surround_px": 256, "veil_contrast": 20},
    "ghost": {"ghost_offset": 6, "ghost_direction": "right", "contrast": 100},
    "selfcheck": {"reference_patch": False},
}

#: Which parameter each family's ↑/↓ drives.
PRIMARY_FIELD: dict[str, str | None] = {
    "amsler": "squares",
    "lines": "dot_pitch",
    "dial": "spoke_count",
    "halo": "source_px",
    "veil": "surround_px",
    "ghost": "ghost_offset",
    "selfcheck": None,
}

#: Which parameter each family's ←/→ drives ("pitch / rotation / direction").
SECONDARY_FIELD: dict[str, str | None] = {
    "amsler": "field_deg",
    "lines": "line_count",
    "dial": "rotation_deg",
    "halo": None,
    "veil": None,
    "ghost": "ghost_direction",
    "selfcheck": None,
}

#: Step overrides for parameters whose natural step is not one unit.
FIELD_STEPS: dict[str, tuple[float, float]] = {
    "rotation_deg": (15.0, 75.0),
    "field_deg": (1.0, 5.0),
}


#: Every key the viewer understands, with its documented step sizes.
@dataclass(frozen=True)
class Control:
    """One keyboard control: the action it triggers and its step sizes."""

    action: str
    keys: tuple[str, ...]
    step: float = 0.0
    coarse_step: float = 0.0
    label: str = ""

    @property
    def primary_key(self) -> str:
        return self.keys[0]


CONTROLS: tuple[Control, ...] = (
    Control("family_amsler", ("a",), label="Amsler grid"),
    Control("family_lines", ("l",), label="M-chart lines"),
    Control("family_dial", ("d",), label="astigmatism dial"),
    Control("family_halo", ("n",), label="halo / point source"),
    Control("family_veil", ("v",), label="veiling glare"),
    Control("family_ghost", ("e",), label="ghost edge"),
    Control("family_selfcheck", ("c",), label="pixel-path self-check"),
    Control("variant_next", ("Tab",), label="next variant"),
    Control("variant_prev", ("Shift+Tab",), label="previous variant"),
    Control("primary_up", ("Up",), step=1, coarse_step=5, label="primary geometry +"),
    Control("primary_down", ("Down",), step=1, coarse_step=5, label="primary geometry −"),
    Control("secondary_up", ("Right",), step=1, coarse_step=5, label="pitch/rotation/direction +"),
    Control("secondary_down", ("Left",), step=1, coarse_step=5, label="pitch/rotation/direction −"),
    Control("contrast_up", ("+",), step=5, coarse_step=20, label="contrast/luminance +"),
    Control("contrast_down", ("-",), step=5, coarse_step=20, label="contrast/luminance −"),
    Control("distance_up", ("]",), step=50, coarse_step=200, label="viewing distance +"),
    Control("distance_down", ("[",), step=50, coarse_step=200, label="viewing distance −"),
    Control("eye", ("m",), label="eye under test"),
    Control("correction", ("w",), label="correction worn"),
    Control("grade", tuple(str(digit) for digit in range(10)), label="grade 0–9"),
    Control("overlay", ("h",), label="HUD"),
    Control("fixation", ("x",), label="fixation mark"),
    Control("blindspot", ("b",), label="scotoma test"),
    Control("blindspot_inverse", ("i",), label="scotoma test, inverse variant"),
    Control("export", ("s",), label="export PNG + JSON"),
    Control("fullscreen", ("f",), label="fullscreen"),
    Control("reset", ("r",), label="reset parameters"),
    Control("quit", ("q", "Esc"), label="quit"),
)


def _build_key_map(controls: tuple[Control, ...]) -> dict[str, Control]:
    mapping: dict[str, Control] = {}
    for control in controls:
        for key in control.keys:
            if key in mapping:
                raise RuntimeError(
                    f"key {key!r} is mapped twice: "
                    f"{mapping[key].action!r} and {control.action!r}"
                )
            mapping[key] = control
    return mapping


CONTROL_BY_KEY: dict[str, Control] = _build_key_map(CONTROLS)


def lookup(key: str) -> Control | None:
    """The control bound to ``key``, or ``None`` when it is unmapped."""
    return CONTROL_BY_KEY.get(key)


def family_actions() -> dict[str, str]:
    """``family`` name -> the action that selects it."""
    return {
        control.action.split("_", 1)[1]: control.action
        for control in CONTROLS
        if control.action.startswith("family_")
    }


#: Session and display settings that a parameter reset must not touch.
KEEP_ON_RESET: tuple[str, ...] = (
    "family",
    "eye",
    "correction",
    "ambient_note",
    "distance_mm",
    "overlay",
    "fixation_visible",
    "fixation_kind",
    "fixation_px",
)


@dataclass
class Params:
    """Every pattern family's settings plus the session context.

    All families stay in one object so switching family retains the previous
    family's parameters and never moves the fixation anchor.
    """

    family: str = "amsler"
    variant: int = 0
    field_deg: float = 20.0
    squares: int = 20
    line_count: int = 7
    dot_pitch: int = 20
    spoke_count: int = 24
    rotation_deg: int = 0
    source_px: int = 49
    surround_px: int = 256
    surround_luminance: float = 235.0
    ghost_offset: int = 6
    ghost_direction: str = "right"
    contrast: int = 100
    veil_contrast: int = 20
    luminance: int = 255
    distance_mm: float = 400.0
    eye: str = "both"
    correction: bool = True
    overlay: bool = True
    fixation_visible: bool = True
    fixation_kind: str = "ring"
    fixation_px: int = 11
    ambient_note: str = "unspecified"
    reference_patch: bool = False

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"family must be one of {FAMILIES}, got {self.family!r}")
        if self.eye not in EYES:
            raise ValueError(f"eye must be one of {EYES}, got {self.eye!r}")
        if self.fixation_kind not in FIXATION_KINDS:
            raise ValueError(
                f"fixation_kind must be one of {FIXATION_KINDS}, "
                f"got {self.fixation_kind!r}"
            )
        if self.ghost_direction not in GHOST_DIRECTIONS:
            raise ValueError(
                f"ghost_direction must be one of {GHOST_DIRECTIONS}, "
                f"got {self.ghost_direction!r}"
            )

    # -- introspection ------------------------------------------------------
    @property
    def variant_name(self) -> str:
        names = VARIANTS[self.family]
        return names[int(self.variant) % len(names)]

    @property
    def primary_field(self) -> str | None:
        return PRIMARY_FIELD[self.family]

    @property
    def secondary_field(self) -> str | None:
        return SECONDARY_FIELD[self.family]

    @property
    def contrast_field(self) -> str:
        """Which brightness parameter the +/− keys drive for this family."""
        if self.family == "halo":
            return "luminance"
        if self.family == "veil":
            return "veil_contrast"
        return "contrast"

    def item_count(self) -> int:
        """How many separately gradable items the active family shows."""
        if self.family == "lines":
            return max(1, int(self.line_count))
        return 1

    def current_item(self) -> int:
        """Index of the item a grade would apply to."""
        if self.family == "lines":
            return int(self.variant) % max(1, int(self.line_count))
        return 0

    # -- mutation -----------------------------------------------------------
    def reset(self) -> None:
        """Back to the active family's defaults, keeping session context."""
        kept = {name: getattr(self, name) for name in KEEP_ON_RESET}
        defaults = Params()
        for item in fields(Params):
            setattr(self, item.name, getattr(defaults, item.name))
        for name, value in kept.items():
            setattr(self, name, value)
        for name, value in FAMILY_DEFAULTS.get(self.family, {}).items():
            setattr(self, name, value)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        """Short description of the active pattern for the readout."""
        if self.family == "amsler":
            return (
                f"amsler {self.variant_name} {self.squares} squares "
                f"contrast {self.contrast}%"
            )
        if self.family == "lines":
            return (
                f"lines {self.variant_name} n={self.line_count} "
                f"pitch {self.dot_pitch} px contrast {self.contrast}%"
            )
        if self.family == "dial":
            return (
                f"dial {self.spoke_count} spokes rotation {self.rotation_deg}° "
                f"contrast {self.contrast}%"
            )
        if self.family == "halo":
            return f"halo source {self.source_px} px luminance {self.luminance}"
        if self.family == "veil":
            return (
                f"veil surround {self.surround_px} px "
                f"target {self.veil_contrast}% of {self.surround_luminance:.0f}"
            )
        if self.family == "ghost":
            return (
                f"ghost edge {self.ghost_direction} offset {self.ghost_offset} px "
                f"contrast {self.contrast}%"
            )
        return "self-check checkerboard"


@dataclass(frozen=True)
class Grade:
    """One subjective distortion grade bound to the item it judged."""

    family: str
    item_index: int
    value: int
    geometry: dict
    pairing: str
    eye: str
    fixation_visible: bool
    attempts: int = 1

    def key(self) -> tuple[str, int, str]:
        return (self.family, self.item_index, self.eye)

    def to_dict(self) -> dict:
        return {
            "family": self.family,
            "item_index": self.item_index,
            "grade": self.value,
            "geometry": dict(self.geometry),
            "pairing": self.pairing,
            "eye": self.eye,
            "fixation_visible": self.fixation_visible,
            "attempts": self.attempts,
        }


def _clamp(field: str, value: float) -> float:
    low, high = LIMITS[field]
    return min(float(high), max(float(low), value))


def _adjust(params: Params, field: str, sign: int, coarse: bool, control: Control) -> str:
    """Move one numeric parameter and describe the result."""
    step, coarse_step = FIELD_STEPS.get(
        field, (control.step or 1.0, control.coarse_step or 5.0)
    )
    delta = (coarse_step if coarse else step) * sign
    current = getattr(params, field)
    value = float(current) + delta
    if field == "rotation_deg":
        value = value % 360.0
    else:
        value = _clamp(field, value)
    if isinstance(current, int):
        value = int(round(value))
    setattr(params, field, value)
    unit = "°" if field == "rotation_deg" else ""
    return f"{field.replace('_', ' ')} = {value}{unit}"


def _cycle(params: Params, field: str, options: tuple[str, ...], steps: int) -> str:
    index = options.index(getattr(params, field))
    value = options[(index + steps) % len(options)]
    setattr(params, field, value)
    return f"{field.replace('_', ' ')}: {value}"


def apply_control(params: Params, key: str, coarse: bool = False) -> str | None:
    """Apply the control bound to ``key``.

    Returns a status message when the parameter layer handled the key, or
    ``None`` when the session layer owns that action (grading, export, quit,
    overlay and fixation toggles).
    """
    control = lookup(key)
    if control is None:
        return None
    action = control.action

    if action.startswith("family_"):
        params.family = action.split("_", 1)[1]
        params.variant = 0
        return f"pattern: {params.family}"

    if action in ("variant_next", "variant_prev"):
        names = VARIANTS[params.family]
        if len(names) == 1:
            return f"{params.family} has a single variant"
        step = 1 if action == "variant_next" else -1
        params.variant = (int(params.variant) + step) % len(names)
        return f"variant: {params.variant_name}"

    if action in ("primary_up", "primary_down"):
        field = params.primary_field
        sign = 1 if action == "primary_up" else -1
        if field is None:
            return f"{params.family} has no primary parameter"
        message = _adjust(params, field, sign, coarse, control)
        if params.family == "lines":
            params.variant = int(params.variant) % max(1, int(params.line_count))
        return message

    if action in ("secondary_up", "secondary_down"):
        field = params.secondary_field
        sign = 1 if action == "secondary_up" else -1
        if field is None:
            return f"{params.family} has no secondary control"
        if field == "ghost_direction":
            steps = (2 if coarse else 1) * sign
            return _cycle(params, field, GHOST_DIRECTIONS, steps)
        return _adjust(params, field, sign, coarse, control)

    if action in ("contrast_up", "contrast_down"):
        sign = 1 if action == "contrast_up" else -1
        return _adjust(params, params.contrast_field, sign, coarse, control)

    if action in ("distance_up", "distance_down"):
        sign = 1 if action == "distance_up" else -1
        return _adjust(params, "distance_mm", sign, coarse, control)

    if action == "eye":
        return _cycle(params, "eye", EYES, 1)

    if action == "correction":
        params.correction = not params.correction
        return "correction: " + ("worn" if params.correction else "not worn")

    if action == "reset":
        params.reset()
        return "parameters reset"

    return None


