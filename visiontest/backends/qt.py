"""Qt presenter: an unfiltered, 1:1 QImage blit into a fullscreen window.

Qt is already installed, runs natively on Wayland (no XWayland resampling) and
lets the scaling policy be forced before the window exists. The presenter owns
no pattern logic: it shows the buffer a :class:`~visiontest.ui.Session` renders
and forwards key names, which is what keeps the renderers testable headlessly.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np

#: Font size of the readout line, in points.
OVERLAY_FONT_POINTS = 11

#: Where the readout line starts inside the strip.
OVERLAY_TEXT_ORIGIN = (8, 18)

#: GNOME schema whose keys Qt 6.6 still reads from the pre-45 location.
XSETTINGS_SCHEMA = "org.gnome.settings-daemon.plugins.xsettings"

#: The key whose absence makes GLib abort the process inside Qt.
XSETTINGS_PROBE_KEY = "antialiasing"


def schema_shim_dir() -> Path:
    """Directory holding the checked-in GLib schema shim."""
    return Path(__file__).resolve().parents[2] / "qtshim"


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
            "(GSETTINGS_SCHEMA_DIR=qtshim); see README troubleshooting",
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
    return QApplication(["visiontest"])


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

    def __init__(self, session):
        from PyQt6.QtCore import QPoint, Qt
        from PyQt6.QtGui import QColor, QImage, QPainter
        from PyQt6.QtWidgets import QApplication, QWidget

        from ..ui import OVERLAY_TEXT_COLOUR

        self.session = session
        outer = self

        class Window(QWidget):
            def __init__(self) -> None:
                super().__init__()
                self.session = session
                self._buffer = None
                self._image = None
                self.hold_until_key = False
                self.setWindowTitle("visiontest")
                self.setCursor(Qt.CursorShape.BlankCursor)

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
                painter.end()

            def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
                if self.hold_until_key:
                    self.close()
                    QApplication.quit()
                    return
                name = key_name(event)
                if not name:
                    return
                result = outer.session.handle_key(name, is_coarse(event, name))
                if result.action == "quit" or not outer.session.running:
                    self.close()
                    QApplication.quit()
                    return
                if result.action == "toggle_fullscreen":
                    if outer.session.fullscreen:
                        self.showFullScreen()
                    else:
                        self.resize(self.session.width, self.session.height)
                        self.showNormal()
                self.set_buffer(outer.session.presented())

            def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
                QApplication.quit()
                super().closeEvent(event)

        self.widget = Window()


class QtPresenter:
    """Presents session buffers fullscreen, one image pixel per screen pixel."""

    def __init__(self, session, app=None, fullscreen: bool = True) -> None:
        self.session = session
        self.app = app if app is not None else create_application()
        self._window = _ViewerWindow(session)
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

