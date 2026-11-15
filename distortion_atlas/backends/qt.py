"""Qt presenter: an unfiltered, 1:1 QImage blit into a fullscreen window.

Qt is already installed, runs natively on Wayland (no XWayland resampling) and
lets the scaling policy be forced before the window exists. The presenter owns
no pattern logic: it shows the buffer a :class:`~distortion_atlas.ui.Session` renders
and forwards key names, which is what keeps the renderers testable headlessly.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from .. import keybar
from ..ui import (
    OVERLAY_ALPHA,
    OVERLAY_BACKGROUND,
    OVERLAY_TEXT_COLOUR,
)

#: Font size of the readout line, in points.
OVERLAY_FONT_POINTS = 11

#: Where the readout line starts inside the strip.
OVERLAY_TEXT_ORIGIN = (8, 18)

#: Slot tint of an active button, as RGBA.
BAR_ACTIVE_COLOUR = (64, 64, 64, 210)

#: Slot tint of the button under the pointer, as RGBA.
BAR_HOVER_COLOUR = (96, 96, 96, 210)

#: Press-and-hold repeat: first delay, then the interval, in milliseconds (D7).
REPEAT_DELAY_MS = 400
REPEAT_INTERVAL_MS = 80

#: Default idle time after which the bar hides, in milliseconds (D4).
KEY_BAR_IDLE_MS = 3000

#: Scotoma-test clock sampling interval, in milliseconds (design D1).
STIMULUS_SAMPLE_MS = 20


#: GNOME schema whose keys Qt 6.6 still reads from the pre-45 location.
XSETTINGS_SCHEMA = "org.gnome.settings-daemon.plugins.xsettings"

#: The key whose absence makes GLib abort the process inside Qt.
XSETTINGS_PROBE_KEY = "antialiasing"


def schema_shim_dir() -> Path:
    """Directory holding the packaged GLib schema shim.

    ``DISTORTION_ATLAS_SCHEMA_DIR`` overrides it for systems where the installed
    package directory is not writable when the shim has to be compiled on demand.
    """
    override = os.environ.get("DISTORTION_ATLAS_SCHEMA_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "qtshim"


def _schema_key_present(key: str = XSETTINGS_PROBE_KEY) -> bool:
    """Whether GLib can read ``key``; probing failure counts as "present"."""
    try:
        done = subprocess.run(
            ["gsettings", "get", XSETTINGS_SCHEMA, key],
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    return done.returncode == 0


def ensure_gnome_schema() -> str:
    """Point GLib at the shim when Qt 6.6 and GNOME disagree.

    gnome-settings-daemon moved ``antialiasing``/``hinting``/``rgba-order`` into
    ``…plugins.xsettings.deprecated``; Qt 6.6 reads the old id and GLib turns the
    missing key into an abort that no Python handler can catch. The probe runs
    before Qt is imported, so setting ``GSETTINGS_SCHEMA_DIR`` here is early
    enough to matter.

    Returns ``"ok"`` when nothing was needed, ``"shimmed"`` when the shim was
    applied, ``"unavailable"`` when the schema is broken and no shim could be
    built (Qt then fails with its own message).
    """
    if sys.platform != "linux":
        return "ok"
    if _schema_key_present():
        return "ok"

    shim = schema_shim_dir()
    source = shim / "org.gnome.qtshim.gschema.xml"
    if not source.is_file():
        return "unavailable"
    if not (shim / "gschemas.compiled").is_file():
        try:
            subprocess.run(
                ["glib-compile-schemas", str(shim)],
                capture_output=True,
                timeout=60,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            return "unavailable"

    search = [str(shim)]
    existing = os.environ.get("GSETTINGS_SCHEMA_DIR")
    if existing:
        search.extend(part for part in existing.split(os.pathsep) if part)
    os.environ["GSETTINGS_SCHEMA_DIR"] = os.pathsep.join(search)
    return "shimmed" if _schema_key_present() else "unavailable"


def configure_scaling() -> None:
    """Force an unscaled pixel path before Qt builds its application object."""
    os.environ.setdefault("QT_SCALE_FACTOR", "1")
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")
    os.environ.setdefault("QT_SCREEN_SCALE_FACTORS", "1")


def create_application():
    """A single :class:`QApplication` with high-DPI scaling disabled."""
    status = ensure_gnome_schema()
    if status == "shimmed":
        print(
            "note: GLib schema shim applied for Qt 6.6 "
            f"(GSETTINGS_SCHEMA_DIR={schema_shim_dir()}); "
            "see README troubleshooting",
            file=sys.stderr,
        )
    elif status == "unavailable":
        print(
            "note: this desktop lacks the GNOME font keys Qt 6.6 reads and no "
            "shim could be built; if Qt aborts, install PyQt6 6.7 or newer",
            file=sys.stderr,
        )

    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        return app
    # Qt 6 disables high-DPI scaling through the environment; the (deprecated)
    # application attribute is only set when this Qt build still exposes it.
    attribute = getattr(
        Qt.ApplicationAttribute, "AA_DisableHighDpiScaling", None
    )
    if attribute is not None:
        QGuiApplication.setAttribute(attribute, True)
    return QApplication(["distortion-atlas"])


def _special_keys() -> dict:
    from PyQt6.QtCore import Qt

    return {
        Qt.Key.Key_Up: "Up",
        Qt.Key.Key_Down: "Down",
        Qt.Key.Key_Left: "Left",
        Qt.Key.Key_Right: "Right",
        Qt.Key.Key_Tab: "Tab",
        Qt.Key.Key_Backtab: "Shift+Tab",
        Qt.Key.Key_Escape: "Esc",
        Qt.Key.Key_Space: "Space",
        Qt.Key.Key_Plus: "+",
        Qt.Key.Key_Minus: "-",
        Qt.Key.Key_BracketLeft: "[",
        Qt.Key.Key_BracketRight: "]",
    }


def key_name(event) -> str:
    """Translate a Qt key event into the session's key vocabulary."""
    special = _special_keys()
    if event.key() in special:
        return special[event.key()]
    text = event.text() or ""
    if len(text) != 1:
        return ""
    if text.isdigit():
        return text
    if text.isalpha():
        return text.lower()
    if text == "=":  # unshifted plus on many layouts
        return "+"
    if text == "_":
        return "-"
    if text in "+-[]":
        return text
    return ""


