"""Amsler grid variants and M-chart dotted straightness lines.

Both families are bilevel: every stroke lands on whole pixels and nothing is
anti-aliased, because a 1.5-px-wide "straight" line is itself a distortion
(design D2). Contrast is changed by mixing the stroke colour toward the
background, never by moving or thinning the stroke.
"""

from __future__ import annotations

import numpy as np

from ..geometry import DEFAULT_MARGIN_PX
from . import (
    BLACK,
    BLUE,
    RED,
    WHITE,
    YELLOW,
    Colour,
    anchor,
    blend,
    blank,
    divide_positions,
    fill_rect,
)

#: Amsler colour pairings: name -> (background, stroke).
PAIRINGS: dict[str, tuple[Colour, Colour]] = {
    "black_on_white": (WHITE, BLACK),
    "white_on_black": (BLACK, WHITE),
    "red_on_black": (BLACK, RED),
    "blue_on_yellow": (YELLOW, BLUE),
}

PAIRING_NAMES: tuple[str, ...] = tuple(PAIRINGS)

#: M-chart orientations.
LINE_ORIENTATIONS: tuple[str, ...] = ("horizontal", "vertical", "diagonal")

#: Side of one M-chart dot, in pixels.
DOT_PX = 3


def pairing_name(variant: int) -> str:
    return PAIRING_NAMES[int(variant) % len(PAIRING_NAMES)]


def pairing_colours(variant: int, contrast: float = 100.0) -> tuple[Colour, Colour]:
    """Background plus the stroke colour at ``contrast`` percent."""
    background, stroke = PAIRINGS[pairing_name(variant)]
    return background, blend(background, stroke, float(contrast) / 100.0)


def field_extent(
    width: int, height: int, extent_px: int | None = None, margin_px: int = DEFAULT_MARGIN_PX
) -> int:
    """Even field side in pixels; even keeps the field symmetric about centre."""
    if extent_px is None:
        available = min(int(width), int(height)) - 2 * int(margin_px)
    else:
        available = int(extent_px)
    if available < 2:
        raise ValueError(f"field extent {available} px is too small")
    return (available // 2) * 2


def grid_cuts(cx: int, extent_px: int, squares: int) -> tuple[int, ...]:
    """``squares + 1`` whole-pixel grid lines spanning ``extent_px`` about ``cx``."""
    extent = (int(extent_px) // 2) * 2
    x0 = int(cx) - extent // 2
    return divide_positions(x0, extent, int(squares))


def line_positions(cx: int, extent_px: int, count: int) -> tuple[int, ...]:
    """``count`` line positions, whole-pixel and centred on ``cx``."""
    count = int(count)
    if count <= 1:
        return (int(cx),)
    extent = (int(extent_px) // 2) * 2
    x0 = int(cx) - extent // 2
    return divide_positions(x0, extent, count - 1)


def render_amsler(
    params,
    width: int,
    height: int,
    extent_px: int | None = None,
) -> np.ndarray:
    """An Amsler grid: ``params.squares`` cells, anchored on the buffer centre."""
    background, stroke = pairing_colours(params.variant, params.contrast)
    frame = blank(width, height, background)
    extent = field_extent(width, height, extent_px)
    cx, cy = anchor(width, height)
    cuts = grid_cuts(cx, extent, params.squares)
    left, right = cuts[0], cuts[-1]
    top, bottom = cy - extent // 2, cy + extent // 2

    for x in cuts:
        fill_rect(frame, x, top, x + 1, bottom, stroke)
    for y in cuts:
        fill_rect(frame, left, y, right, y + 1, stroke)
    return frame


def _draw_dot(frame: np.ndarray, x: int, y: int, colour: Colour, size: int = DOT_PX) -> None:
    half = size // 2
    fill_rect(frame, x - half, y - half, x - half + size, y - half + size, colour)


def _draw_dash(
    frame: np.ndarray,
    x: int,
    y: int,
    steps: int,
    dx: int,
    dy: int,
    colour: Colour,
) -> None:
    for step in range(max(0, steps)):
        _draw_dot(frame, x + dx * step, y + dy * step, colour, size=1)


def grading_marker_offset() -> int:
    """Rows/columns between a line and its grading-reference dash."""
    return DOT_PX + 1


def render_lines(
    params,
    width: int,
    height: int,
    extent_px: int | None = None,
) -> np.ndarray:
    """M-chart dotted straightness lines with a per-line grading reference.

    The dot pitch is exact in whole pixels along the line, the line set is
    centred on the fixation anchor, and the dash at the start of each line
    grows by ``DOT_PX`` per index so the observer can name the line being
    graded.
    """
    background, stroke = pairing_colours(0, params.contrast)
    frame = blank(width, height, background)
    extent = field_extent(width, height, extent_px)
    cx, cy = anchor(width, height)
    pitch = max(1, int(params.dot_pitch))
    count = max(1, int(params.line_count))

    orientation = LINE_ORIENTATIONS[int(params.variant) % len(LINE_ORIENTATIONS)]
    horizontal = orientation in ("horizontal", "diagonal")
    positions = line_positions(cy if horizontal else cx, extent, count)
    half = extent // 2
    span = half // pitch + 1

    for index, line in enumerate(positions):
        for k in range(-span, span + 1):
            if orientation == "horizontal":
                x, y = cx + k * pitch, line
            elif orientation == "vertical":
                x, y = line, cy + k * pitch
            else:  # diagonal: dots step (+1, -1) so the pitch stays exact
                x, y = cx + k * pitch, line - k * pitch
            if not (0 <= x < width and 0 <= y < height):
                continue
            if abs(x - cx) > half or abs(y - cy) > half:
                continue
            _draw_dot(frame, x, y, stroke)

        # Grading reference: the dash length encodes the line index (1-based).
        # It sits just clear of the line so it cannot merge with a dot.
        dash_steps = DOT_PX * (index + 1)
        if orientation == "horizontal":
            _draw_dash(
                frame, cx - half, line + grading_marker_offset(), dash_steps, 1, 0, stroke
            )
        elif orientation == "vertical":
            _draw_dash(
                frame, line + grading_marker_offset(), cy - half, dash_steps, 0, 1, stroke
            )
        else:
            _draw_dash(frame, cx - half, cy + half, dash_steps, 1, -1, stroke)
    return frame
