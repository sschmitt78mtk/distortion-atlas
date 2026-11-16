"""Central fixation mark (hollow ring or dot) that anchors the gaze.

The mark is drawn about the pattern anchor with whole pixels and an odd size, so
it is symmetric about that anchor and, in the default hollow-ring form, leaves
the centre pixel itself untouched — the observer still sees the pattern exactly
where the distortion matters most.
"""

from __future__ import annotations

import numpy as np

from .patterns import RED, Colour, anchor, coords

DEFAULT_KIND = "ring"
DEFAULT_SIZE_PX = 11
DEFAULT_COLOUR: Colour = RED

#: Thickness of the hollow ring, in pixels.
RING_THICKNESS_PX = 2


def snap_size(size_px: int) -> int:
    """Largest odd size not above ``size_px``; odd keeps the mark symmetric."""
    value = max(3, int(size_px))
    return value if value % 2 else max(3, value - 1)


def size_for_dot(dot_size_px: int, gap_px: int = 2) -> int:
    """Smallest odd ring size whose inner edge clears a dot, leaving ``gap_px``.

    The inverse scotoma field draws a black dot on the fixation anchor. At the
    default ring size the mark would sit on top of that dot and be hard to find
    on the bright field, so the field raises its size until a background gap
    separates the red circle from the dot.
    """
    half = max(1, int(dot_size_px)) // 2
    gap = max(0, int(gap_px))
    return snap_size(2 * (half + gap + RING_THICKNESS_PX) + 1)


def fixation_mask(
    width: int,
    height: int,
    cx: int,
    cy: int,
    kind: str = DEFAULT_KIND,
    size_px: int = DEFAULT_SIZE_PX,
) -> np.ndarray:
    """Boolean mask of the fixation mark, centred on ``(cx, cy)``."""
    size = snap_size(size_px)
    radius = size // 2
    xx, yy = coords(width, height)
    distance_sq = (xx - cx) ** 2 + (yy - cy) ** 2

    if kind == "dot":
        return distance_sq <= radius * radius + 1e-6
    if kind == "ring":
        inner = max(0, radius - RING_THICKNESS_PX)
        return (distance_sq <= radius * radius + 1e-6) & (distance_sq > inner * inner)
    raise ValueError(f"unknown fixation kind {kind!r}")


def draw_fixation(
    buffer: np.ndarray,
    cx: int,
    cy: int,
    kind: str = DEFAULT_KIND,
    size_px: int = DEFAULT_SIZE_PX,
    colour: Colour = DEFAULT_COLOUR,
) -> np.ndarray:
    """Return a copy of ``buffer`` with the fixation mark painted on it."""
    frame = buffer.copy()
    height, width = frame.shape[:2]
    frame[fixation_mask(width, height, cx, cy, kind, size_px)] = colour
    return frame


def apply_fixation(
    buffer: np.ndarray, params, min_size_px: int = 0
) -> np.ndarray:
    """Paint the mark the parameters ask for, or leave the frame untouched.

    ``min_size_px`` raises the ring size without changing the recorded
    parameters: the inverse scotoma field uses it so the red circle clears its
    black centre dot instead of being buried in it. Filled marks are never
    enlarged, because they are already visible against any field.
    """
    if not getattr(params, "fixation_visible", True):
        return buffer.copy()
    height, width = buffer.shape[:2]
    cx, cy = anchor(width, height)
    kind = getattr(params, "fixation_kind", DEFAULT_KIND)
    size_px = int(getattr(params, "fixation_px", DEFAULT_SIZE_PX))
    if min_size_px and kind == "ring":
        size_px = max(size_px, int(min_size_px))
    return draw_fixation(
        buffer,
        cx,
        cy,
        kind=kind,
        size_px=size_px,
        colour=DEFAULT_COLOUR,
    )


def covers_centre(size_px: int = DEFAULT_SIZE_PX, kind: str = DEFAULT_KIND) -> bool:
    """True when the mark would hide the centre pixel of the pattern."""
    size = snap_size(size_px)
    mask = fixation_mask(size + 2, size + 2, (size + 2) // 2, (size + 2) // 2, kind, size)
    return bool(mask[(size + 2) // 2, (size + 2) // 2])
