import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from blocker.core import ROOT, PRESETS
from blocker.ui import Window, prepare_app


class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        prepare_app(cls.app)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_patch = patch("blocker.ui.DATA", Path(self.temp.name))
        self.data_patch.start()
        self.window = Window(offline=True)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.data_patch.stop()
        self.temp.cleanup()

    def test_navigation_presets_and_search(self):
        w = self.window
        w.navs[1].click()
        self.assertEqual(w.stack.currentIndex(), 1)
        w.navs[0].click()
        for key in PRESETS:
            w.preset_buttons[key].click()
            self.assertEqual(w.preset, key)
            self.assertTrue(w.allowed)
            self.assertEqual(sum(w.table.item(r, 0).checkState() == Qt.CheckState.Checked
                                 for r in range(w.table.rowCount())), len(w.allowed))
        w.search.setText("hkg")
        self.assertEqual(sum(not w.table.isRowHidden(r) for r in range(w.table.rowCount())), 1)

    def test_manual_selection_and_allow_all(self):
        w = self.window
        w.choose_preset("ru")
        item = w.table.item(0, 0)
        item.setCheckState(Qt.CheckState.Checked)
        self.assertEqual(w.preset, "")
        self.assertIn(item.data(Qt.ItemDataRole.UserRole), w.allowed)
        w.allow_all()
        self.assertEqual(len(w.allowed), len(w.pops))

    def test_theme_switch_and_restore(self):
        w = self.window
        w.choose_preset("ru")
        allowed = set(w.allowed)
        w.search.setText("hkg")
        w.navigate(1)
        for theme in ("light", "dark"):
            w.theme_button.click()
            self.app.processEvents()
            self.assertEqual(self.app.property("relayTheme"), theme)
            self.assertEqual(w.allowed, allowed)
            self.assertEqual(w.search.text(), "hkg")
            self.assertEqual(w.stack.currentIndex(), 1)
            restored = Window(offline=True)
            self.assertEqual(restored.theme, theme)
            self.assertFalse(hasattr(restored, "theme_combo"))
            self.assertTrue(restored.theme_button.toolTip())
            restored.close()
            if os.environ.get("RELAY_TEST_SCREENSHOT"):
                w.theme_fade.finish()
                w.grab().save(os.environ["RELAY_TEST_SCREENSHOT"] + f"-{theme}-settings.png")
                w.navigate(0)
                w.search.clear()
                self.app.processEvents()
                w.stack.finish_transition()
                w.grab().save(os.environ["RELAY_TEST_SCREENSHOT"] + f"-{theme}.png")
                w.search.setText("hkg")
                w.navigate(1)

    def test_custom_preset_roundtrip(self):
        w = self.window
        with patch("blocker.ui.QInputDialog.getText", return_value=("Мой маршрут", True)):
            w.choose_preset("us")
            expected = set(w.allowed)
            w.save_custom()
        w.allow_all()
        w.load_custom()
        self.assertEqual(w.allowed, expected)
        w.save()
        restored = Window(offline=True)
        self.assertEqual(restored.allowed, expected)
        self.assertIn("Мой маршрут", restored.custom)
        restored.close()

    def test_theme_animation_interrupt_and_disable(self):
        from PySide6.QtCore import QAbstractAnimation
        from PySide6.QtTest import QTest
        w = self.window
        self.app.setProperty("relayMotionEnabled", True)
        with patch("blocker.motion.system_allows_motion", return_value=True):
            w.theme_button.click()
            self.assertEqual(w.theme_fade.animation.state(), QAbstractAnimation.State.Running)
            QTest.qWait(70)
            w.theme_button.click()
            self.assertEqual(w.theme, "dark")
            self.assertTrue(w.theme_button.isEnabled())
            QTest.qWait(330)
            self.assertFalse(w.theme_fade.isVisible())
            w.theme_button.click()
            w.motion_checkbox.setChecked(False)
            self.assertFalse(w.theme_fade.isVisible())
            w.theme_button.click()
            self.assertEqual(w.theme, "dark")
            self.assertEqual(w.theme_fade.animation.state(), QAbstractAnimation.State.Stopped)

    def test_real_rule_status_does_not_follow_pending_selection(self):
        w = self.window
        w.game.setText(r"C:\Games\deadlock.exe")
        pop = w.pops[0]
        rule = {"enabled": True, "action": 0, "direction": 2,
                "program": w.game.text(), "ips": ",".join(pop.ips)}
        w.show_rules({"rules": [rule]})
        w.allow_all()
        self.assertEqual(w.rule_status(pop), "Закрыто")
        w.game.setText("C:/Games/deadlock.exe")
        self.assertEqual(w.rule_status(pop), "Закрыто")
        rule["program"] = r"C:\Other\deadlock.exe"
        self.assertEqual(w.rule_status(pop), "Без правил")

    def test_missing_admin_requests_elevation(self):
        from PySide6.QtWidgets import QMessageBox
        w = self.window
        with patch("blocker.ui.is_admin", return_value=False), patch(
            "blocker.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes
        ), patch.object(w, "elevate") as elevate:
            self.assertFalse(w.request_admin())
            elevate.assert_called_once()
        with patch("blocker.ui.is_admin", return_value=False), patch(
            "blocker.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.No
        ), patch.object(w, "elevate") as elevate:
            self.assertFalse(w.request_admin())
            elevate.assert_not_called()

    def test_disabled_firewall_requires_consent(self):
        from PySide6.QtWidgets import QMessageBox
        w = self.window
        off = {"rules": [], "currentProfiles": 2,
               "enabledProfiles": [{"profile": 2, "enabled": False}]}
        on = {"rules": [], "currentProfiles": 2,
              "enabledProfiles": [{"profile": 2, "enabled": True}]}
        from unittest.mock import Mock
        ready = Mock()
        def run(fn, done, lock=False, finished=None):
            done(on if fn is ui_enable else off)
            if finished:
                finished()
        from blocker.ui import enable_firewall as ui_enable
        with patch.object(w, "run_job", side_effect=run) as jobs, patch(
            "blocker.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.No
        ):
            w.verify_firewall(ready)
            self.app.processEvents()
            ready.assert_not_called()
            self.assertEqual(jobs.call_count, 1)
        with patch.object(w, "run_job", side_effect=run) as jobs, patch(
            "blocker.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes
        ):
            w.verify_firewall(ready)
            self.app.processEvents()
            self.app.processEvents()
            ready.assert_called_once()
            self.assertEqual(jobs.call_count, 2)

    def test_native_layout_sizes(self):
        w = self.window
        for width, height in [(1320, 930), (1080, 900)]:
            w.resize(width, height)
            self.app.processEvents()
            self.assertGreater(w.table.viewport().height(), 220)
            self.assertLess(w.preset_panel.height(), 250)
            self.assertFalse(hasattr(w, "route_title"))
            self.assertGreater(w.apply_btn.height(), 40)
            for nav in w.navs:
                self.assertEqual(nav.width(), 54)
                self.assertEqual(nav.height(), 54)
                self.assertTrue(nav.accessibleName())
                self.assertTrue(nav.toolTip())
        if os.environ.get("RELAY_TEST_SCREENSHOT"):
            w.resize(1320, 980)
            self.app.processEvents()
            w.grab().save(os.environ["RELAY_TEST_SCREENSHOT"])

    def test_corrupt_settings_do_not_prevent_startup(self):
        path = Path(self.temp.name) / "settings.json"
        for content in ("broken JSON", "null", "[]",
                        '{"custom":[],"game":3,"allowed":[{}],"preset":[],"theme":[],"motion":"false"}'):
            path.write_text(content, encoding="utf-8")
            with patch("blocker.ui.find_game", return_value=""):
                restored = Window(offline=True)
            self.assertEqual(restored.custom, {})
            self.assertEqual(restored.theme, "dark")
            self.assertEqual(restored.game.text(), "")
            self.assertEqual(len(restored.allowed), len(restored.pops))
            restored.close()

    def test_invalid_refresh_preserves_existing_config(self):
        w = self.window
        before = (w.raw, w.pops, w.generation, set(w.allowed))
        with self.assertRaises(ValueError):
            w.install_config({"revision": "bad", "pops": {}}, "bad response")
        self.assertEqual((w.raw, w.pops, w.generation, w.allowed), before)

    def test_callback_failure_is_reported_and_unlocks_controls(self):
        from PySide6.QtCore import QThread
        w = self.window
        threads = []
        def bad_callback(result):
            threads.append(QThread.currentThread())
            raise ValueError("Invalid response")
        with patch.object(w, "error") as error:
            w.run_job(lambda: {}, bad_callback, lock=True)
            self.assertTrue(w.pool.waitForDone(2000))
            self.app.processEvents()
            error.assert_called_once_with("Invalid response")
            self.assertEqual(threads, [self.app.thread()])
            self.assertFalse(w.busy)
            self.assertFalse(w.jobs)

    def test_worker_failure_unlocks_controls(self):
        w = self.window
        def failed():
            raise RuntimeError("Connection failed")
        with patch.object(w, "error") as error:
            w.run_job(failed, lambda result: self.fail("Unexpected success"), lock=True)
            self.assertTrue(w.pool.waitForDone(2000))
            self.app.processEvents()
            error.assert_called_once_with("Connection failed")
            self.assertFalse(w.busy)
            self.assertFalse(w.jobs)

    def test_ping_completes_and_does_not_overwrite_new_config(self):
        w = self.window
        with patch("blocker.ui.ping_ip", return_value=12):
            w.ping()
            self.assertTrue(w.pool.waitForDone(2000))
            self.app.processEvents()
        self.assertFalse(w.pinging)
        self.assertTrue(w.ping_btn.isEnabled())
        self.assertEqual(len(w.latencies), len(w.pops))
        before = dict(w.latencies)
        w.ping_done((w.generation - 1, {"old": 999}))
        self.assertEqual(w.latencies, before)

    def test_unknown_firewall_is_not_shown_as_enabled(self):
        self.window.show_rules({"rules": []})
        self.assertEqual(self.window.badge.property("tone"), "warning")

    def test_apply_preflight_reaches_worker(self):
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtTest import QTest
        from PySide6.QtCore import QElapsedTimer
        w = self.window
        game = Path(self.temp.name) / "deadlock.exe"
        game.touch()
        w.game.setText(str(game))
        w.choose_preset("ru")
        state = {"rules": [], "currentProfiles": 4,
                 "enabledProfiles": [{"profile": 4, "enabled": True}]}
        with patch("blocker.ui.is_admin", return_value=True), patch(
            "blocker.ui.inspect_rules", return_value=state
        ), patch("blocker.ui.apply_rules") as apply, patch(
            "blocker.ui.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes
        ):
            w.apply()
            timer = QElapsedTimer()
            timer.start()
            while timer.elapsed() < 3000 and (w.jobs or not apply.called):
                QTest.qWait(20)
            apply.assert_called_once()
            self.assertFalse(w.busy)
            self.assertFalse(w.jobs)


if __name__ == "__main__":
    unittest.main()
