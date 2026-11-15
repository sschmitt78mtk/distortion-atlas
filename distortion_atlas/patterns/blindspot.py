"""Lattice, single-dot and results renderers for the scotoma test.

All three renderers are pure numpy and return a ``uint8`` RGB buffer, like the
rest of this package. The results frame draws its rings from horizontal pixel
spans (:func:`fill_rect`) rather than per-pixel masks, so a full lattice paints
in one pass without a new dependency. Captions use a small built-in 5x7 bitmap
font so the frame is identical on every machine and can be asserted headlessly.
"""

from __future__ import annotations

import math

import numpy as np

from . import BLACK, GREY, RED, WHITE, Colour, blend, blank, fill_rect

#: Lattice dots are drawn at this contrast against black (design D7).
LATTICE_CONTRAST = 12.0
LATTICE_COLOUR: Colour = blend(BLACK, WHITE, LATTICE_CONTRAST / 100.0)
LIT_COLOUR: Colour = WHITE

#: Results-frame ring colours (design D8).
SEEN_COLOUR: Colour = (0, 192, 0)
BLIND_COLOUR: Colour = RED
UNTESTED_COLOUR: Colour = GREY
CAPTION_COLOUR: Colour = (235, 235, 235)

#: Ring geometry, in pixels.
RING_THICKNESS_PX = 3
MIN_RING_RADIUS_PX = 4

#: Caption margin and line spacing, in pixels.
CAPTION_MARGIN_PX = 16
CAPTION_LINE_GAP_PX = 3
MAX_CLUSTER_LINES = 6


def dot_size(settings=None) -> int:
    """Diameter of one lattice dot, in pixels."""
    return max(1, int(getattr(settings, "dot_px", 8)))


