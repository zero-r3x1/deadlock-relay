import sys

if __name__ == "__main__":
    if "--self-check" in sys.argv:
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        import tempfile
        from pathlib import Path
        from PySide6.QtWidgets import QApplication
        from blocker import ui
        app = QApplication(sys.argv)
        ui.prepare_app(app)
        with tempfile.TemporaryDirectory() as temp:
            ui.DATA = Path(temp)
            ui.find_game = lambda: ""
            window = ui.Window(offline=True)
            assert window.table.rowCount() > 0
            assert not window.windowIcon().isNull()
            for theme in ("light", "dark"):
                window.set_theme(theme)
                assert window.theme == theme
            for page in (1, 2, 0):
                window.navigate(page)
                assert window.stack.currentIndex() == page
            for preset in ui.PRESETS:
                window.choose_preset(preset)
                assert window.allowed
            window.close()
        raise SystemExit(0)
    else:
        from blocker.ui import launch
        raise SystemExit(launch(offline="--offline" in sys.argv))
