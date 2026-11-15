"""Visual-angle geometry: pixels, millimetres, degrees and arcmin.

Everything the tool reports about size comes from :class:`Scale`, which turns a
pixel count into a physical length and a viewing angle. One object means a
distance change is a single mutation and every readout follows (design D4).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

#: Where the pixels-per-millimetre value came from.
SOURCES = ("calibrated", "panel_derived")

#: Border kept free around a fitted field, in pixels.
DEFAULT_MARGIN_PX = 8

_EPS = 1e-9


@dataclass(frozen=True)
class Scale:
    """Pixels, millimetres and viewing angle in one place.

    A pixel subtends ``atan(mm_per_px / distance_mm)`` radians, so the angle
    shrinks with distance while the pixel count stays untouched — which is
    exactly what "distance change rescales the report only" asks for.
    """

    px_per_mm: float
    distance_mm: float
    source: str = "panel_derived"

    def __post_init__(self) -> None:
        if not self.px_per_mm > 0:
            raise ValueError(f"px_per_mm must be positive, got {self.px_per_mm!r}")
        if not self.distance_mm > 0:
            raise ValueError(f"distance_mm must be positive, got {self.distance_mm!r}")
        if self.source not in SOURCES:
            raise ValueError(f"source must be one of {SOURCES}, got {self.source!r}")

    # -- pixel <-> millimetre -------------------------------------------------
    @property
    def mm_per_px(self) -> float:
        return 1.0 / self.px_per_mm

    def mm_for_px(self, px: float) -> float:
        return px * self.mm_per_px

    def px_for_mm(self, mm: float) -> float:
        return mm * self.px_per_mm

    # -- pixel <-> angle ------------------------------------------------------
    @property
    def deg_per_px(self) -> float:
        return math.degrees(math.atan(self.mm_per_px / self.distance_mm))

    @property
    def arcmin_per_px(self) -> float:
        return self.deg_per_px * 60.0

    @property
    def px_per_deg(self) -> float:
        return 1.0 / self.deg_per_px

    def degrees_for_px(self, px: float) -> float:
        return px * self.deg_per_px

    def arcmin_for_px(self, px: float) -> float:
        return px * self.arcmin_per_px

    def px_for_degrees(self, degrees: float) -> float:
        return degrees * self.px_per_deg

    def field_for_px(self, px: float) -> float:
        """Field of view subtended by ``px`` pixels, in degrees."""
        return self.degrees_for_px(px)

    # -- derived scales -------------------------------------------------------
    def with_distance(self, distance_mm: float) -> "Scale":
        return replace(self, distance_mm=distance_mm)

    def with_calibration(self, px_per_mm: float) -> "Scale":
        """Same session, but the pitch now comes from a ruler measurement."""
        return replace(self, px_per_mm=px_per_mm, source="calibrated")

    def describe_px(self, px: float) -> str:
        """Human readout for one dimension, e.g. ``39 px = 6.94 mm = 1.00°``."""
        return (
            f"{px:.0f} px = {self.mm_for_px(px):.2f} mm = "
            f"{self.degrees_for_px(px):.2f}° ({self.arcmin_for_px(px):.1f}′)"
        )


def snap_pitch(value: float) -> int:
    """Snap a pitch in pixels down to a whole pixel, never below one.

    A 39.3 px pitch becomes 39 px, because a line drawn at a fractional
    position is itself the distortion the observer is looking for.
    """
    return max(1, int(math.floor(value + _EPS)))


@dataclass(frozen=True)
class FieldFit:
    """A requested field of view resolved against a finite buffer."""

    scale: Scale
    requested_field_deg: float
    requested_squares: int
    squares: int
    pitch_px: int
    pixels: int
    field_deg: float
    margin_px: int
    #: True when the request did not fit and the field had to be reduced.
    fitted: bool
    #: True when the fractional pitch had to be snapped down to a whole pixel.
    snapped: bool

    @property
    def pitch_mm(self) -> float:
        return self.scale.mm_for_px(self.pitch_px)

    @property
    def field_mm(self) -> float:
        return self.scale.mm_for_px(self.pixels)

    @property
    def reduction_deg(self) -> float:
        return self.requested_field_deg - self.field_deg

    def summary(self) -> str:
        """One line describing what is actually drawn."""
        text = (
            f"{self.squares} squares @ {self.pitch_px} px = "
            f"{self.field_deg:.2f}° ({self.field_mm:.1f} mm)"
        )
        if self.fitted:
            text += f" — requested {self.requested_field_deg:.2f}° does not fit"
        elif self.snapped:
            text += f" — snapped from {self.requested_field_deg:.2f}°"
        return text

    def as_dict(self) -> dict:
        return {
            "requested_field_deg": round(self.requested_field_deg, 4),
            "field_deg": round(self.field_deg, 4),
            "field_mm": round(self.field_mm, 3),
            "squares": self.squares,
            "pitch_px": self.pitch_px,
            "pitch_mm": round(self.pitch_mm, 4),
            "drawn_px": self.pixels,
            "margin_px": self.margin_px,
            "fitted": self.fitted,
            "snapped": self.snapped,
        }


def max_field_deg(
    scale: Scale,
    squares: int,
    width: int,
    height: int,
    margin_px: int = DEFAULT_MARGIN_PX,
) -> float:
    """Largest field a buffer can show for ``squares`` cells at whole pixels."""
    available = _available_px(width, height, margin_px)
    pitch = max(1, available // max(1, squares))
    return scale.field_for_px(pitch * squares)


def fit_field(
    scale: Scale,
    field_deg: float,
    squares: int,
    width: int,
    height: int,
    margin_px: int = DEFAULT_MARGIN_PX,
) -> FieldFit:
    """Snap a requested field to a whole-pixel pitch that fits the buffer.

    The pitch is derived from the requested field and then clamped so the drawn
    grid stays inside the buffer with ``margin_px`` to spare. The reported field
    is always recomputed from the integer pitch that will actually be drawn, so
    the readout can never claim a field the panel is not showing.
    """
    if squares < 1:
        raise ValueError(f"squares must be at least 1, got {squares}")
    if field_deg <= 0:
        raise ValueError(f"field_deg must be positive, got {field_deg}")

    available = _available_px(width, height, margin_px)
    requested_px = scale.px_for_degrees(field_deg)
    requested_pitch = requested_px / squares

    max_pitch = max(1, available // squares)
    pitch = max(1, min(snap_pitch(requested_pitch), max_pitch))
    pixels = pitch * squares

    return FieldFit(
        scale=scale,
        requested_field_deg=field_deg,
        requested_squares=squares,
        squares=squares,
        pitch_px=pitch,
        pixels=pixels,
        field_deg=scale.field_for_px(pixels),
        margin_px=margin_px,
        fitted=snap_pitch(requested_pitch) > max_pitch,
        snapped=abs(requested_pitch - round(requested_pitch)) > 1e-6,
    )


def _available_px(width: int, height: int, margin_px: int) -> int:
    available = min(int(width), int(height)) - 2 * int(margin_px)
    if available < 1:
        raise ValueError(
            f"buffer {width}×{height} px is too small for a {margin_px} px margin"
        )
    return available