def ring_radius(lattice, settings=None) -> int:
    """Ring radius that fits between two lattice positions."""
    if lattice is None:
        return 2 * MIN_RING_RADIUS_PX
    spacing = int(getattr(lattice, "spacing_px", 24))
    return max(MIN_RING_RADIUS_PX, spacing // 2 - dot_size(settings))


def _draw_dot(frame: np.ndarray, x: int, y: int, size: int, colour: Colour) -> None:
    size = max(1, int(size))
    half = size // 2
    fill_rect(frame, int(x) - half, int(y) - half, int(x) - half + size, int(y) - half + size, colour)


def draw_ring(
    frame: np.ndarray,
    cx: int,
    cy: int,
    radius_px: int,
    colour: Colour,
    thickness_px: int = RING_THICKNESS_PX,
) -> np.ndarray:
    """Draw a ring one row at a time using :func:`fill_rect`.

    A whole-frame mask per ring would be unusably slow for a 19x11 lattice, so
    each row is reduced to its outer and inner horizontal spans. Pixels are
    specified inclusively and converted to the helper's half-open rectangles.
    """
    radius = max(1, int(radius_px))
    thickness = max(1, min(int(thickness_px), radius))
    inner = max(0, radius - thickness)
    height = frame.shape[0]
    for dy in range(-radius, radius + 1):
        span = math.isqrt(max(0, radius * radius - dy * dy))
        y = int(cy) + dy
        if y < 0 or y >= height:
            continue
        if inner and abs(dy) <= inner:
            inner_span = math.isqrt(max(0, inner * inner - dy * dy))
            if inner_span < span:
                fill_rect(
                    frame, int(cx) - span, y, int(cx) - inner_span, y + 1, colour
                )
                fill_rect(
                    frame,
                    int(cx) + inner_span + 1,
                    y,
                    int(cx) + span + 1,
                    y + 1,
                    colour,
                )
            continue
        fill_rect(frame, int(cx) - span, y, int(cx) + span + 1, y + 1, colour)
    return frame


#: 5x7 bitmap font; each row is five bits, the most significant bit leftmost.
FONT_5X7: dict[str, tuple[int, ...]] = {
    " ": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000),
    "A": (0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    "B": (0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110),
    "C": (0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110),
    "D": (0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110),
    "E": (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111),
    "F": (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000),
    "G": (0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01110),
    "H": (0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    "I": (0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b11111),
    "J": (0b00111, 0b00010, 0b00010, 0b00010, 0b00010, 0b10010, 0b01100),
    "K": (0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001),
    "L": (0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111),
    "M": (0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001),
    "N": (0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001),
    "O": (0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    "P": (0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000),
    "Q": (0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101),
    "R": (0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001),
    "S": (0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110),
    "T": (0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100),
    "U": (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    "V": (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100),
    "W": (0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b11011, 0b10001),
    "X": (0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001),
    "Y": (0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100),
    "Z": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111),
    "0": (0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110),
    "1": (0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "2": (0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111),
    "3": (0b11110, 0b00001, 0b00001, 0b01110, 0b00001, 0b00001, 0b11110),
    "4": (0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010),
    "5": (0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110),
    "6": (0b00110, 0b01000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110),
    "7": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000),
    "8": (0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110),
    "9": (0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100),
    ".": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00110, 0b00110),
    ",": (0b00000, 0b00000, 0b00000, 0b00000, 0b00110, 0b00110, 0b00100),
    ":": (0b00000, 0b00110, 0b00110, 0b00000, 0b00110, 0b00110, 0b00000),
    "/": (0b00001, 0b00010, 0b00010, 0b00100, 0b01000, 0b01000, 0b10000),
    "-": (0b00000, 0b00000, 0b00000, 0b01110, 0b00000, 0b00000, 0b00000),
    "+": (0b00000, 0b00100, 0b00100, 0b11111, 0b00100, 0b00100, 0b00000),
    "(": (0b00010, 0b00100, 0b01000, 0b01000, 0b01000, 0b00100, 0b00010),
    ")": (0b01000, 0b00100, 0b00010, 0b00010, 0b00010, 0b00100, 0b01000),
    "%": (0b11001, 0b11010, 0b00010, 0b00100, 0b01000, 0b01011, 0b10011),
    "?": (0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b00000, 0b00100),
    "!": (0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00000, 0b00100),
    "=": (0b00000, 0b00000, 0b11111, 0b00000, 0b11111, 0b00000, 0b00000),
}

GLYPH_WIDTH = 5
GLYPH_HEIGHT = 7
GLYPH_GAP = 1


def draw_text(
    frame: np.ndarray,
    x: int,
    y: int,
    text: str,
    colour: Colour = CAPTION_COLOUR,
    scale: int = 1,
) -> np.ndarray:
    """Draw ``text`` with the built-in 5x7 font, clipped to the frame."""
    scale = max(1, int(scale))
    height, width = frame.shape[:2]
    pen_x = int(x)
    pen_y = int(y)
    advance = (GLYPH_WIDTH + GLYPH_GAP) * scale
    max_x = width
    for character in str(text).upper():
        if pen_x + GLYPH_WIDTH * scale > max_x:
            break
        glyph = FONT_5X7.get(character, FONT_5X7[" "])
        for row_index, bits in enumerate(glyph):
            for col in range(GLYPH_WIDTH):
                if not bits & (1 << (GLYPH_WIDTH - 1 - col)):
                    continue
                px = pen_x + col * scale
                py = pen_y + row_index * scale
                if 0 <= py < height and 0 <= px < width:
                    fill_rect(frame, px, py, px + scale, py + scale, colour)
        pen_x += advance
    return frame


def text_width(text: str, scale: int = 1) -> int:
    """Rendered width of ``text`` with the built-in font, in pixels."""
    scale = max(1, int(scale))
    return len(str(text)) * (GLYPH_WIDTH + GLYPH_GAP) * scale


def render_lattice(
    params,
    width: int,
    height: int,
    positions,
    settings=None,
) -> np.ndarray:
    """The faint dot lattice on black; the caller applies the fixation mark."""
    frame = blank(width, height, BLACK)
    size = dot_size(settings)
    for position in positions:
        _draw_dot(frame, position.x_px, position.y_px, size, LATTICE_COLOUR)
    return frame


def render_test_frame(
    params,
    width: int,
    height: int,
    positions,
    lit=None,
    settings=None,
) -> np.ndarray:
    """The lattice with exactly one position at full contrast, all others dim."""
    frame = render_lattice(params, width, height, positions, settings=settings)
    if lit is None:
        return frame
    x = getattr(lit, "x_px", None)
    if x is None:
        x, y = lit
    else:
        y = lit.y_px
    _draw_dot(frame, int(x), int(y), dot_size(settings), LIT_COLOUR)
    return frame


def _caption_lines(summary: dict) -> list[tuple[str, int]]:
    """The results-frame caption, as ``(text, font scale)`` pairs."""
    lines: list[tuple[str, int]] = []
    if not summary.get("interpretable", True):
        lines.append(("NOT INTERPRETABLE - TOO FEW INNER-RING DOTS SEEN", 2))
    lines.append(
        (
            "SEEN {}  BLIND {}  UNTESTED {}".format(
                int(summary.get("seen", 0)),
                int(summary.get("blind", 0)),
                int(summary.get("untested", 0)),
            ),
            2,
        )
    )
    lines.append((f"INNER RING {summary.get('central_seen', '0/0')} SEEN", 2))
    latency = summary.get("median_latency_ms")
    lines.append(
        (
            f"MEDIAN RESPONSE {int(latency)} MS"
            if latency is not None
            else "NO RESPONSES RECORDED",
            2,
        )
    )
    clusters = list(summary.get("clusters", []))
    for index, cluster in enumerate(clusters[:MAX_CLUSTER_LINES], start=1):
        centre = cluster.get("centre_deg", [0.0, 0.0])
        extent = cluster.get("extent_deg", [0.0, 0.0])
        lines.append(
            (
                "CLUSTER {}: {} DOTS CENTRE {:+.1f},{:+.1f} DEG "
                "EXTENT {:.1f}X{:.1f} DEG".format(
                    index,
                    int(cluster.get("dots", 0)),
                    float(centre[0]),
                    float(centre[1]),
                    float(extent[0]),
                    float(extent[1]),
                ),
                1,
            )
        )
    if len(clusters) > MAX_CLUSTER_LINES:
        lines.append((f"AND {len(clusters) - MAX_CLUSTER_LINES} MORE CLUSTERS", 1))
    lines.append(("PHOTOSENSITIVITY: RANDOM FLASHING DOTS - STOP IF UNCOMFORTABLE", 1))
    lines.append(("NOT A MEDICAL DIAGNOSIS - OBSERVATION AID ONLY", 1))
    return lines


def render_results_frame(
    params,
    width: int,
    height: int,
    positions,
    summary: dict,
    lattice=None,
    settings=None,
) -> np.ndarray:
    """Rings for every position plus the counts, clusters and caveat caption.

    Seen positions are green rings, blind positions red rings with a filled
    centre, and everything the run never reached a grey ring (design D8).
    """
    frame = blank(width, height, BLACK)
    radius = ring_radius(lattice, settings)
    blind_dot = max(2, dot_size(settings) // 2)
    for position in positions:
        verdict = position.verdict
        if verdict == "seen":
            colour = SEEN_COLOUR
        elif verdict == "blind":
            colour = BLIND_COLOUR
        else:
            colour = UNTESTED_COLOUR
        draw_ring(frame, position.x_px, position.y_px, radius, colour)
        if verdict == "blind":
            _draw_dot(frame, position.x_px, position.y_px, blind_dot, BLIND_COLOUR)

    pen_y = CAPTION_MARGIN_PX
    for text, scale in _caption_lines(summary):
        draw_text(
            frame,
            CAPTION_MARGIN_PX,
            pen_y,
            text,
            CAPTION_COLOUR,
            scale=scale,
        )
        pen_y += (GLYPH_HEIGHT + CAPTION_LINE_GAP_PX) * scale
    return frame