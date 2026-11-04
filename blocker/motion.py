"""Immediate press feedback and interruptible page transitions."""
import ctypes
import os

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, Qt, Property, QRectF, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QPushButton, QStackedWidget, QLabel, QSizePolicy

PRESS_MS = 160


def system_allows_motion():
    if os.environ.get("RELAY_REDUCE_MOTION") == "1":
        return False
    if os.name == "nt":
        enabled = ctypes.c_int(1)
        try:
            if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
                return bool(enabled.value)
        except (AttributeError, OSError):
            return False
    return True


class MotionButton(QPushButton):
    """Animate mouse release, never keyboard activation or programmatic clicks."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.feedback = QGraphicsOpacityEffect(self)
        self.feedback.setOpacity(1)
        self.setGraphicsEffect(self.feedback)
        self.release_animation = QPropertyAnimation(self.feedback, b"opacity", self)
        self.release_animation.setDuration(PRESS_MS)
        curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
        curve.addCubicBezierSegment(QPointF(.23, 1), QPointF(.32, 1), QPointF(1, 1))
        self.release_animation.setEasingCurve(curve)
        self.pointer_press = False

    def motion_allowed(self):
        app = QApplication.instance()
        return app.property("relayMotionEnabled") is not False and system_allows_motion()

    def reset_feedback(self):
        self.release_animation.stop()
        self.feedback.setOpacity(1)
        self.pointer_press = False

    def mousePressEvent(self, event):
        self.pointer_press = (event.button() == Qt.MouseButton.LeftButton
                              and event.source() == Qt.MouseEventSource.MouseEventNotSynthesized
                              and self.motion_allowed())
        self.release_animation.stop()
        self.feedback.setOpacity(.90 if self.pointer_press else 1)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        play = self.pointer_press and self.motion_allowed()
        self.pointer_press = False
        super().mouseReleaseEvent(event)
        if play and self.isEnabled():
            self.release_animation.setStartValue(self.feedback.opacity())
            self.release_animation.setEndValue(1)
            self.release_animation.start()
        else:
            self.reset_feedback()

    def keyPressEvent(self, event):
        self.reset_feedback()
        super().keyPressEvent(event)

    def hideEvent(self, event):
        self.reset_feedback()
        super().hideEvent(event)

    def changeEvent(self, event):
        if not self.isEnabled():
            self.reset_feedback()
        super().changeEvent(event)


class TransitionStack(QStackedWidget):
    """Fade a snapshot over the new page; live controls stay interactive."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.veil = QLabel(self)
        self.veil.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.veil.hide()
        self.effect = QGraphicsOpacityEffect(self.veil)
        self.veil.setGraphicsEffect(self.effect)
        self.transition = QPropertyAnimation(self.effect, b"opacity", self)
        self.transition.setDuration(220)
        self.transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.transition.finished.connect(self.finish_transition)

    def finish_transition(self):
        self.transition.stop()
        self.veil.hide()
        self.veil.clear()

    def setCurrentIndex(self, index):
        if index == self.currentIndex() or not 0 <= index < self.count():
            return
        app = QApplication.instance()
        animate = (self.isVisible() and app.property("relayMotionEnabled") is not False
                   and system_allows_motion())
        # Capture the presentation, including any transition already in flight.
        shot = self.grab() if animate else None
        self.finish_transition()
        super().setCurrentIndex(index)
        if shot is not None:
            self.veil.setPixmap(shot)
            self.veil.setGeometry(self.rect())
            self.veil.raise_()
            self.effect.setOpacity(1)
            self.veil.show()
            self.transition.setStartValue(1)
            self.transition.setEndValue(0)
            self.transition.start()

    def resizeEvent(self, event):
        self.finish_transition()
        super().resizeEvent(event)

    def hideEvent(self, event):
        self.finish_transition()
        super().hideEvent(event)


class RailButton(MotionButton):
    """A fixed hit target with independently animated icon and highlight."""

    def __init__(self, title, icon, parent=None):
        super().__init__("", parent)
        self.setObjectName("railButton")
        self.setAccessibleName(title)
        self.setToolTip(title)
        self.setIcon(icon)
        self.setCheckable(True)
        self.setFixedSize(54, 54)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = 0.0
        self.hover_animation = QPropertyAnimation(self, b"hoverProgress", self)
        self.hover_animation.setDuration(180)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def sizeHint(self):
        return QSize(54, 54)

    def minimumSizeHint(self):
        return QSize(54, 54)

    def get_hover(self):
        return self._hover

    def set_hover(self, value):
        self._hover = value
        self.update()

    hoverProgress = Property(float, get_hover, set_hover)

    def animate_hover(self, target):
        self.hover_animation.stop()
        if self.motion_allowed():
            self.hover_animation.setStartValue(self._hover)
            self.hover_animation.setEndValue(target)
            self.hover_animation.start()
        else:
            self.set_hover(target)

    def enterEvent(self, event):
        self.animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animate_hover(0.0)
        super().leaveEvent(event)

    def reset_feedback(self):
        super().reset_feedback()
        if hasattr(self, "hover_animation"):
            self.hover_animation.stop()
            self.set_hover(0.0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(2, 2, self.width() - 4, self.height() - 4)
        selected = self.isChecked()
        dark = QApplication.instance().property("relayTheme") != "light"
        if selected:
            painter.setBrush(QColor("#dedee8" if dark else "#242426"))
            painter.setPen(QPen(QColor("#f5f5fa" if dark else "#3c3c40"), 1))
            painter.drawRoundedRect(bounds, 17, 17)
        elif self._hover > 0:
            painter.setBrush(QColor(74, 74, 88, round(235 * self._hover)) if dark else QColor(255, 255, 255, round(235 * self._hover)))
            painter.setPen(QPen(QColor(111, 111, 129, round(180 * self._hover)) if dark else QColor(255, 255, 255, round(255 * self._hover)), 1))
            painter.drawRoundedRect(bounds, 17, 17)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#777780"), 1.5))
            painter.drawRoundedRect(bounds.adjusted(-1, -1, 1, 1), 18, 18)
        size = round(23 + 4 * self._hover)
        # Tint the complete SVG consistently in both selected and resting states.
        dpr = self.devicePixelRatioF()
        pix = self.icon().pixmap(QSize(size, size), dpr)
        tint = QPainter(pix)
        tint.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        tint.fillRect(pix.rect(), QColor(("#222229" if selected else "#dddde8") if dark else ("#ffffff" if selected else "#303035")))
        tint.end()
        x = (self.width() - size) / 2
        y = (self.height() - size) / 2 - 2 * self._hover
        painter.drawPixmap(QRectF(x, y, size, size), pix, QRectF(pix.rect()))


class ThemeFade(QLabel):
    """Cross-fade the entire shell without blocking input or changing layout."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.animation = QPropertyAnimation(self.effect, b"opacity", self)
        self.animation.setDuration(280)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.finished.connect(self.finish)
        self.hide()

    def capture(self):
        app = QApplication.instance()
        allowed = (self.parentWidget().isVisible()
                   and app.property("relayMotionEnabled") is not False
                   and system_allows_motion())
        # Include the current overlay when a previous fade is interrupted.
        shot = self.parentWidget().grab() if allowed else None
        self.finish()
        return shot

    def play(self, shot):
        if shot is None:
            return
        self.setPixmap(shot)
        self.setGeometry(self.parentWidget().rect())
        self.effect.setOpacity(1)
        self.raise_()
        self.show()
        self.animation.setStartValue(1)
        self.animation.setEndValue(0)
        self.animation.start()

    def finish(self):
        self.animation.stop()
        self.hide()
        self.clear()
