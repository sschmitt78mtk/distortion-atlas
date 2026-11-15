"""Pure numpy pattern renderers.

Every renderer takes a parameter object and a buffer size and returns a
``uint8`` array of shape ``(height, width, 3)``. Nothing in this package may
import a GUI toolkit: that is what makes the atlas testable headlessly and what
guarantees that the exported PNG is the displayed image.
This module holds the helpers the families share: colours, the centre anchor,
cached coordinate grids, whole-pixel cut positions, drawing primitives and the
ordered-dither field used for low-contrast luminances.
"""

from __future__ import annotations

import math

import numpy as np

Colour = tuple[int, int, int]

BLACK: Colour = (0, 0, 0)
WHITE: Colour = (255, 255, 255)
RED: Colour = (200, 0, 0)
BLUE: Colour = (0, 60, 200)
YELLOW: Colour = (255, 220, 0)
GREY: Colour = (128, 128, 128)

#: 4×4 ordered-dither matrix (Bayer), normalised to [0, 1).
BAYER4 = np.array(
    [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]],
    dtype=np.float32,
) / 16.0

_coord_cache: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}


def blank(width: int, height: int, colour: Colour = BLACK) -> np.ndarray:
    """An all-``colour`` RGB buffer."""
    if width < 1 or height < 1:
        raise ValueError(f"buffer must be at least 1×1 px, got {width}×{height}")
    frame = np.empty((int(height), int(width), 3), dtype=np.uint8)
    frame[:, :] = colour
    return frame


def anchor(width: int, height: int) -> tuple[int, int]:
    """The buffer's centre pixel — the fixation anchor for every pattern."""
    return int(width) // 2, int(height) // 2


def coords(width: int, height: int) -> tuple[np.ndarray, np.ndarray]:
    """Cached ``float32`` x/y index grids for a buffer size (design D5)."""
    key = (int(width), int(height))
    cached = _coord_cache.get(key)
    if cached is None:
        yy, xx = np.mgrid[0 : key[1], 0 : key[0]]
        cached = (xx.astype(np.float32), yy.astype(np.float32))
        if len(_coord_cache) > 8:
            _coord_cache.clear()
        _coord_cache[key] = cached
    return cached


