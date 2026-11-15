"""Layout and hit-testing for the pointer-revealed key bar.

No GUI toolkit is imported here (design D3): the bar is described as plain
rectangles, captions and key hints, so the layout can be verified headless and
the Qt backend only paints what this module returns. One button exists per key
string in :data:`distortion_atlas.params.CONTROL_BY_KEY`, except the quit control
whose ``q`` and ``Esc`` share one button.

The layout is deliberately arithmetic only - equal-width slots per row, no font
measurement - so it produces identical numbers on every machine and font.
"""

from __future__ import annotations

from dataclasses import dataclass

from .params import CONTROLS, Control

#: Left and right margin around the bar, in pixels.
MARGIN_PX = 12
#: Gap between two buttons in a row, in pixels.
GAP_PX = 6
#: Padding above the first and below the last row, in pixels.
PADDING_PX = 6
#: Row height limits, in pixels; the height follows the screen size.
MIN_ROW_HEIGHT_PX = 30
MAX_ROW_HEIGHT_PX = 44
#: Below this slot width the key hint is dropped (task 1.3).
MIN_HINT_SLOT_PX = 64
#: Approximate glyph width used for model-side elision, in pixels.
GLYPH_PX = 7
#: Room reserved inside a slot before its caption has to be elided, in pixels.
SLOT_PADDING_PX = 8

#: The four semantic rows, in on-screen order (design D3).
ROW_ACTIONS: tuple[tuple[str, ...], ...] = (
    (
        "family_amsler",
        "family_lines",
        "family_dial",
        "family_halo",
        "family_veil",
        "family_ghost",
        "family_selfcheck",
    ),
    (
        "variant_prev",
        "variant_next",
        "secondary_down",
        "primary_up",
        "primary_down",
        "secondary_up",
        "contrast_down",
        "contrast_up",
        "distance_down",
        "distance_up",
    ),
    ("grade", "eye", "correction"),
    ("overlay", "fixation", "export", "fullscreen", "reset", "quit"),
)

#: Short captions keyed by :attr:`distortion_atlas.params.Control.action`.
CAPTIONS: dict[str, str] = {
    "family_amsler": "amsler",
    "family_lines": "lines",
    "family_dial": "dial",
    "family_halo": "halo",
    "family_veil": "veil",
    "family_ghost": "ghost",
    "family_selfcheck": "self-check",
    "variant_next": "next variant",
    "variant_prev": "prev variant",
    "primary_up": "geometry +",
    "primary_down": "geometry −",
    "secondary_up": "pitch +",
    "secondary_down": "pitch −",
    "contrast_up": "contrast +",
    "contrast_down": "contrast −",
    "distance_up": "distance +",
    "distance_down": "distance −",
    "grade": "grade",
    "eye": "eye",
    "correction": "correction",
    "overlay": "HUD",
    "fixation": "fixation",
    "export": "export",
    "fullscreen": "fullscreen",
    "reset": "reset",
    "quit": "quit",
}

#: The ten step actions a held button may repeat (design D7).
STEP_ACTIONS: frozenset[str] = frozenset(
    {
        "variant_next",
        "variant_prev",
        "primary_up",
        "primary_down",
        "secondary_up",
        "secondary_down",
        "contrast_up",
        "contrast_down",
        "distance_up",
        "distance_down",
    }
)


@dataclass(frozen=True)
class BarButton:
    """One button: its control, the key it dispatches and where it sits."""

    action: str
    key: str
    caption: str
    hint: str
    rect: tuple[int, int, int, int]
    active: bool = False
    repeatable: bool = False

    def contains(self, x: float, y: float) -> bool:
        """Whether the point lies inside this button's rectangle."""
        left, top, width, height = self.rect
        return left <= x < left + width and top <= y < top + height


@dataclass(frozen=True)
class KeyBar:
    """The assembled bar: its own rectangle plus every button, row by row."""

    width: int
    height: int
    rect: tuple[int, int, int, int]
    buttons: tuple[BarButton, ...]

    def hit_test(self, x: float, y: float) -> BarButton | None:
        """The button under the point, or ``None`` when nothing was hit."""
        for button in self.buttons:
            if button.contains(x, y):
                return button
        return None


