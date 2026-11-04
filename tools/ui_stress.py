"""Development-only Break UI harness. Never imported by the packaged application.

Run: .venv/Scripts/python tools/ui_stress.py
Capture: ... tools/ui_stress.py --capture <directory>
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if "--capture" in sys.argv:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea
from blocker import ui, core

LONG_PRESET = "Стокгольм_вечером_для_совместной_игры_с_друзьями_без_остальных"[:60]
NAMES = [
    "Datapacket Frankfurt am Main — Telekom international network (Germany)",
    "HongKongInternationalTelecommunicationsExchangeUnicomBackbone",
    "J", "東京・江東区 — 香港 — Стокгольм", "",
    "<b>Stockholm & partners</b>",
]


def fixture(raw, mode):
    result = copy.deepcopy(raw)
    entries = list(result["pops"].items())
    usable = [(k, v) for k, v in entries if v.get("relays")]
    if mode == "One":
        result["pops"] = dict(usable[:1])
    elif mode == "Worst case":
        for (_, value), name in zip(usable, NAMES):
            value["desc"] = name
    elif mode == "1,000 rows":
        result["pops"] = {f"relay{i:04d}": dict(copy.deepcopy(usable[i % len(usable)][1]),
                                               desc=f"Regional relay network — node {i + 1}")
                          for i in range(1000)}
    return result


class StressHarness(QWidget):
    def __init__(self, base):
        super().__init__()
        self.base = base
        self.setWindowTitle("DEV ONLY · Break UI · No firewall changes")
        self.resize(1360, 1040)
        self.window = ui.Window(offline=True)
        self.window.setWindowFlags(Qt.WindowType.Widget)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.window, 1)
        controls = QHBoxLayout()
        controls.addStretch()
        for mode in ["Demo data", "Worst case", "Empty", "One", "1,000 rows"]:
            b = QPushButton(mode)
            b.clicked.connect(lambda checked=False, m=mode: self.select(m))
            controls.addWidget(b)
        zoom = QPushButton("Text 100% / 200%")
        zoom.clicked.connect(self.toggle_zoom)
        controls.addWidget(zoom)
        controls.addStretch()
        layout.addLayout(controls)
        self.zoom = False
        self.normal_style = QApplication.instance().styleSheet()
        self.select("Demo data")

    def select(self, mode):
        start = time.perf_counter()
        w = self.window
        w.settings = {}
        w.preset = ""
        w.custom = {}
        w.search.clear()
        w.install_config(fixture(self.base, mode), "DEV / " + mode, initial=True)
        w.game.setText(r"D:\SteamLibrary\Игры и приложения\Deadlock\game\bin\win64\deadlock.exe")
        if mode == "Worst case":
            w.custom[LONG_PRESET] = sorted(w.allowed)
            w.latencies = {p.code: [0, None, 999][i % 3] for i, p in enumerate(w.pops)}
            w.render_table()
        w.reload_custom()
        if mode == "Worst case":
            w.custom_combo.setCurrentIndex(1)
        if mode == "Empty":
            w.search.setText("no-relay-has-this-name.example.test")
        for control in [w.apply_btn, w.reset_btn, w.refresh_btn, w.ping_btn]:
            control.setEnabled(False)
        w.status.setText("DEV ONLY · Тестовые данные. Изменение правил отключено.")
        QApplication.processEvents()
        self.elapsed_ms = round((time.perf_counter() - start) * 1000)

    def toggle_zoom(self):
        self.zoom = not self.zoom
        style = re.sub(r"font-size:\s*(\d+)px", lambda m: f"font-size: {int(m[1]) * 2}px", self.normal_style) if self.zoom else self.normal_style
        QApplication.instance().setStyleSheet(style)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    app = QApplication([])
    ui.prepare_app(app)
    raw = json.loads((core.ROOT / "assets/sdr-deadlock.json").read_text(encoding="utf-8-sig"))
    with tempfile.TemporaryDirectory() as tmp:
        # No user's presets, cache, or firewall are touched by this process.
        ui.DATA = core.DATA = Path(tmp)
        def forbidden(*args, **kwargs):
            raise RuntimeError("DEV ONLY: system operations disabled")
        ui.apply_rules = ui.remove_rules = ui.fetch_config = ui.inspect_rules = forbidden
        ui.Window.elevate = ui.Window.check_firewall = ui.Window.ping = forbidden
        harness = StressHarness(raw)
        harness.show()
        if args.capture:
            args.capture.mkdir(parents=True, exist_ok=True)
            for width, height in [(1080, 900), (1320, 1040), (1920, 1080)]:
                harness.resize(width, height)
                app.processEvents()
                for mode in ["Demo data", "Worst case", "Empty", "One", "1,000 rows"]:
                    harness.select(mode)
                    app.processEvents()
                    name = f"{width}-{mode.replace(' ', '-').replace(',', '')}.png"
                    harness.grab().save(str(args.capture / name))
                    print(f"{name}: {harness.elapsed_ms}ms", flush=True)
                    if mode == "Worst case":
                        scroll = harness.window.findChild(QScrollArea)
                        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
                        app.processEvents()
                        harness.grab().save(str(args.capture / f"{width}-Worst-case-table.png"))
                        scroll.verticalScrollBar().setValue(0)
            harness.resize(1320, 1040)
            harness.select("Worst case")
            harness.toggle_zoom()
            app.processEvents()
            harness.grab().save(str(args.capture / "1320-text-200.png"))
            harness.close()
            return 0
        return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
