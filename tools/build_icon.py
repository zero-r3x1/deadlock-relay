"""Render the source SVG into a PNG and a multi-resolution Windows icon."""
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter, QIcon
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]


def render(renderer, size):
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return image


def build():
    app = QApplication.instance() or QApplication(sys.argv)
    renderer = QSvgRenderer(str(ROOT / "assets/icon.svg"))
    if not renderer.isValid():
        raise RuntimeError("Invalid icon SVG")
    render(renderer, 512).save(str(ROOT / "assets/icon.png"))
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    payloads = []
    for size in sizes:
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not render(renderer, size).save(buffer, "PNG"):
            raise RuntimeError("PNG encoding failed")
        payloads.append(bytes(data))
    offset = 6 + 16 * len(sizes)
    entries = []
    for size, data in zip(sizes, payloads):
        entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0,
                                   1, 32, len(data), offset))
        offset += len(data)
    icon = ROOT / "assets/icon.ico"
    icon.write_bytes(struct.pack("<HHH", 0, 1, len(sizes)) +
                     b"".join(entries) + b"".join(payloads))
    loaded = QIcon(str(icon))
    for size in sizes:
        if loaded.pixmap(size, size).isNull():
            raise RuntimeError(f"Icon validation failed at {size}px")
    print("Generated icon.svg -> icon.png + icon.ico (9 sizes)")


if __name__ == "__main__":
    build()