def row_height(height: int) -> int:
    """Row height for a screen ``height`` px, clamped to 30-44 px."""
    return min(MAX_ROW_HEIGHT_PX, max(MIN_ROW_HEIGHT_PX, int(height) // 24))


def elide(caption: str, slot: int) -> str:
    """Shorten ``caption`` so it fits ``slot`` px of model-side text."""
    limit = max(1, (int(slot) - SLOT_PADDING_PX) // GLYPH_PX)
    if len(caption) <= limit:
        return caption
    if limit == 1:
        return caption[:1]
    return caption[: limit - 1] + "…"


def _caption(action: str, key: str, state: dict) -> str:
    """The caption for one button, carrying its live value where it has one."""
    if action == "grade":
        return key
    base = CAPTIONS[action]
    if action == "eye":
        return f"{base}: {state.get('eye', 'both')}"
    if action == "correction":
        worn = bool(state.get("correction", True))
        return f"{base}: {'worn' if worn else 'not worn'}"
    return base


def _hint(control: Control, key: str) -> str:
    """The key hint; multi-key controls read ``q / Esc`` (task 1.2)."""
    if len(control.keys) > 1 and control.action != "grade":
        return " / ".join(control.keys)
    return key


def _is_active(action: str, key: str, state: dict) -> bool:
    """Whether the button reflects the state snapshot (design D9)."""
    if action.startswith("family_"):
        return action == f"family_{state.get('family')}"
    if action == "grade":
        grade = state.get("grade")
        return grade is not None and int(grade) == int(key)
    if action == "overlay":
        return bool(state.get("overlay", False))
    if action == "fixation":
        return bool(state.get("fixation_visible", False))
    return False


def _row_buttons(actions: tuple[str, ...], controls: dict[str, Control]) -> list:
    """Expand one row's actions into ``(control, key)`` pairs."""
    pairs: list[tuple[Control, str]] = []
    for action in actions:
        control = controls[action]
        if action == "grade":
            pairs.extend((control, key) for key in control.keys)
        else:
            pairs.append((control, control.keys[0]))
    return pairs


def build(width: int, height: int, state: dict | None = None) -> KeyBar:
    """Lay the bar out for a ``width`` x ``height`` widget.

    ``state`` is the snapshot from :meth:`distortion_atlas.ui.Session.key_bar_state`;
    missing keys fall back to a neutral state.
    """
    state = dict(state or {})
    width = int(width)
    height = int(height)
    controls = {control.action: control for control in CONTROLS}

    row = row_height(height)
    bar_height = len(ROW_ACTIONS) * row + 2 * PADDING_PX
    bar_rect = (0, max(0, height - bar_height), width, bar_height)
    top = bar_rect[1] + PADDING_PX

    buttons: list[BarButton] = []
    for row_index, actions in enumerate(ROW_ACTIONS):
        pairs = _row_buttons(actions, controls)
        count = max(1, len(pairs))
        slot = max(1, (width - 2 * MARGIN_PX - (count - 1) * GAP_PX) // count)
        row_top = top + row_index * row
        for index, (control, key) in enumerate(pairs):
            left = MARGIN_PX + index * (slot + GAP_PX)
            caption = elide(_caption(control.action, key, state), slot)
            hint = _hint(control, key) if slot >= MIN_HINT_SLOT_PX else ""
            buttons.append(
                BarButton(
                    action=control.action,
                    key=key,
                    caption=caption,
                    hint=hint,
                    rect=(left, row_top, slot, row),
                    active=_is_active(control.action, key, state),
                    repeatable=control.action in STEP_ACTIONS,
                )
            )
    return KeyBar(width=width, height=height, rect=bar_rect, buttons=tuple(buttons))


def hit_test(bar: KeyBar | None, x: float, y: float) -> BarButton | None:
    """The button at ``(x, y)``, or ``None`` when the point hits no button."""
    if bar is None:
        return None
    return bar.hit_test(x, y)