def is_coarse(event, name: str) -> bool:
    """Shift coarsens the arrow keys; Ctrl coarsens contrast and distance."""
    from PyQt6.QtCore import Qt

    modifiers = event.modifiers()
    if name in ("Up", "Down", "Left", "Right"):
        return bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
    return bool(modifiers & Qt.KeyboardModifier.ControlModifier)


class _ViewerWindow:
    """Factory wrapper so Qt is imported only when a window is built."""

    def __init__(self, session, key_bar_idle_ms: int = KEY_BAR_IDLE_MS):
        from PyQt6.QtCore import QPoint, QRect, Qt, QTimer
        from PyQt6.QtGui import QColor, QImage, QPainter
        from PyQt6.QtWidgets import QApplication, QWidget

        self.session = session
        outer = self

        class Window(QWidget):
            def __init__(self) -> None:
                super().__init__()
                self.session = session
                self._buffer = None
                self._image = None
                self.hold_until_key = False
                self._hover_key = None
                self._repeat_button = None
                self._repeat_coarse = False
                self.setWindowTitle("distortion-atlas")
                self.setMouseTracking(True)
                self.setCursor(Qt.CursorShape.BlankCursor)

                self._idle_timer = QTimer(self)
                self._idle_timer.setSingleShot(True)
                self._idle_timer.setInterval(int(key_bar_idle_ms))
                self._idle_timer.timeout.connect(self._idle)

                # Press-and-hold: one delay timer, then a repeating ticker.
                self._repeat_delay_timer = QTimer(self)
                self._repeat_delay_timer.setSingleShot(True)
                self._repeat_delay_timer.setInterval(REPEAT_DELAY_MS)
                self._repeat_delay_timer.timeout.connect(self._begin_repeat)
                self._repeat_timer = QTimer(self)
                self._repeat_timer.setInterval(REPEAT_INTERVAL_MS)
                self._repeat_timer.timeout.connect(self._repeat_step)

                # Scotoma test: sample the clock, repaint on a state change only.
                self._stimulus_timer = QTimer(self)
                self._stimulus_timer.setInterval(STIMULUS_SAMPLE_MS)
                self._stimulus_timer.timeout.connect(self._sample_stimulus)

            # -- buffer and painting ---------------------------------------
            def set_buffer(self, buffer: np.ndarray) -> None:
                array = np.ascontiguousarray(buffer)
                height, width = array.shape[:2]
                self._buffer = array
                self._image = QImage(
                    array.data,
                    width,
                    height,
                    3 * width,
                    QImage.Format.Format_RGB888,
                )
                self.update()

            def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
                painter = QPainter(self)
                if self._image is not None:
                    painter.drawImage(QPoint(0, 0), self._image)
                if self.session.params.overlay:
                    font = painter.font()
                    font.setPointSize(OVERLAY_FONT_POINTS)
                    painter.setFont(font)
                    painter.setPen(QColor(*OVERLAY_TEXT_COLOUR))
                    painter.drawText(*OVERLAY_TEXT_ORIGIN, self.session.overlay_text())
                if self._bar_shown():
                    self._paint_bar(painter)
                painter.end()

            # -- key bar ---------------------------------------------------
            def _bar(self):
                return keybar.build(
                    self.width(), self.height(), outer.session.key_bar_state()
                )

            def _bar_shown(self) -> bool:
                return (
                    outer.session.key_bar_visible
                    and outer.session.key_bar_allowed
                    and not self.hold_until_key
                )

            def _paint_bar(self, painter) -> None:
                bar = self._bar()
                panel = QColor(*OVERLAY_BACKGROUND)
                panel.setAlphaF(OVERLAY_ALPHA)
                painter.fillRect(QRect(*bar.rect), panel)
                caption_font = painter.font()
                caption_font.setPointSize(OVERLAY_FONT_POINTS)
                hint_font = painter.font()
                hint_font.setPointSize(max(6, OVERLAY_FONT_POINTS - 4))
                active_tint = QColor(*BAR_ACTIVE_COLOUR)
                hover_tint = QColor(*BAR_HOVER_COLOUR)
                for button in bar.buttons:
                    rect = QRect(*button.rect)
                    if button.active:
                        painter.fillRect(rect, active_tint)
                    elif (button.action, button.key) == self._hover_key:
                        painter.fillRect(rect, hover_tint)
                    painter.setPen(QColor(*OVERLAY_TEXT_COLOUR))
                    if button.hint and button.hint != button.caption:
                        split = int(button.rect[3] * 0.62)
                        left, top, width, height = button.rect
                        caption_rect = QRect(left, top, width, split)
                        hint_rect = QRect(left, top + split, width, height - split)
                        painter.setFont(hint_font)
                        painter.drawText(
                            hint_rect, Qt.AlignmentFlag.AlignCenter, button.hint
                        )
                        painter.setFont(caption_font)
                        painter.drawText(
                            caption_rect, Qt.AlignmentFlag.AlignCenter, button.caption
                        )
                    else:
                        painter.setFont(caption_font)
                        painter.drawText(
                            rect, Qt.AlignmentFlag.AlignCenter, button.caption
                        )

            # -- pointer, cursor and timers --------------------------------
            def _apply_cursor(self) -> None:
                if not self._bar_shown():
                    self.setCursor(Qt.CursorShape.BlankCursor)
                elif self._hover_key is not None:
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
                else:
                    self.setCursor(Qt.CursorShape.ArrowCursor)

            def _reveal(self) -> None:
                if self.hold_until_key or not outer.session.show_key_bar():
                    self._hover_key = None
                    self._apply_cursor()
                    return
                self._idle_timer.start()
                self._apply_cursor()
                self.update()

            def _idle(self) -> None:
                if self._repeat_button is not None:
                    # A held step button is still pointer activity (D7).
                    self._idle_timer.start()
                    return
                outer.session.hide_key_bar()
                self._hover_key = None
                self._stop_repeat()
                self._apply_cursor()
                self.update()

            def _button_at(self, position):
                if not self._bar_shown():
                    return None
                return keybar.hit_test(self._bar(), position.x(), position.y())

            # -- dispatch --------------------------------------------------
            def _dispatch(self, name: str, coarse: bool = False):
                if not name:
                    return None
                result = outer.session.handle_key(name, coarse)
                if result.action == "quit" or not outer.session.running:
                    self.close()
                    QApplication.quit()
                    return result
                if result.action == "toggle_fullscreen":
                    if outer.session.fullscreen:
                        self.showFullScreen()
                    else:
                        self.resize(self.session.width, self.session.height)
                        self.showNormal()
                if not outer.session.key_bar_allowed:
                    outer.session.hide_key_bar()
                    self._hover_key = None
                    self._stop_repeat()
                test = outer.session.scotoma
                if test is not None and not test.finished:
                    if not self._stimulus_timer.isActive():
                        self._stimulus_timer.start()
                elif self._stimulus_timer.isActive():
                    self._stimulus_timer.stop()
                self.set_buffer(outer.session.presented())
                self._apply_cursor()
                return result

            def _sample_stimulus(self) -> None:
                """Advance the scotoma test clock and repaint on a change."""
                test = outer.session.scotoma
                if test is None or test.finished:
                    self._stimulus_timer.stop()
                    return
                if outer.session.tick_scotoma_test():
                    self.set_buffer(outer.session.presented())
                if test.finished:
                    self._stimulus_timer.stop()

            def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
                if self.hold_until_key:
                    self.close()
                    QApplication.quit()
                    return
                name = key_name(event)
                if not name:
                    return
                self._dispatch(name, is_coarse(event, name))

            # -- mouse -----------------------------------------------------
            def mouseMoveEvent(self, event) -> None:  # noqa: N802 (Qt naming)
                self._reveal()
                button = self._button_at(event.position())
                hover = (button.action, button.key) if button is not None else None
                changed = hover != self._hover_key
                self._hover_key = hover
                if changed:
                    self._apply_cursor()
                    self.update()

            def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
                if event.button() != Qt.MouseButton.LeftButton:
                    return
                if self.hold_until_key:
                    self.close()
                    QApplication.quit()
                    return
                test = outer.session.scotoma
                if test is not None and not test.finished:
                    # A click is a response only while a dot is lit; the bar is inert.
                    if test.lit:
                        self._dispatch("Space")
                    return
                self._reveal()
                button = self._button_at(event.position())
                if button is None:
                    self.update()
                    return
                coarse = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                self._dispatch(button.key, coarse)
                if button.repeatable and outer.session.running and self._bar_shown():
                    self._repeat_button = button
                    self._repeat_coarse = coarse
                    self._repeat_delay_timer.start()

            def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt naming)
                if event.button() == Qt.MouseButton.LeftButton:
                    self._stop_repeat()

            def _begin_repeat(self) -> None:
                if self._repeat_button is not None and outer.session.running:
                    self._repeat_timer.start()

            def _repeat_step(self) -> None:
                if (
                    self._repeat_button is None
                    or not outer.session.running
                    or not self._bar_shown()
                ):
                    self._stop_repeat()
                    return
                self._dispatch(self._repeat_button.key, self._repeat_coarse)

            def _stop_repeat(self) -> None:
                self._repeat_delay_timer.stop()
                self._repeat_timer.stop()
                self._repeat_button = None

            def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
                self._stop_repeat()
                self._stimulus_timer.stop()
                QApplication.quit()
                super().closeEvent(event)

        self.widget = Window()


