"""Capture documentation images using isolated data and no system changes."""
import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication, QLabel
from blocker import ui


def main():
    app = QApplication([])
    ui.prepare_app(app)
    output = ui.ROOT / "docs/screenshots"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        ui.DATA = Path(temp)
        ui.find_game = lambda: r"C:\Games\Deadlock\game\bin\win64\deadlock.exe"
        window = ui.Window(offline=True)
        for item in window.findChildren(QLabel):
            if item.text() == str(ui.DATA):
                item.setText(r"%LOCALAPPDATA%\DeadlockRelay")
        window.resize(1320, 920)
        window.show()
        window.choose_preset("ru")
        window.show_rules({"rules": [], "currentProfiles": 4,
                           "enabledProfiles": [{"profile": 4, "enabled": True}]})
        for name, theme, page in [
            ("home-dark", "dark", 0), ("home-light", "light", 0),
            ("settings", "dark", 1), ("about", "dark", 2),
        ]:
            window.set_theme(theme)
            window.navigate(page)
            window.theme_fade.finish()
            window.stack.finish_transition()
            app.processEvents()
            if not window.grab().save(str(output / f"{name}.png")):
                raise RuntimeError("Screenshot encoding failed")
            print(f"Captured {name}.png")
        window.close()


if __name__ == "__main__":
    main()
