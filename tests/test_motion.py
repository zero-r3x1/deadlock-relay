import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import unittest
from unittest.mock import patch

from PySide6.QtCore import QAbstractAnimation, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from blocker.motion import MotionButton, TransitionStack


class MotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.app.setProperty("relayMotionEnabled", True)
        self.button = MotionButton("Test")
        self.button.resize(150, 50)
        self.button.show()
        self.app.processEvents()

    def tearDown(self):
        self.button.close()

    def test_mouse_feedback_completes(self):
        with patch("blocker.motion.system_allows_motion", return_value=True):
            QTest.mousePress(self.button, Qt.MouseButton.LeftButton)
            self.assertAlmostEqual(self.button.feedback.opacity(), .9)
            QTest.mouseRelease(self.button, Qt.MouseButton.LeftButton)
            self.assertEqual(self.button.release_animation.state(), QAbstractAnimation.State.Running)
            QTest.qWait(200)
            self.assertAlmostEqual(self.button.feedback.opacity(), 1)

    def test_reduced_motion_respected(self):
        with patch("blocker.motion.system_allows_motion", return_value=False):
            QTest.mouseClick(self.button, Qt.MouseButton.LeftButton)
            self.assertEqual(self.button.release_animation.state(), QAbstractAnimation.State.Stopped)
            self.assertEqual(self.button.feedback.opacity(), 1)

    def test_keyboard_activation_instant(self):
        calls = []
        self.button.clicked.connect(lambda: calls.append(True))
        QTest.keyClick(self.button, Qt.Key.Key_Space)
        self.assertEqual(calls, [True])
        self.assertEqual(self.button.release_animation.state(), QAbstractAnimation.State.Stopped)

    def test_disable_during_press_restores_opacity(self):
        with patch("blocker.motion.system_allows_motion", return_value=True):
            QTest.mousePress(self.button, Qt.MouseButton.LeftButton)
            self.button.setEnabled(False)
            self.assertEqual(self.button.feedback.opacity(), 1)
            self.assertEqual(self.button.release_animation.state(), QAbstractAnimation.State.Stopped)


class TransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_interrupt_and_reduced_motion(self):
        from PySide6.QtWidgets import QWidget
        stack = TransitionStack()
        for _ in range(3):
            stack.addWidget(QWidget())
        stack.show()
        self.app.processEvents()
        self.app.setProperty("relayMotionEnabled", True)
        with patch("blocker.motion.system_allows_motion", return_value=True):
            stack.setCurrentIndex(1)
            self.assertEqual(stack.transition.state(), QAbstractAnimation.State.Running)
            stack.setCurrentIndex(2)
            QTest.qWait(280)
            self.assertEqual(stack.currentIndex(), 2)
            self.assertFalse(stack.veil.isVisible())
            self.app.setProperty("relayMotionEnabled", False)
            stack.setCurrentIndex(0)
            self.assertFalse(stack.veil.isVisible())
            self.assertEqual(stack.transition.state(), QAbstractAnimation.State.Stopped)
        stack.close()
        self.app.setProperty("relayMotionEnabled", True)


class RailHoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_hover_reverses_from_current_value(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QIcon
        from blocker.motion import RailButton
        button = RailButton("Settings", QIcon())
        self.app.setProperty("relayMotionEnabled", True)
        with patch("blocker.motion.system_allows_motion", return_value=True):
            self.app.sendEvent(button, QEvent(QEvent.Type.Enter))
            QTest.qWait(65)
            current = button.get_hover()
            self.assertGreater(current, 0)
            self.assertLess(current, 1)
            self.app.sendEvent(button, QEvent(QEvent.Type.Leave))
            self.assertAlmostEqual(button.hover_animation.startValue(), current)
            QTest.qWait(220)
            self.assertAlmostEqual(button.get_hover(), 0)
            self.assertEqual(button.size().width(), 54)
        button.close()

    def test_hover_respects_reduced_motion(self):
        from PySide6.QtGui import QIcon
        from blocker.motion import RailButton
        button = RailButton("Settings", QIcon())
        with patch("blocker.motion.system_allows_motion", return_value=False):
            button.animate_hover(1)
            self.assertEqual(button.get_hover(), 1)
            self.assertEqual(button.hover_animation.state(), QAbstractAnimation.State.Stopped)
            button.reset_feedback()
            self.assertEqual(button.get_hover(), 0)
        button.close()


if __name__ == "__main__":
    unittest.main()
