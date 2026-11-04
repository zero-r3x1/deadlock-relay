"""Two palettes share one stylesheet and the same layout."""
import re
from PySide6.QtGui import QColor, QPalette
from .core import ROOT

LIGHT = {
    "#111114": "#d2d2d8", "#19191f": "#ffffff",
    "#202027": "#f0f0f4", "#222229": "#ffffff", "#23352c": "#e4f3e8",
    "#24242b": "#f7f7fa", "#25252c": "#f3f3f7", "#27272f": "#f2f2f5",
    "#282830": "#f7f8fa", "#292932": "#e5e5eb", "#2b2b34": "#fafafb",
    "#2d2d35": "#e9e9ed", "#2d2d36": "#ebebf0", "#30303a": "#dcdce4",
    "#34343c": "#dedee8", "#34343e": "#e0e0e6", "#393024": "#fff3d6",
    "#393943": "#e0e6ee", "#393945": "#e8e8ef", "#3a3a44": "#e6e6eb",
    "#3b3b47": "#ffffff", "#3b3b49": "#e4e4eb", "#3c3c47": "#e3e3e8",
    "#3e3e49": "#e0e8f2", "#405e4a": "#b8d9c0", "#41414c": "#fafafd",
    "#42424e": "#d1d1da", "#444450": "#e3e3e9", "#454552": "#d8d8e1",
    "#484852": "#d2d2db", "#4b4b59": "#ceced8", "#4b4b60": "#dcdce8",
    "#50505c": "#ccd8e7", "#565666": "#b7b7c1", "#626276": "#555563",
    "#6b5637": "#ebd39c", "#707080": "#b4b4c0", "#77778a": "#92929e",
    "#797989": "#babac6", "#79798b": "#aaaab6", "#878796": "#787881",
    "#9090a6": "#555563", "#9595a6": "#64768a", "#a0a0b0": "#72727c",
    "#a1a1b9": "#5e5e68", "#a2a2b2": "#65656f", "#a4a4b0": "#62626b",
    "#a6dbb5": "#236336", "#aaaab9": "#64646e", "#aaaac8": "#535380",
    "#b0b0be": "#66666f", "#b0b0c0": "#62626c", "#bdbdcd": "#414146",
    "#c1c1ce": "#4b4b55", "#c8c8d4": "#161619", "#d4d4de": "#42424a",
    "#d7d7e4": "#34343a", "#dddde7": "#29292d", "#eeeef2": "#1d1d1f",
    "#f0f0f4": "#242429", "#f1ce8c": "#805000", "#f1f1f7": "#414146",
}


def apply_theme(app, theme):
    theme = theme if theme in ("light", "dark") else "dark"
    sheet = (ROOT / "blocker/style.qss").read_text(encoding="utf-8")
    if theme == "light":
        sheet = re.sub(r"#[0-9a-fA-F]{6}",
                       lambda match: LIGHT[match.group().lower()], sheet)
    app.setProperty("relayTheme", theme)
    palette = app.style().standardPalette()
    palette.setColor(QPalette.ColorRole.Link,
                     QColor("#5577bb" if theme == "light" else "#aabfff"))
    if theme == "dark":
        for role, color in {
            QPalette.ColorRole.Window: "#24242b",
            QPalette.ColorRole.WindowText: "#eeeef2",
            QPalette.ColorRole.Base: "#222229",
            QPalette.ColorRole.AlternateBase: "#282830",
            QPalette.ColorRole.Text: "#eeeef2",
            QPalette.ColorRole.Button: "#2d2d35",
            QPalette.ColorRole.ButtonText: "#eeeef2",
            QPalette.ColorRole.Highlight: "#4b4b60",
            QPalette.ColorRole.HighlightedText: "#ffffff",
        }.items():
            palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(sheet.replace("__ASSETS__", (ROOT / "assets").as_posix()))
    return theme
