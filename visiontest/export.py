"""PNG image plus JSON session record export.

The PNG is produced from the same buffer the presenter shows, minus the overlay,
so "the exported image matches the display" holds by construction. The JSON
record carries everything a second person needs to read the session without the
application: pattern parameters, scale and its provenance, session context,
every grade, the panel identity and the non-diagnostic statement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image

TOOL_NAME = "visiontest"
TOOL_VERSION = "0.1.0"

DISCLAIMER = (
    "visiontest supports observation of visual distortion. It is not a medical "
    "device and its output is not a diagnosis."
)
NON_DIAGNOSTIC = "Not a medical device — this record is an observation aid only."
PHOTOSENSITIVITY_WARNING = (
    "All current patterns are static. Any future flashing content would carry a "
    "photosensitivity risk."
)

#: EDID of the target panel; read for the panel identity in the record.
EDID_PATH = "/sys/class/drm/card1-eDP-1/edid"

#: Default export location (git-ignored in this repository).
DEFAULT_EXPORT_DIR = Path("exports")

UNKNOWN_PANEL: dict = {
    "name": "unknown",
    "manufacturer": "unknown",
    "resolution": "unknown",
    "size_mm": None,
    "source": "unknown",
}

#: Code-value difference below which an 8-bit panel cannot separate the step.
DISPLAY_LIMITED_CODES = 3


@dataclass(frozen=True)
class ExportResult:
    """Outcome of one export request."""

    ok: bool
    png_path: Path | None = None
    json_path: Path | None = None
    error: str = ""
    attempted_dir: Path | None = None

    def message(self) -> str:
        if self.ok:
            return f"exported {self.png_path.name} and {self.json_path.name}"
        return f"export failed: {self.error}"


def _decode_manufacturer(raw: bytes) -> str:
    value = (raw[0] << 8) | raw[1]
    letters = [(value >> shift) & 0x1F for shift in (10, 5, 0)]
    if any(code < 1 or code > 26 for code in letters):
        return ""
    return "".join(chr(code + 64) for code in letters)


def _decode_descriptor_name(block: bytes) -> str:
    text = block[5:18].decode("ascii", "ignore").split("\n")[0]
    return text.strip("\x00 ").strip()


def parse_edid(data: bytes) -> dict:
    """Extract name, manufacturer, resolution and size from EDID bytes."""
    if len(data) < 128 or data[:8] != b"\x00\xff\xff\xff\xff\xff\xff\x00":
        return dict(UNKNOWN_PANEL)

    hactive = data[56] | ((data[58] & 0xF0) << 4)
    vactive = data[59] | ((data[61] & 0xF0) << 4)
    width_mm = data[12] | ((data[13] & 0xF0) << 4)
    height_mm = data[14] | ((data[15] & 0xF0) << 4)

    name = ""
    unspecified_text = ""
    for offset in range(54, 126, 18):
        block = data[offset : offset + 18]
        if len(block) < 18:
            break
        if block[0] == 0x00 and block[1] == 0x00:
            if block[3] == 0xFC:
                name = _decode_descriptor_name(block)
            elif block[3] == 0xFE:
                unspecified_text = _decode_descriptor_name(block)
        if name:
            break
    name = name or unspecified_text

    resolution = f"{hactive}x{vactive}" if hactive and vactive else "unknown"
    return {
        "name": name or "unknown",
        "manufacturer": _decode_manufacturer(data[8:10]) or "unknown",
        "resolution": resolution,
        "size_mm": [width_mm, height_mm] if width_mm and height_mm else None,
        "source": "edid",
    }


def panel_identity(path: str | Path = EDID_PATH) -> dict:
    """Read the panel identity, degrading to ``unknown`` when unreadable."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return dict(UNKNOWN_PANEL)
    return parse_edid(data)


