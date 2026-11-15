"""Halo, veiling-glare and ghost-edge targets.

These are the continuous renderers of design D2: luminance is a float and is
spread over the panel with a 4×4 ordered dither, because a hard 8-bit step would
band and banding fakes the halo the observer is trying to see. Sizes are still
whole pixels — only luminance is sub-code-value.
"""

from __future__ import annotations

import numpy as np

from . import (
    BLACK,
    WHITE,
    Colour,
    anchor,
    blank,
    blend,
    disc_diameter_px,
    disc_mask,
    fill_dithered,
    fill_rect,
)
#: Width of the ghost copy of the edge, in pixels.
GHOST_LINE_PX = 2

#: Directions the ghost can be displaced in.
GHOST_DIRECTIONS: tuple[str, ...] = ("right", "left", "down", "up")

#: Default luminance of the veiling surround, in code values.
DEFAULT_SURROUND_LUMINANCE = 235.0


def source_diameter_px(params) -> int:
    """Source diameter as actually drawn, so the readout cannot disagree."""
    return disc_diameter_px(params.source_px)


def halo_value(params) -> float:
    """Requested source luminance in code values."""
    return float(min(255.0, max(0.0, params.luminance)))


def render_halo(params, width: int, height: int) -> np.ndarray:
    """A point source of ``source_px`` on a black field."""
    frame = blank(width, height, BLACK)
    cx, cy = anchor(width, height)
    mask = disc_mask(width, height, cx, cy, params.source_px)
    fill_dithered(frame, halo_value(params), mask)
    return frame


def surround_side_px(params) -> int:
    """Even side of the bright veiling square, in pixels."""
    return max(2, (int(params.surround_px) // 2) * 2)


def veil_surround_value(params) -> float:
    return float(getattr(params, "surround_luminance", DEFAULT_SURROUND_LUMINANCE))


def veil_target_value(params) -> float:
    """Central target luminance: ``veil_contrast`` percent of the surround."""
    percent = float(
        getattr(params, "veil_contrast", getattr(params, "contrast", 100.0))
    )
    return veil_surround_value(params) * percent / 100.0


def veil_target_diameter_px(params) -> int:
    return disc_diameter_px(params.source_px)


def render_veil(params, width: int, height: int) -> np.ndarray:
    """A bright surround with a dim central target (veiling glare)."""
    frame = blank(width, height, BLACK)
    cx, cy = anchor(width, height)
    side = surround_side_px(params)
    x0, y0 = cx - side // 2, cy - side // 2

    surround_mask = np.zeros((height, width), dtype=bool)
    surround_mask[y0 : y0 + side, x0 : x0 + side] = True
    fill_dithered(frame, veil_surround_value(params), surround_mask)

    target_mask = disc_mask(width, height, cx, cy, params.source_px)
    fill_dithered(frame, veil_target_value(params), target_mask)
    return frame


def ghost_edge_position(params, width: int, height: int) -> tuple[int, int, str]:
    """Coordinates of the primary edge and of the ghost band.

    Returns ``(edge, ghost_start, axis)`` where ``axis`` is ``"x"`` or ``"y"``.
    The ghost band starts exactly ``ghost_offset`` pixels away from the primary
    edge in ``params.ghost_direction``.
    """
    cx, cy = anchor(width, height)
    direction = str(getattr(params, "ghost_direction", "right"))
    offset = max(0, int(params.ghost_offset))
    if direction == "right":
        return cx, cx + offset, "x"
    if direction == "left":
        return cx, cx - offset - GHOST_LINE_PX, "x"
    if direction == "down":
        return cy, cy + offset, "y"
    if direction == "up":
        return cy, cy - offset - GHOST_LINE_PX, "y"
    raise ValueError(f"unknown ghost direction {direction!r}")


def render_ghost(params, width: int, height: int) -> np.ndarray:
    """A high-contrast edge plus one displaced copy of it (monocular ghosting)."""
    frame = blank(width, height, BLACK)
    bright: Colour = blend(BLACK, WHITE, float(params.contrast) / 100.0)
    cx, cy = anchor(width, height)
    direction = str(getattr(params, "ghost_direction", "right"))
    offset = max(0, int(params.ghost_offset))

    if direction in ("right", "left"):
        fill_rect(frame, 0, 0, width, height, BLACK)
        if direction == "right":
            fill_rect(frame, cx, 0, width, height, bright)
        else:
            fill_rect(frame, 0, 0, cx, height, bright)
    elif direction in ("down", "up"):
        fill_rect(frame, 0, 0, width, height, BLACK)
        if direction == "down":
            fill_rect(frame, 0, cy, width, height, bright)
        else:
            fill_rect(frame, 0, 0, width, cy, bright)
    else:
        raise ValueError(f"unknown ghost direction {direction!r}")

    if offset > 0:
        _, ghost_start, axis = ghost_edge_position(params, width, height)
        if axis == "x":
            fill_rect(frame, ghost_start, 0, ghost_start + GHOST_LINE_PX, height, BLACK)
        else:
            fill_rect(frame, 0, ghost_start, width, ghost_start + GHOST_LINE_PX, BLACK)
    return frame


def measured_diameter(mask: np.ndarray, row: int | None = None) -> int:
    """Number of set pixels across the widest row (or a chosen row) of a mask."""
    if not mask.any():
        return 0
    if row is None:
        row = int(np.argmax(mask.sum(axis=1)))
    columns = np.flatnonzero(mask[row])
    if columns.size == 0:
        return 0
    return int(columns[-1] - columns[0] + 1)
