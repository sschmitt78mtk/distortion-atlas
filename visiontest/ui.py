"""Session state, key dispatch and the presentable frame.

Nothing here imports a GUI toolkit. A :class:`Session` owns the parameters, the
scale, the grades and the buffers; a backend (see :mod:`visiontest.backends.qt`)
only hands buffers to the screen and forwards key strings. That split is what
lets the viewer be tested under ``QT_QPA_PLATFORM=offscreen`` and keeps the
exported buffer free of the readout overlay by construction (design D6).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from . import calibration, export
from .fixation import apply_fixation
from .geometry import FieldFit, Scale, fit_field
from .params import Grade, Params, apply_control, lookup
from .patterns import dials, glare, grids, targets

#: Height of the readout strip, in pixels.
OVERLAY_HEIGHT_PX = 24

#: How strongly the strip covers the pattern underneath it.
OVERLAY_ALPHA = 0.65
OVERLAY_BACKGROUND = (16, 16, 16)
OVERLAY_TEXT_COLOUR = (235, 235, 235)

#: Shown before any pattern is displayed, and repeated in every record.
STARTUP_NOTICE = (
    "visiontest supports observation of visual distortion. It is not a medical "
    "device and its output is not a diagnosis. All current patterns are static; "
    "any future flashing content would carry a photosensitivity risk."
)

MONOCULAR_REMINDER = "cover the other eye"


@dataclass(frozen=True)
class SelfCheck:
    """Result of the pixel-path integrity check."""

    ok: bool
    buffer_size: tuple[int, int]
    surface_size: tuple[int, int] | None = None
    scale_factor: float | None = None
    message: str = ""


@dataclass(frozen=True)
class ActionResult:
    """What the session did with one key press."""

    changed: bool
    message: str = ""
    action: str = ""


def check_pixel_path(
    buffer_size: tuple[int, int],
    surface_size: tuple[int, int] | None = None,
    scale_factor: float | None = None,
) -> SelfCheck:
    """Compare the presented surface with the rendered buffer.

    A mismatch, or a device pixel ratio other than 1, means the compositor is
    resampling the image; every distortion reading after that is unreliable, so
    the mismatch is named and carried into the record.
    """
    buffer_size = (int(buffer_size[0]), int(buffer_size[1]))
    if surface_size is None:
        return SelfCheck(
            ok=True,
            buffer_size=buffer_size,
            scale_factor=scale_factor,
            message="no presented surface to compare (headless render)",
        )
    surface_size = (int(surface_size[0]), int(surface_size[1]))
    if surface_size != buffer_size:
        return SelfCheck(
            ok=False,
            buffer_size=buffer_size,
            surface_size=surface_size,
            scale_factor=scale_factor,
            message=(
                f"surface {surface_size[0]}×{surface_size[1]} does not match the "
                f"buffer {buffer_size[0]}×{buffer_size[1]}: the pixel path is "
                "scaled or cropped, so measurements are unreliable"
            ),
        )
    if scale_factor is not None and abs(float(scale_factor) - 1.0) > 1e-6:
        return SelfCheck(
            ok=False,
            buffer_size=buffer_size,
            surface_size=surface_size,
            scale_factor=scale_factor,
            message=(
                f"device pixel ratio {float(scale_factor):g} is not 1: display "
                "scaling is active, so measurements are unreliable"
            ),
        )
    return SelfCheck(
        ok=True,
        buffer_size=buffer_size,
        surface_size=surface_size,
        scale_factor=scale_factor,
        message=(
            f"1:1 pixel path: surface {surface_size[0]}×{surface_size[1]} equals "
            f"buffer {buffer_size[0]}×{buffer_size[1]} at scale factor "
            f"{1.0 if scale_factor is None else float(scale_factor):g}"
        ),
    )


class Session:
    """One viewing session: parameters, scale, grades, buffers."""

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        scale: Scale | None = None,
        params: Params | None = None,
        export_dir: str | Path | None = None,
        ambient_note: str | None = None,
    ) -> None:
        self.width = int(width)
        self.height = int(height)
        self.params = params if params is not None else Params()
        if ambient_note is not None:
            self.params.ambient_note = ambient_note
        self._base_scale = (
            scale
            if scale is not None
            else calibration.default_scale(distance_mm=self.params.distance_mm)
        )
        self.grades: dict[tuple[str, int, str], Grade] = {}
        self._grade_order: list[tuple[str, int, str]] = []
        self.last_fit: FieldFit | None = None
        self.shown_family: str | None = None
        self.buffer: np.ndarray | None = None
        self.self_check = check_pixel_path((self.width, self.height))
        self.reliable = True
        self.export_dir = (
            Path(export_dir) if export_dir is not None else export.DEFAULT_EXPORT_DIR
        )
        self.message = ""
        self.running = True
        self.fullscreen = True
        self.notice = STARTUP_NOTICE
        if self.params.eye in ("left", "right"):
            self.message = MONOCULAR_REMINDER
        elif self._base_scale.source != "calibrated":
            self.message = self.calibration_prompt()

    # -- scale --------------------------------------------------------------
    @property
    def ambient_note(self) -> str:
        """Session context: the ambient condition note."""
        return self.params.ambient_note

    @ambient_note.setter
    def ambient_note(self, value: str) -> None:
        self.params.ambient_note = str(value)

    @property
    def scale(self) -> Scale:
        """The single source of truth: base pitch plus the live distance."""
        return self._base_scale.with_distance(self.params.distance_mm)

    def set_calibration(
        self, px_per_mm: float, confirm: bool = False
    ) -> calibration.Calibration:
        """Adopt and store a ruler measurement."""
        stored = calibration.save_calibration(
            px_per_mm,
            reference=self._base_scale.px_per_mm,
            confirm=confirm,
        )
        self._base_scale = self._base_scale.with_calibration(stored.px_per_mm)
        self.message = f"calibrated: {stored.px_per_mm:.3f} px/mm"
        return stored

    def calibration_prompt(self) -> str:
        """Warn while the pitch is still the panel-derived guess."""
        if self._base_scale.source == "calibrated":
            return ""
        return "UNCALIBRATED pitch — calibrate against a ruler before grading"

    def update_pixel_path(
        self,
        surface_size: tuple[int, int] | None,
        scale_factor: float | None = None,
    ) -> SelfCheck:
        """Re-run the integrity check against the presented surface."""
        self.self_check = check_pixel_path(
            (self.width, self.height), surface_size, scale_factor
        )
        self.reliable = self.self_check.ok
        if not self.reliable:
            self.message = self.self_check.message
        return self.self_check

    # -- rendering ----------------------------------------------------------
    def field_fit(self) -> FieldFit:
        """Fit the requested Amsler field to this buffer, in whole pixels."""
        fit = fit_field(
            self.scale,
            float(self.params.field_deg),
            int(self.params.squares),
            self.width,
            self.height,
        )
        extent = grids.field_extent(self.width, self.height, fit.pixels)
        if extent != fit.pixels:
            fit = replace(fit, pixels=extent, field_deg=self.scale.field_for_px(extent))
        self.last_fit = fit
        return fit

    def render(self) -> np.ndarray:
        """Render the active pattern; the result is the exportable buffer."""
        params = self.params
        family = params.family
        width, height = self.width, self.height

        if family == "amsler":
            fit = self.field_fit()
            frame = grids.render_amsler(params, width, height, extent_px=fit.pixels)
        elif family == "lines":
            self.last_fit = None
            frame = grids.render_lines(params, width, height)
        elif family == "dial":
            self.last_fit = None
            frame = dials.render_dial(params, width, height)
        elif family == "halo":
            self.last_fit = None
            frame = glare.render_halo(params, width, height)
        elif family == "veil":
            self.last_fit = None
            frame = glare.render_veil(params, width, height)
        elif family == "ghost":
            self.last_fit = None
            frame = glare.render_ghost(params, width, height)
        elif family == "selfcheck":
            self.last_fit = None
            frame = targets.render_self_check(params, width, height)
        else:  # pragma: no cover - Params validates the family
            raise ValueError(f"unknown pattern family {family!r}")

        frame = apply_fixation(frame, params)
        self.buffer = frame
        self.shown_family = family
        return frame

    def presented(self) -> np.ndarray:
        """The frame the observer sees: pattern plus optional readout strip."""
        frame = self.render() if self.buffer is None else self.buffer
        if not self.params.overlay:
            return frame
        presented = frame.copy()
        rows = min(OVERLAY_HEIGHT_PX, self.height)
        strip = presented[0:rows].astype(np.float32)
        background = np.array(OVERLAY_BACKGROUND, dtype=np.float32)
        mixed = strip * (1.0 - OVERLAY_ALPHA) + background * OVERLAY_ALPHA
        presented[0:rows] = mixed.astype(np.uint8)
        return presented

    def overlay_text(self) -> str:
        """The single status line; painted by the backend, never exported."""
        params = self.params
        scale = self.scale
        eye = params.eye if params.eye != "both" else "both eyes"
        reminder = (
            f" — {MONOCULAR_REMINDER}" if params.eye in ("left", "right") else ""
        )
        grade = self.grades.get((params.family, params.current_item(), params.eye))
        grade_text = f"grade {grade.value}" if grade else "no grade"
        if grade is not None and grade.attempts > 1:
            grade_text += f" (×{grade.attempts})"
        source = "calibrated" if scale.source == "calibrated" else "UNCALIBRATED"
        field = ""
        if self.last_fit is not None:
            field = f" | {self.last_fit.field_deg:.1f}° {self.last_fit.pitch_px} px"
        fixation = (
            f"{params.fixation_kind} {params.fixation_px} px"
            if params.fixation_visible
            else "hidden"
        )
        parts = [
            f"{params.summary()}{field}",
            f"{params.distance_mm:.0f} mm {scale.arcmin_per_px:.2f}′/px ({source})",
            f"eye {eye}{reminder}",
            f"item {params.current_item() + 1}/{params.item_count()}",
            grade_text,
            f"fixation {fixation}",
        ]
        if self.message:
            parts.append(self.message)
        if not self.reliable:
            parts.append("PIXEL PATH UNRELIABLE")
        parts.append("not a medical device")
        return " | ".join(parts)

    # -- key dispatch -------------------------------------------------------
    def handle_key(self, key: str, coarse: bool = False) -> ActionResult:
        """Apply one key press and re-render immediately."""
        control = lookup(key)
        if control is None:
            self.message = f"key {key!r} is not mapped"
            return ActionResult(False, self.message)
        action = control.action

        if action == "quit":
            self.running = False
            return ActionResult(True, "quit", "quit")
        if action == "fullscreen":
            self.fullscreen = not self.fullscreen
            self.message = "windowed" if not self.fullscreen else "fullscreen"
            return ActionResult(True, self.message, "toggle_fullscreen")
        if action == "overlay":
            self.params.overlay = not self.params.overlay
            self.message = "HUD on" if self.params.overlay else "HUD hidden"
            return ActionResult(True, self.message)
        if action == "fixation":
            self.params.fixation_visible = not self.params.fixation_visible
            self.message = (
                "fixation mark on"
                if self.params.fixation_visible
                else "fixation mark hidden — recorded with any grade"
            )
            self.render()
            return ActionResult(True, self.message)
        if action == "export":
            return self._handle_export()
        if action == "grade":
            return self.grade(int(key))

        message = apply_control(self.params, key, coarse)
        if message is None:
            self.message = f"{action.replace('_', ' ')} is not available here"
            return ActionResult(False, self.message)
        self.message = message
        self.render()
        return ActionResult(True, message)

    # -- grading ------------------------------------------------------------
    def geometry_snapshot(self) -> dict:
        """The geometry and colour pairing in force right now."""
        params = self.params
        snapshot = {
            "family": params.family,
            "variant": params.variant_name,
            "item_count": params.item_count(),
            "distance_mm": float(params.distance_mm),
            "px_per_mm": round(float(self.scale.px_per_mm), 6),
            "arcmin_per_px": round(float(self.scale.arcmin_per_px), 6),
            "scale_source": self.scale.source,
            "field_deg": float(params.field_deg),
            "squares": int(params.squares),
            "line_count": int(params.line_count),
            "dot_pitch": int(params.dot_pitch),
            "spoke_count": int(params.spoke_count),
            "rotation_deg": int(params.rotation_deg),
            "source_px": int(params.source_px),
            "surround_px": int(params.surround_px),
            "ghost_offset": int(params.ghost_offset),
            "ghost_direction": params.ghost_direction,
            "contrast": int(params.contrast),
            "veil_contrast": int(params.veil_contrast),
            "luminance": int(params.luminance),
        }
        if self.last_fit is not None:
            snapshot["field"] = self.last_fit.as_dict()
        return snapshot

    def grade(self, value: int) -> ActionResult:
        """Store (or replace) the grade for the item on screen."""
        value = int(value)
        if not 0 <= value <= 9:
            raise ValueError(f"a grade is an integer from 0 to 9, got {value}")
        if self.shown_family is None:
            self.message = "no pattern shown yet — show a pattern before grading"
            return ActionResult(False, self.message)

        params = self.params
        key = (params.family, params.current_item(), params.eye)
        previous = self.grades.get(key)
        grade = Grade(
            family=params.family,
            item_index=params.current_item(),
            value=value,
            geometry=self.geometry_snapshot(),
            pairing=params.variant_name,
            eye=params.eye,
            fixation_visible=params.fixation_visible,
            attempts=(previous.attempts + 1) if previous else 1,
        )
        self.grades[key] = grade
        if key not in self._grade_order:
            self._grade_order.append(key)
        item = params.current_item() + 1
        self.message = (
            f"grade {value} for {params.family} item {item}"
            + (" (regraded)" if previous else "")
            + ("" if params.fixation_visible else " — fixation mark was hidden")
        )
        return ActionResult(True, self.message)

    def ordered_grades(self) -> list[Grade]:
        """Every grade, in the order the items were first graded."""
        return [self.grades[key] for key in self._grade_order if key in self.grades]

    # -- export -------------------------------------------------------------
    def export(
        self,
        directory: str | Path | None = None,
        timestamp=None,
        panel: dict | None = None,
    ) -> export.ExportResult:
        """Write PNG plus JSON; a failure leaves the session untouched."""
        result = export.export_session(
            self, directory=directory, timestamp=timestamp, panel=panel
        )
        self.message = result.message()
        return result

    def _handle_export(self) -> ActionResult:
        result = self.export()
        return ActionResult(
            result.ok, self.message, "exported" if result.ok else "export_failed"
        )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="visiontest",
        description=(
            "A self-administered distortion atlas: live test patterns with "
            "visual-angle geometry, grading and session export. "
            "Not a medical device."
        ),
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="print the panel, scale and pixel-path readout, then exit",
    )
    parser.add_argument(
        "--distance",
        type=float,
        default=calibration.DEFAULT_DISTANCE_MM,
        metavar="MM",
        help=f"viewing distance in millimetres (default {calibration.DEFAULT_DISTANCE_MM:.0f})",
    )
    parser.add_argument(
        "--ambient",
        default="unspecified",
        metavar="TEXT",
        help="ambient condition note stored with the session (default 'unspecified')",
    )
    parser.add_argument(
        "--export-dir",
        default=None,
        metavar="PATH",
        help=f"where PNG and JSON are written (default {export.DEFAULT_EXPORT_DIR})",
    )
    return parser.parse_args(argv)


def _build_scale(
    args: argparse.Namespace, width: int, height: int
) -> tuple[Scale, dict]:
    panel = export.panel_identity()
    size = panel.get("size_mm")
    panel_mm = tuple(size) if size else calibration.DEFAULT_PANEL_MM
    scale = calibration.default_scale(
        distance_mm=args.distance,
        width_px=width,
        height_px=height,
        panel_mm=panel_mm,
    )
    return scale, panel


def _build_session(
    args: argparse.Namespace, width: int, height: int
) -> tuple[Session, dict]:
    scale, panel = _build_scale(args, width, height)
    session = Session(
        width=width,
        height=height,
        scale=scale,
        export_dir=args.export_dir,
        ambient_note=args.ambient,
    )
    return session, panel


def _run_self_check(args: argparse.Namespace) -> int:
    """Report the panel, scale, field fit and pixel path, then exit."""
    app = None
    try:
        from .backends.qt import QtPresenter, configure_scaling, create_application

        configure_scaling()
        app = create_application()
        width, height = QtPresenter.screen_size(app)
        print(f"screen: {width}×{height} px, scale factor 1 requested")
    except Exception as error:  # no display, or no PyQt6
        width, height = 1920, 1080
        print(f"screen: unavailable ({error}); using {width}×{height} for the readout")

    session, panel = _build_session(args, width, height)
    print(
        f"panel: {panel['name']} ({panel['manufacturer']}) "
        f"{panel['resolution']} from {panel['source']}"
    )
    print(f"buffer: {width}×{height} px")
    print(
        f"scale: {session.scale.px_per_mm:.3f} px/mm "
        f"({session.scale.source}), {session.scale.arcmin_per_px:.3f}′/px "
        f"at {session.scale.distance_mm:.0f} mm"
    )
    fit = fit_field(
        session.scale,
        float(session.params.field_deg),
        int(session.params.squares),
        width,
        height,
    )
    print(f"amsler fit: {fit.summary()}")
    hundred_mm = session.scale.px_for_mm(100.0)
    print(
        f"ruler reference: 100 mm = {hundred_mm:.0f} px "
        f"({session.scale.describe_px(hundred_mm)})"
    )

    session.handle_key("c")  # the one-pixel checkerboard

    if app is not None:
        presenter = QtPresenter(session, app=app)
        presenter.show(session.presented())
        app.processEvents()
        surface = presenter.surface_size()
        check = presenter.check_surface()
        print(f"surface: {surface[0]}×{surface[1]} px")
        print(f"pixel path: {check.message}")
        print(
            "by eye: the checkerboard should read as uniform mid-grey; "
            "any moiré means the pixel path is being scaled"
        )
        presenter.close()
        app.processEvents()
    else:
        print(f"pixel path: {session.self_check.message}")

    print(f"readout: {session.overlay_text()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point used by ``main.py``."""
    args = _parse_args(argv)
    print(STARTUP_NOTICE)

    if args.self_check:
        return _run_self_check(args)

    from .backends.qt import QtPresenter, configure_scaling, create_application

    configure_scaling()
    app = create_application()
    width, height = QtPresenter.screen_size(app)
    session, panel = _build_session(args, width, height)
    session.render()

    presenter = QtPresenter(session, app=app)
    check = presenter.check_surface()
    if not check.ok:
        print(f"WARNING: {check.message}")
        print("The session is marked unreliable; press any key to continue or Esc.")
    presenter.show(session.presented())
    presenter.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())