def contrast_flags(params) -> dict:
    """Report whether the requested contrast survives 8-bit quantisation."""
    family = str(getattr(params, "family", ""))
    if family in ("amsler", "lines", "dial", "ghost"):
        percent = int(params.contrast)
    elif family == "veil":
        percent = int(params.veil_contrast)
    else:
        return {
            "family": family,
            "applies": False,
            "note": "this family is judged by luminance, not by contrast",
            "display_limited": False,
        }
    code_difference = int(round(255 * percent / 100.0))
    limited = code_difference <= DISPLAY_LIMITED_CODES
    return {
        "family": family,
        "applies": True,
        "requested_percent": percent,
        "code_difference": code_difference,
        "display_limited": limited,
        "note": (
            "8-bit panel; a step of 3 code values or fewer cannot be shown "
            "reliably"
            if limited
            else "step is representable in 8 bits per channel"
        ),
    }


def _scale_block(scale) -> dict:
    return {
        "px_per_mm": round(float(scale.px_per_mm), 6),
        "source": scale.source,
        "distance_mm": float(scale.distance_mm),
        "deg_per_px": round(float(scale.deg_per_px), 6),
        "arcmin_per_px": round(float(scale.arcmin_per_px), 6),
    }


def build_record(
    session, panel: dict | None = None, timestamp: datetime | None = None
) -> dict:
    """The JSON payload for one export, built from the live session."""
    params = session.params
    check = getattr(session, "self_check", None)
    fit = getattr(session, "last_fit", None)

    return {
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "generated_at": (timestamp or datetime.now()).isoformat(timespec="seconds"),
        "disclaimer": DISCLAIMER,
        "non_diagnostic": NON_DIAGNOSTIC,
        "photosensitivity_warning": PHOTOSENSITIVITY_WARNING,
        "panel": panel if panel is not None else panel_identity(),
        "display": {
            "buffer_px": [int(session.width), int(session.height)],
            "surface_px": (
                list(check.surface_size) if check and check.surface_size else None
            ),
            "scale_factor": check.scale_factor if check else None,
            "overlay_exported": False,
        },
        "pixel_path": {
            "ok": bool(check.ok) if check else None,
            "message": check.message if check else "",
            "session_reliable": bool(getattr(session, "reliable", True)),
        },
        "scale": _scale_block(session.scale),
        "pattern": {
            "family": params.family,
            "variant": params.variant_name,
            "parameters": params.to_dict(),
            "field": fit.as_dict() if fit is not None else None,
        },
        "context": {
            "eye": params.eye,
            "correction": "worn" if params.correction else "not worn",
            "ambient_note": params.ambient_note,
            "distance_mm": float(params.distance_mm),
            "fixation": {
                "visible": bool(params.fixation_visible),
                "kind": params.fixation_kind,
                "size_px": int(params.fixation_px),
            },
        },
        "contrast_limits": contrast_flags(params),
        "grades": [grade.to_dict() for grade in session.ordered_grades()],
        "overlay_text": session.overlay_text(),
    }


def export_session(
    session,
    directory: str | Path | None = None,
    timestamp: datetime | None = None,
    panel: dict | None = None,
) -> ExportResult:
    """Write ``<tool>-<stamp>.png`` and ``.json``; never mutate the session."""
    target_dir = Path(
        directory
        if directory is not None
        else getattr(session, "export_dir", None) or DEFAULT_EXPORT_DIR
    )
    buffer = getattr(session, "buffer", None)
    if buffer is None:
        return ExportResult(
            ok=False,
            error="no pattern has been displayed yet",
            attempted_dir=target_dir,
        )

    moment = timestamp or datetime.now()
    stem = f"{TOOL_NAME}-{moment.strftime('%Y%m%d-%H%M%S')}"
    png_path = target_dir / f"{stem}.png"
    json_path = target_dir / f"{stem}.json"

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        Image.fromarray(buffer).save(png_path)
        record = build_record(session, panel=panel, timestamp=moment)
        json_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    except OSError as error:
        if png_path.exists():
            try:
                png_path.unlink()
            except OSError:
                pass
        return ExportResult(
            ok=False,
            error=f"{error.strerror or error} — tried {target_dir}",
            attempted_dir=target_dir,
        )
    return ExportResult(ok=True, png_path=png_path, json_path=json_path)

