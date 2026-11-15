"""Astigmatism clock dial with crossed line pairs.

The dial is a set of radial spokes at regular angular steps. A crossed target
of two diameters at the same orientations sits in the middle so the observer can
compare the sharpest/darkest direction against a known reference. Spoke length
and width are derived from the buffer, never from the rotation, so turning the
dial cannot change them.
"""

from __future__ import annotations

import math

import numpy as np

from ..geometry import DEFAULT_MARGIN_PX
from . import BLACK, WHITE, Colour, anchor, blend, blank, draw_spoke

#: Stroke width of a spoke and of the crossed target, in pixels.
SPOKE_WIDTH_PX = 2

#: Crossed target length as a fraction of the spoke radius.
CROSSED_RATIO = 0.35


def dial_angles(count: int, rotation_deg: float = 0.0) -> tuple[float, ...]:
    """Angles of the ``count`` spokes, rotated by ``rotation_deg``."""
    count = int(count)
    if count < 1:
        raise ValueError(f"spoke count must be at least 1, got {count}")
    step = 360.0 / count
    rotation = float(rotation_deg) % 360.0
    return tuple((rotation + index * step) % 360.0 for index in range(count))


def spoke_radius(width: int, height: int, margin_px: int = DEFAULT_MARGIN_PX) -> int:
    """Spoke length in pixels for a buffer; independent of the rotation."""
    return max(1, (min(int(width), int(height)) // 2) - int(margin_px))


def crossed_angles(count: int, rotation_deg: float = 0.0) -> tuple[float, ...]:
    """Orientations of the crossed target — exactly the spoke orientations."""
    return dial_angles(count, rotation_deg)


def draw_crossed_target(
    frame: np.ndarray,
    cx: int,
    cy: int,
    radius: int,
    count: int,
    rotation_deg: float,
    colour: Colour,
) -> np.ndarray:
    """Two opposite radii per orientation, forming a small crossed target."""
    length = max(1, int(radius * CROSSED_RATIO))
    for angle in crossed_angles(count, rotation_deg):
        for direction in (angle, angle + 180.0):
            draw_spoke(
                frame,
                cx,
                cy,
                direction,
                length,
                colour,
                width_px=SPOKE_WIDTH_PX,
            )
    return frame


def render_dial(
    params,
    width: int,
    height: int,
    radius_px: int | None = None,
) -> np.ndarray:
    """The clock dial: spokes at ``params.spoke_count`` plus the crossed target."""
    frame = blank(width, height, BLACK)
    stroke = blend(BLACK, WHITE, float(params.contrast) / 100.0)
    cx, cy = anchor(width, height)
    radius = int(radius_px) if radius_px is not None else spoke_radius(width, height)
    radius = max(1, radius)
    angles = dial_angles(params.spoke_count, params.rotation_deg)

    for angle in angles:
        draw_spoke(frame, cx, cy, angle, radius, stroke, width_px=SPOKE_WIDTH_PX)
    draw_crossed_target(
        frame, cx, cy, radius, params.spoke_count, params.rotation_deg, stroke
    )
    return frame


def angle_step_deg(count: int) -> float:
    """Angular step between spokes, in degrees."""
    return 360.0 / max(1, int(count))


def spoke_endpoint(cx: int, cy: int, angle_deg: float, radius: int) -> tuple[int, int]:
    """Whole-pixel endpoint of a spoke (screen y grows downwards)."""
    theta = math.radians(float(angle_deg))
    return (
        int(round(cx + radius * math.cos(theta))),
        int(round(cy - radius * math.sin(theta))),
    )