def divide_positions(x0: int, extent: int, count: int) -> tuple[int, ...]:
    """Whole-pixel cut positions for ``count`` cells spanning exactly ``extent``.

    The outer boundary is bit-identical for every ``count`` and the cuts stay
    symmetric about the middle of the field, so changing the square count
    cannot move the reference field. Where ``extent`` is not a multiple of
    ``count`` the cells differ by one pixel rather than the pitch turning
    fractional.
    """
    extent = int(extent)
    count = int(count)
    if count < 1:
        raise ValueError(f"count must be at least 1, got {count}")
    if extent < count:
        raise ValueError(f"extent {extent} px cannot hold {count} cells")
    return tuple(
        int(x0) + (i * extent + count // 2) // count for i in range(count + 1)
    )


def blend(background: Colour, foreground: Colour, fraction: float) -> Colour:
    """Mix ``fraction`` (0..1) of ``foreground`` into ``background``."""
    f = min(1.0, max(0.0, float(fraction)))
    return tuple(int(round(b + (fg - b) * f)) for b, fg in zip(background, foreground))


def fill_rect(
    frame: np.ndarray, x0: int, y0: int, x1: int, y1: int, colour: Colour
) -> np.ndarray:
    """Fill the half-open rectangle ``[x0, x1) × [y0, y1)``, clipped."""
    height, width = frame.shape[:2]
    xs, xe = max(0, int(x0)), min(width, int(x1))
    ys, ye = max(0, int(y0)), min(height, int(y1))
    if xs >= xe or ys >= ye:
        return frame
    frame[ys:ye, xs:xe] = colour
    return frame


def draw_hline(
    frame: np.ndarray, y: int, x0: int, x1: int, colour: Colour, width_px: int = 1
) -> np.ndarray:
    return fill_rect(frame, x0, y, x1, y + max(1, width_px), colour)


def draw_vline(
    frame: np.ndarray, x: int, y0: int, y1: int, colour: Colour, width_px: int = 1
) -> np.ndarray:
    return fill_rect(frame, x, y0, x + max(1, width_px), y1, colour)


def disc_diameter_px(requested: int) -> int:
    """Largest odd diameter not exceeding ``requested``.

    A disc centred on a pixel can only have an odd diameter without shifting
    its centre; renderers and readouts both call this so they cannot disagree.
    """
    value = max(1, int(requested))
    return value if value % 2 else max(1, value - 1)


def disc_mask(
    width: int, height: int, cx: int, cy: int, diameter_px: int
) -> np.ndarray:
    """Boolean mask of a pixel-centred disc of ``diameter_px`` pixels."""
    diameter = disc_diameter_px(diameter_px)
    radius = (diameter - 1) / 2.0
    xx, yy = coords(width, height)
    return (xx - cx) ** 2 + (yy - cy) ** 2 <= radius * radius + 1e-6


def draw_disc(
    frame: np.ndarray, cx: int, cy: int, diameter_px: int, colour: Colour
) -> np.ndarray:
    height, width = frame.shape[:2]
    frame[disc_mask(width, height, cx, cy, diameter_px)] = colour
    return frame


def spoke_mask(
    width: int,
    height: int,
    cx: int,
    cy: int,
    angle_deg: float,
    length_px: float,
    width_px: float = 2.0,
) -> np.ndarray:
    """Mask of a radial spoke drawn from the centre at ``angle_deg``.

    The angle is measured counter-clockwise from the +x axis in the observer's
    view, so "up" on screen is +90°; the mask itself is computed from the
    cached index grids, which keeps the spoke length and width independent of
    the rotation.
    """
    theta = math.radians(float(angle_deg))
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    xx, yy = coords(width, height)
    dx = xx - cx
    dy = cy - yy  # screen y grows downwards; flip so +90° points up
    along = dx * cos_t + dy * sin_t
    across = -dx * sin_t + dy * cos_t
    half_width = max(0.5, float(width_px) / 2.0)
    return (
        (along >= 0.0)
        & (along <= float(length_px))
        & (across >= -half_width)
        & (across < half_width)
    )


def draw_spoke(
    frame: np.ndarray,
    cx: int,
    cy: int,
    angle_deg: float,
    length_px: float,
    colour: Colour,
    width_px: float = 2.0,
) -> np.ndarray:
    height, width = frame.shape[:2]
    frame[spoke_mask(width, height, cx, cy, angle_deg, length_px, width_px)] = colour
    return frame


def dither_thresholds(width: int, height: int) -> np.ndarray:
    """Pixel-stable ordered-dither thresholds tiled over the buffer."""
    tiles_y = int(math.ceil(height / 4.0))
    tiles_x = int(math.ceil(width / 4.0))
    tiled = np.tile(BAYER4, (tiles_y, tiles_x))[:height, :width]
    return (tiled + (0.5 / 16.0)).astype(np.float32)


def dithered_values(width: int, height: int, value: float) -> np.ndarray:
    """8-bit values whose local mean is ``value``, via a 4×4 ordered dither.

    An 8-bit panel cannot show a contrast step finer than one code value; the
    dither lets the veil/glare family request fractional luminances whose
    average still lands on the requested value.
    """
    clamped = min(255.0, max(0.0, float(value)))
    base = math.floor(clamped)
    fraction = clamped - base
    return np.where(
        dither_thresholds(width, height) < fraction, base + 1, base
    ).astype(np.uint8)


def fill_dithered(
    frame: np.ndarray, value: float, mask: np.ndarray | None = None
) -> np.ndarray:
    """Fill ``frame`` (or ``mask`` inside it) with a dithered luminance."""
    height, width = frame.shape[:2]
    values = dithered_values(width, height, value)
    if mask is None:
        frame[:, :, 0] = values
        frame[:, :, 1] = values
        frame[:, :, 2] = values
    else:
        for channel in range(3):
            frame[:, :, channel][mask] = values[mask]
    return frame


