# Third-party components

- PySide6 / Shiboken 6.10.2: LGPLv3 / GPLv3 / commercial, depending on the component.
- Qt Core, GUI, Widgets and SVG: Qt module-specific licenses.
- Python 3.12: Python Software Foundation license.
- PyInstaller: GPL with a bootloader exception allowing distribution of bundled applications.

Sources and license information:

- https://code.qt.io/pyside/pyside-setup.git/
- https://code.qt.io/qt/qtbase.git/
- https://code.qt.io/qt/qtsvg.git/
- https://www.qt.io/licensing/open-source-lgpl-obligations
- https://www.gnu.org/licenses/lgpl-3.0.html
- https://docs.python.org/3/license.html
- https://pyinstaller.org/en/stable/license.html

The onedir build uses separate Qt DLLs. Users may replace these with compatible modified libraries and debug changes to LGPL components. Preserve the included third-party license texts with redistributed builds. No CS2 Server Picker source code is incorporated.
