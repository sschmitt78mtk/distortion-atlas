"""Persistence of the pixels-per-millimetre calibration.

The stored value lives in ``$XDG_CONFIG_HOME/distortion-atlas/config.json``
(stdlib ``json`` only, no new dependency). A value stored under the pre-rename
``visiontest`` directory is still read, and the next save writes the new path.
Without a usable value the pitch is derived from the reported panel size and
labelled ``panel_derived`` everywhere, because an uncalibrated pitch gives
plausible but wrong angular sizes.

A measurement that differs from the panel-derived pitch by more than 25 % is
refused unless it is explicitly confirmed — that is the guard from the
``visual-angle-geometry`` spec.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .geometry import Scale

CONFIG_DIR_NAME = "distortion-atlas"
LEGACY_CONFIG_DIR_NAME = "visiontest"
CONFIG_FILE_NAME = "config.json"

#: Anything further than this from the panel-derived pitch needs confirmation.
PLAUSIBILITY_TOLERANCE = 0.25

#: Fallback panel description used when nothing better is known.
DEFAULT_WIDTH_PX = 1920
DEFAULT_HEIGHT_PX = 1080
DEFAULT_PANEL_MM = (340.0, 190.0)

DEFAULT_DISTANCE_MM = 400.0
MIN_DISTANCE_MM = 200.0
MAX_DISTANCE_MM = 1000.0


class ImplausibleCalibration(ValueError):
    """The entered length implies a pitch far from the panel-derived one."""

    def __init__(
        self,
        px_per_mm: float,
        reference: float,
        tolerance: float = PLAUSIBILITY_TOLERANCE,
    ) -> None:
        self.px_per_mm = px_per_mm
        self.reference = reference
        self.tolerance = tolerance
        super().__init__(
            f"{px_per_mm:.2f} px/mm differs from the panel-derived "
            f"{reference:.2f} px/mm by more than {tolerance * 100:.0f} % — "
            "confirm to store it anyway"
        )


@dataclass(frozen=True)
class Calibration:
    """A stored ruler measurement."""

    px_per_mm: float
    source: str = "calibrated"
    stored_at: str | None = None

    def scale(self, distance_mm: float = DEFAULT_DISTANCE_MM) -> Scale:
        return Scale(
            px_per_mm=self.px_per_mm, distance_mm=distance_mm, source=self.source
        )

    def as_dict(self) -> dict:
        return {
            "px_per_mm": self.px_per_mm,
            "source": self.source,
            "stored_at": self.stored_at,
        }


def _config_root() -> Path:
    """``$XDG_CONFIG_HOME`` or ``~/.config``."""
    base = os.environ.get("XDG_CONFIG_HOME")
    return Path(base) if base else Path.home() / ".config"


def config_path() -> Path:
    """Location of the stored calibration, honouring ``XDG_CONFIG_HOME``."""
    return _config_root() / CONFIG_DIR_NAME / CONFIG_FILE_NAME


def legacy_config_path() -> Path:
    """Pre-rename calibration location; read for migration, never written."""
    return _config_root() / LEGACY_CONFIG_DIR_NAME / CONFIG_FILE_NAME


def panel_derived_px_per_mm(
    width_px: int = DEFAULT_WIDTH_PX,
    height_px: int = DEFAULT_HEIGHT_PX,
    panel_mm: tuple[float, float] = DEFAULT_PANEL_MM,
) -> float:
    """Pitch implied by the panel's reported pixel count and physical size."""
    width_mm, height_mm = panel_mm
    ratios = []
    if width_mm > 0 and width_px > 0:
        ratios.append(width_px / width_mm)
    if height_mm > 0 and height_px > 0:
        ratios.append(height_px / height_mm)
    if not ratios:
        raise ValueError("need a positive pixel count and panel size")
    return sum(ratios) / len(ratios)


def panel_derived_scale(
    distance_mm: float = DEFAULT_DISTANCE_MM,
    width_px: int = DEFAULT_WIDTH_PX,
    height_px: int = DEFAULT_HEIGHT_PX,
    panel_mm: tuple[float, float] = DEFAULT_PANEL_MM,
) -> Scale:
    """The uncalibrated fallback: usable, but labelled as derived."""
    return Scale(
        px_per_mm=panel_derived_px_per_mm(width_px, height_px, panel_mm),
        distance_mm=distance_mm,
        source="panel_derived",
    )


def is_plausible(
    px_per_mm: float,
    reference: float,
    tolerance: float = PLAUSIBILITY_TOLERANCE,
) -> bool:
    if reference <= 0:
        return True
    return abs(px_per_mm - reference) / reference <= tolerance


def _read_calibration(target: Path) -> Calibration | None:
    """Parse one calibration file, or ``None`` when it is missing or unusable."""
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        px_per_mm = float(data["px_per_mm"])
    except (OSError, ValueError, TypeError, KeyError):
        return None
    if not px_per_mm > 0:
        return None
    return Calibration(
        px_per_mm=px_per_mm,
        source=str(data.get("source") or "calibrated"),
        stored_at=data.get("stored_at"),
    )


def load_calibration(path: Path | None = None) -> Calibration | None:
    """Read the stored calibration, falling back to the pre-rename location."""
    if path is not None:
        return _read_calibration(Path(path))
    return _read_calibration(config_path()) or _read_calibration(legacy_config_path())


def save_calibration(
    px_per_mm: float,
    reference: float | None = None,
    confirm: bool = False,
    path: Path | None = None,
) -> Calibration:
    """Store a ruler measurement, refusing implausible values without consent."""
    value = float(px_per_mm)
    if not value > 0:
        raise ValueError(f"px_per_mm must be positive, got {px_per_mm!r}")
    if reference is not None and not confirm and not is_plausible(value, reference):
        raise ImplausibleCalibration(value, float(reference))

    calibration = Calibration(
        px_per_mm=value,
        stored_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    target = Path(path) if path is not None else config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(calibration.as_dict(), indent=2) + "\n", encoding="utf-8"
    )
    return calibration


def default_scale(
    distance_mm: float = DEFAULT_DISTANCE_MM,
    width_px: int = DEFAULT_WIDTH_PX,
    height_px: int = DEFAULT_HEIGHT_PX,
    panel_mm: tuple[float, float] = DEFAULT_PANEL_MM,
    path: Path | None = None,
) -> Scale:
    """Calibrated scale when one is stored, otherwise the panel-derived one."""
    stored = load_calibration(path)
    if stored is not None:
        return stored.scale(distance_mm)
    return panel_derived_scale(distance_mm, width_px, height_px, panel_mm)
