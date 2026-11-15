"""One-pixel checkerboard self-check and flat-field helper.

The checkerboard is the pixel-path integrity pattern: at 1:1 it averages to a
uniform mid-grey, and any compositor scaling or filtering turns it into a visible
moiré instead. The flat field is the reference for the dithered luminance of the
glare family.
"""

from __future__ import annotations

import numpy as np

from . import BLACK, WHITE, anchor, blank, coords, disc_mask, fill_dithered


def checkerboard(width: int, height: int, cell_px: int = 1) -> np.ndarray:
    """A checkerboard whose cells are exactly ``cell_px`` pixels wide."""
    cell = max(1, int(cell_px))
    xx, yy = coords(width, height)
    parity = ((np.floor(xx).astype(np.int32) // cell) + (np.floor(yy).astype(np.int32) // cell)) % 2 == 0
    frame = np.empty((int(height), int(width), 3), dtype=np.uint8)
    frame[parity] = WHITE
    frame[~parity] = BLACK
    return frame


def render_self_check(params, width: int, height: int) -> np.ndarray:
    """The 1-px checkerboard, plus an optional flat patch for comparison."""
    frame = checkerboard(width, height, cell_px=1)
    if getattr(params, "reference_patch", False):
        cx, cy = anchor(width, height)
        frame[disc_mask(width, height, cx, cy, params.source_px)] = 128
    return frame


def render_flat(params, width: int, height: int) -> np.ndarray:
    """A flat field at ``params.luminance`` code values, expanded by dither."""
    frame = blank(width, height, BLACK)
    fill_dithered(frame, float(params.luminance))
    return frame


def block_average(frame: np.ndarray, block: int = 2) -> np.ndarray:
    """Mean over non-overlapping ``block``×``block`` tiles (drop-in diagnostic).

    A 1-px checkerboard gives a constant mid-grey here; a scaled or filtered
    copy does not, which is exactly the check the observer performs by eye.
    """
    block = max(1, int(block))
    height = (frame.shape[0] // block) * block
    width = (frame.shape[1] // block) * block
    cropped = frame[:height, :width].astype(np.float32)
    reshaped = cropped.reshape(height // block, block, width // block, block, 3)
    return reshaped.mean(axis=(1, 3))


def mean_code_value(frame: np.ndarray) -> float:
    """Mean of the frame across all three channels, in code values."""
    return float(np.asarray(frame, dtype=np.float32).mean())