class QtPresenter:
    """Presents session buffers fullscreen, one image pixel per screen pixel."""

    def __init__(
        self,
        session,
        app=None,
        fullscreen: bool = True,
        key_bar_idle_ms: int = KEY_BAR_IDLE_MS,
    ) -> None:
        self.session = session
        self.app = app if app is not None else create_application()
        self._window = _ViewerWindow(session, key_bar_idle_ms=key_bar_idle_ms)
        self.widget = self._window.widget
        if fullscreen:
            # Size the surface to the whole screen before it is mapped, so the
            # integrity check compares real numbers instead of Qt's 640×480
            # placeholder size.
            screen = self.widget.screen() or self.app.primaryScreen()
            if screen is not None:
                self.widget.setGeometry(screen.geometry())
            self.widget.showFullScreen()
            if screen is not None:
                self.widget.setGeometry(screen.geometry())
        else:
            self.widget.resize(session.width, session.height)
            self.widget.show()
        for _ in range(3):
            self.app.processEvents()

    @staticmethod
    def screen_size(app=None) -> tuple[int, int]:
        """Primary screen size in device pixels (scaling is disabled)."""
        app = app if app is not None else create_application()
        screen = app.primaryScreen()
        if screen is None:  # pragma: no cover - platform without a screen
            raise RuntimeError("no screen available")
        geometry = screen.geometry()
        return int(geometry.width()), int(geometry.height())

    def surface_size(self) -> tuple[int, int]:
        return int(self.widget.width()), int(self.widget.height())

    def check_surface(self):
        """Compare the presented surface with the rendered buffer."""
        return self.session.update_pixel_path(
            self.surface_size(), float(self.widget.devicePixelRatioF())
        )

    def show(self, buffer: np.ndarray) -> None:
        self.widget.set_buffer(buffer)

    def dispatch(self, key: str, coarse: bool = False):
        """Key dispatch without a real event, used by the offscreen test."""
        result = self.session.handle_key(key, coarse)
        test = self.session.scotoma
        if test is not None and not test.finished:
            if not self.widget._stimulus_timer.isActive():
                self.widget._stimulus_timer.start()
        elif self.widget._stimulus_timer.isActive():
            self.widget._stimulus_timer.stop()
        self.widget.set_buffer(self.session.presented())
        return result

    def run(self) -> int:
        return int(self.app.exec())

    def hold(self, seconds: float | None = None) -> None:
        """Keep the current frame on screen, then close the window.

        ``None`` waits for a key press or the window's close button, ``0``
        returns without starting an event loop and a positive number waits that
        many seconds. Used by ``--self-check``, whose whole point is to let an
        observer judge the presented pixels.
        """
        from PyQt6.QtCore import QTimer

        if seconds is not None and seconds <= 0:
            return
        if seconds is None:
            self.widget.hold_until_key = True
        else:
            QTimer.singleShot(int(round(seconds * 1000)), self.app.quit)
        self.app.exec()
        self.close()

    def close(self) -> None:
        self.widget.close()

