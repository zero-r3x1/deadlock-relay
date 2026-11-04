from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import ipaddress

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, QTimer, Signal, Slot, QLockFile, QEvent
from PySide6.QtGui import QColor, QIcon, QFont, QFontDatabase, QDesktopServices
from PySide6.QtCore import QUrl, QSize
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QInputDialog,
    QComboBox, QProgressBar, QStackedWidget, QAbstractItemView,
    QGraphicsDropShadowEffect, QSizePolicy, QScrollArea, QCheckBox)

from .core import (ROOT, DATA, API, PRESETS, atomic_json, parse_config,
                   cached_config, fetch_config, build_plan, find_game, normalize_settings)
from .firewall import inspect_rules, apply_rules, remove_rules, ping_ip, is_admin, enable_firewall, disabled_active_profiles
from .motion import MotionButton, TransitionStack, RailButton, ThemeFade
from .themes import apply_theme


class Signals(QObject):
    done = Signal(object)
    error = Signal(str)
    finished = Signal()


class Job(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = Signals()

    def run(self):
        try:
            self.signals.done.emit(self.fn())
        except Exception as error:
            self.signals.error.emit(str(error))
        finally:
            self.signals.finished.emit()


def label(text, name="", wrap=False):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def button(text, fn, name=""):
    b = MotionButton(text)
    if name:
        b.setObjectName(name)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.clicked.connect(fn)
    return b


def panel(name="panel"):
    w = QFrame()
    w.setObjectName(name)
    layout = QVBoxLayout(w)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    return w, layout


class PresetButton(MotionButton):
    def __init__(self, key, title, subtitle, fn):
        super().__init__()
        self.setObjectName("preset")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"{title}. {subtitle}")
        self.clicked.connect(fn)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 9, 14, 9)
        layout.setSpacing(4)
        captions = {"ru": ("RU / NORD", "Стокгольм · приближение"),
                    "eu": ("EUROPE", "Без Стокгольма"),
                    "us": ("UNITED STATES", "Американские relay"),
                    "cn": ("CHINA / HK", "Гонконг · приближение")}
        code, detail = captions[key]
        for text, name in [(code, "presetCode"), (title, "presetTitle")]:
            item = label(text, name, wrap=True)
            item.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(item)


class Window(QMainWindow):
    def __init__(self, offline=False):
        super().__init__()
        self.setWindowTitle("Deadlock Relay · Выбор региона")
        self.setWindowIcon(QIcon(str(ROOT / "assets/icon.ico")))
        self.resize(1320, 920)
        self.setMinimumSize(1080, 820)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(4)
        self.jobs = set()
        self.busy = False
        self.pinging = False
        self.loading = False
        self.rules = []
        self.latencies = {}
        self.preset = ""
        self.allowed = set()
        self.custom = {}
        self.source = ""
        self.raw = {}
        self.pops = []
        self.generation = 0
        try:
            self.settings = json.loads((DATA / "settings.json").read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            self.settings = {}
        self.settings = normalize_settings(self.settings)
        self.custom = self.settings.get("custom", {})
        self.theme = self.settings.get("theme", "dark")
        self.theme = apply_theme(QApplication.instance(), self.theme)
        QApplication.instance().setProperty("relayMotionEnabled", self.settings.get("motion", True))
        self.build_ui()
        self.theme_fade = ThemeFade(self.centralWidget())
        self.update_theme_icons()
        try:
            raw, source = cached_config()
            self.install_config(raw, source, initial=True)
        except ValueError as error:
            self.status.setText(str(error))
        self.game.setText(self.settings.get("game", "") or find_game())
        self.game.editingFinished.connect(self.save)
        self.game.editingFinished.connect(self.render_table)
        if not offline:
            QTimer.singleShot(0, self.startup_check)

    def build_ui(self):
        shell = QWidget()
        shell.setObjectName("shell")
        self.setCentralWidget(shell)
        outer = QHBoxLayout(shell)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(22)
        rail, rl = panel("rail")
        rail.setFixedWidth(82)
        rl.setContentsMargins(13, 20, 13, 18)
        rl.setSpacing(14)
        mark = label("", "logoMark")
        self.brand_mark = mark
        mark.setPixmap(QIcon(str(ROOT / "assets/icons/spark.svg")).pixmap(32, 32))
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(52, 52)
        rl.addWidget(mark)
        divider = QFrame()
        divider.setObjectName("railDivider")
        divider.setFixedHeight(1)
        rl.addWidget(divider)
        rl.addSpacing(12)
        self.navs = []
        for index, text in enumerate(["Подключение", "Настройки", "О серверах"]):
            b = RailButton(text, QIcon(str(ROOT / "assets/icons" / ["network.svg", "settings.svg", "info.svg"][index])))
            b.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            self.navs.append(b)
        rl.addWidget(self.navs[0])
        rl.addWidget(self.navs[2])
        rl.addStretch()
        credit = label('<a href="https://www.youtube.com/@zero-r2x1">by ноль</a>', "railNote")
        credit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit.setWordWrap(True)
        credit.setOpenExternalLinks(True)
        credit.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        credit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        credit.setToolTip("YouTube-канал ноль")
        rl.addWidget(credit)
        self.theme_button = RailButton("", QIcon())
        self.theme_button.setCheckable(False)
        self.theme_button.clicked.connect(self.toggle_theme)
        rl.addWidget(self.theme_button)
        rl.addWidget(self.navs[1])
        outer.addWidget(rail)
        self.stack = TransitionStack()
        workspace, workspace_layout = panel("workspace")
        workspace_layout.setContentsMargins(24, 22, 24, 22)
        workspace_layout.addWidget(self.stack)
        outer.addWidget(workspace, 1)
        home = QWidget()
        self.home = home
        hl = QVBoxLayout(home)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(12)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label("DEADLOCK RELAY", "eyebrow"))
        titles.addWidget(label("Подключение", "title"))
        heading.addLayout(titles, 1)
        self.badge = label("Проверка правил…", "badge")
        heading.addWidget(self.badge)
        hl.addLayout(heading)
        p, pl = panel()
        self.preset_panel = p
        pl.setContentsMargins(16, 12, 16, 12)
        pl.setSpacing(8)
        p.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        top = QHBoxLayout()
        top.addWidget(label("Регион подключения", "section"))
        top.addStretch()
        top.addWidget(label("Пресеты и свои маршруты", "muted"))
        pl.addLayout(top)
        grid = QGridLayout()
        self.preset_grid = grid
        grid.setSpacing(10)
        self.preset_buttons = {}
        for index, (key, (title, subtitle, _, __)) in enumerate(PRESETS.items()):
            b = PresetButton(key, title, subtitle, lambda checked=False, k=key: self.choose_preset(k))
            b.setToolTip(PRESETS[key][3])
            self.preset_buttons[key] = b
            grid.addWidget(b, 0, index)
        pl.addLayout(grid)
        self.explanation = label("Выбор маршрута не гарантирует язык или страну игроков в матче.", "muted", True)
        pl.addWidget(self.explanation)
        custom_row = QHBoxLayout()
        self.custom_combo = QComboBox()
        self.custom_combo.currentTextChanged.connect(self.custom_combo.setToolTip)
        self.custom_combo.setMinimumWidth(190)
        self.reload_custom()
        custom_row.addWidget(self.custom_combo, 1)
        self.load_custom_btn = button("Выбрать", self.load_custom)
        self.save_custom_btn = button("Сохранить свой", self.save_custom)
        self.delete_custom_btn = button("Удалить", self.delete_custom)
        for b in [self.load_custom_btn, self.save_custom_btn, self.delete_custom_btn]:
            custom_row.addWidget(b)
        pl.addLayout(custom_row)
        hl.addWidget(p)
        p, pl = panel()
        p.setMinimumHeight(330)
        row = QHBoxLayout()
        row.addWidget(label("Точки подключения", "section"))
        row.addStretch()
        self.count = label("", "muted")
        row.addWidget(self.count)
        pl.addLayout(row)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по городу, коду или региону…")
        self.search.setAccessibleName("Поиск точек подключения")
        self.search.textChanged.connect(self.filter_rows)
        row.addWidget(self.search, 1)
        self.all_btn = button("Разрешить все", self.allow_all)
        self.ping_btn = button("Проверить пинг", self.ping)
        self.refresh_btn = button("Обновить Valve", self.refresh)
        for b in [self.all_btn, self.ping_btn, self.refresh_btn]:
            row.addWidget(b)
        pl.addLayout(row)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Доступ", "Точка / город", "Регион", "IP", "Пинг", "Брандмауэр"])
        self.table.verticalHeader().hide()
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col, width in [(0, 70), (2, 140), (3, 45), (4, 80), (5, 125)]:
            self.table.setColumnWidth(col, width)
        self.table.verticalHeader().setDefaultSectionSize(43)
        self.table.itemChanged.connect(self.item_changed)
        self.table.setMinimumHeight(170)
        pl.addWidget(self.table, 1)
        self.source_label = label("", "muted")
        pl.addWidget(self.source_label)
        hl.addWidget(p, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        hl.addWidget(self.progress)
        footer = QFrame()
        footer.setObjectName("footer")
        bottom = QHBoxLayout(footer)
        bottom.setContentsMargins(16, 12, 16, 12)
        self.status = label("Выбери пресет или отметь доступные точки.", "muted", True)
        bottom.addWidget(self.status, 1)
        self.reset_btn = button("Снять блокировки", self.reset)
        self.apply_btn = button("Применить маршрут", self.apply, "primary")
        bottom.addWidget(self.reset_btn)
        bottom.addWidget(self.apply_btn)
        home_scroll = QScrollArea()
        home_scroll.setWidgetResizable(True)
        home_scroll.setFrameShape(QFrame.Shape.NoFrame)
        home_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        home_scroll.setWidget(home)
        home_page = QWidget()
        page_layout = QVBoxLayout(home_page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(12)
        page_layout.addWidget(home_scroll, 1)
        page_layout.addWidget(footer)
        self.stack.addWidget(home_page)
        self.build_settings()
        self.build_about()
        self.navigate(0)

    def build_settings(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label("Настройки", "title"))
        p, pl = panel()
        pl.addWidget(label("Игра и брандмауэр", "section"))
        pl.addWidget(label("Выбери файл Deadlock. Правила будут действовать только для этого приложения.", "muted", True))
        row = QHBoxLayout()
        self.game = QLineEdit()
        self.game.setAccessibleName("Путь к исполняемому файлу Deadlock")
        self.game.setPlaceholderText(r"…\Deadlock\game\bin\win64\deadlock.exe")
        self.game.setAccessibleName("Путь к deadlock.exe")
        row.addWidget(self.game, 1)
        row.addWidget(button("Обзор…", self.browse))
        pl.addLayout(row)
        pl.addWidget(label("Права администратора: " + ("есть" if is_admin() else "нет — потребуются при применении"), "muted"))
        pl.addWidget(button("Перезапустить с правами администратора", self.elevate))
        pl.addWidget(button("Проверить реальные правила Windows", self.check_firewall))
        pl.addWidget(button("Открыть брандмауэр Windows", lambda: QDesktopServices.openUrl(QUrl("windowsdefender://network"))))
        self.firewall_note = label("Статус сетевых профилей ещё не прочитан.", "muted", True)
        pl.addWidget(self.firewall_note)
        pl.addWidget(label("Закрытие приложения сохраняет блокировки. Для возврата обычного подключения нажми «Снять блокировки». Удаляются только правила Deadlock Relay.", "muted", True))
        layout.addWidget(p)
        p, pl = panel()
        pl.addWidget(label("Оформление и данные", "section"))
        pl.addWidget(label(str(DATA), "muted", True))
        pl.addWidget(label("Здесь сохраняются пресеты, путь к игре и кэш Valve. Пресеты не включаются автоматически при запуске. Обновление списка адресов также требует повторного применения маршрута.", "muted", True))
        self.motion_checkbox = QCheckBox("Анимации интерфейса")
        self.motion_checkbox.setChecked(self.settings.get("motion", True))
        self.motion_checkbox.setToolTip("Плавные переходы разделов, подсветка и отклик кнопок. Учитываются настройки анимаций Windows.")
        self.motion_checkbox.toggled.connect(self.set_motion)
        pl.addWidget(self.motion_checkbox)
        layout.addWidget(p)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        self.stack.addWidget(scroll)

    def build_about(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label("Как устроены регионы", "title"))
        sections = [
            ("Точка подключения ≠ игровой сервер", [
                "Deadlock скрывает адреса матчевых серверов за Steam Datagram Relay (SDR). "
                "Приложение получает опубликованные Valve IPv4-адреса ретрансляторов для Deadlock "
                "(App ID 1422450) и ограничивает исходящие соединения deadlock.exe через Windows Firewall.",
            ]),
            ("Что делают пресеты", [
                "RU — оставляет Стокгольм как приближение. В публичном списке нет российских relay.",
                "EU — оставляет европейские точки, кроме Стокгольма. Хельсинки без опубликованных relay не включается.",
                "US — оставляет опубликованные точки США.",
                "Китай — оставляет Гонконг. В текущем списке нет материкового Китая.",
                "Эти группы описывают сетевые маршруты. Они не фильтруют игроков по языку, гражданству, "
                "стране или месту проживания. Через оставшийся relay Valve может направить трафик в другой регион.",
            ]),
            ("Пинг и статус", [
                "Пинг — ICMP до первого адреса точки; отсутствие ответа не означает, что игровой relay недоступен.",
                "Колонка «Брандмауэр» показывает собственные правила для выбранного файла игры, а не результат проверки трафика. "
                "Галочки — будущая конфигурация. Она вступает в силу только после нажатия «Применить маршрут».",
            ]),
            ("Ограничения", [
                "Чем меньше доступных маршрутов, тем выше вероятность долгого поиска или ошибки подключения. "
                "Применяй изменения до поиска матча. Блокировки сохраняются после выхода.",
                "Программа не меняет файлы игры и не использует инъекции; это не обещание совместимости с будущими обновлениями.",
            ]),
        ]
        for title, paragraphs in sections:
            card, content = panel()
            content.addWidget(label(title, "section", True))
            for text in paragraphs:
                body = label(text, "muted", True)
                body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                content.addWidget(body)
            layout.addWidget(card)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        self.stack.addWidget(scroll)

    def navigate(self, index):
        self.stack.setCurrentIndex(index)
        for i, nav in enumerate(self.navs):
            nav.setChecked(i == index)

    def run_job(self, fn, done, lock=False, finished=None):
        if lock:
            self.set_busy(True)
        job = Job(fn)
        job.callback = done
        job.lock = lock
        job.on_finished = finished
        job.result_handled = False
        job.worker_finished = False
        self.jobs.add(job)
        job.signals.done.connect(self.job_done)
        job.signals.error.connect(self.job_error)
        job.signals.finished.connect(self.job_complete)
        self.pool.start(job)

    @Slot(object)
    def job_done(self, result):
        sender = self.sender()
        job = next((job for job in self.jobs if job.signals is sender), None)
        if job is not None:
            try:
                job.callback(result)
            except Exception as error:
                self.error(str(error))
            finally:
                job.result_handled = True
                self.finish_job_if_ready(job)

    @Slot(str)
    def job_error(self, message):
        sender = self.sender()
        job = next((job for job in self.jobs if job.signals is sender), None)
        try:
            self.error(message)
        finally:
            if job is not None:
                job.result_handled = True
                self.finish_job_if_ready(job)

    @Slot()
    def job_complete(self):
        sender = self.sender()
        job = next((job for job in self.jobs if job.signals is sender), None)
        if job is not None:
            job.worker_finished = True
            self.finish_job_if_ready(job)

    def finish_job_if_ready(self, job):
        if job in self.jobs and job.result_handled and job.worker_finished:
            self.job_finished(job, job.lock)
            if job.on_finished:
                job.on_finished()

    def job_finished(self, job, lock):
        self.jobs.discard(job)
        if lock:
            self.set_busy(False)

    def set_busy(self, busy):
        self.busy = busy
        self.progress.setVisible(busy)
        for w in [self.apply_btn, self.reset_btn, self.refresh_btn, self.all_btn,
                  self.table, self.load_custom_btn, self.save_custom_btn, self.delete_custom_btn,
                  self.custom_combo, self.game, *self.preset_buttons.values()]:
            w.setEnabled(not busy)

    @Slot(str)
    def error(self, message):
        self.status.setText("Операция не завершена. " + message[:180])
        QMessageBox.warning(self, "Deadlock Relay", message)

    def install_config(self, raw, source, initial=False):
        pops = parse_config(raw)
        revision = datetime.fromtimestamp(int(raw["revision"]), timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
        self.generation += 1
        self.latencies.clear()
        self.raw, self.source = raw, source
        self.pops = pops
        known = {p.code for p in self.pops}
        if initial:
            saved = self.settings.get("allowed")
            self.allowed = set(saved) & known if saved is not None else known
            self.preset = self.settings.get("preset", "")
        elif self.preset in PRESETS:
            self.allowed = PRESETS[self.preset][2] & known
        else:
            self.allowed &= known
        self.source_label.setText(f"{source} · Deadlock 1422450 · ревизия {raw['revision']} · {revision}")
        self.render_table()
        self.update_selection()

    def refresh(self):
        if self.busy:
            return
        self.status.setText("Загружаем актуальные точки Valve…")
        self.run_job(fetch_config, self.refreshed, lock=True)

    def refreshed(self, raw):
        self.install_config(raw, "Valve · обновлено сейчас")
        self.status.setText("Список обновлён. Для обновления правил нажми «Применить маршрут».")

    def render_table(self):
        self.loading = True
        self.table.setRowCount(len(self.pops))
        for row, pop in enumerate(self.pops):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            check.setCheckState(Qt.CheckState.Checked if pop.code in self.allowed else Qt.CheckState.Unchecked)
            check.setData(Qt.ItemDataRole.UserRole, pop.code)
            self.table.setItem(row, 0, check)
            for col, value in enumerate([f"{pop.name}  / {pop.code}", pop.region, str(len(pop.ips)), self.latency_text(pop.code), self.rule_status(pop)], 1):
                item = QTableWidgetItem(value)
                item.setToolTip(pop.name + "\n" + "\n".join(pop.ips) if col == 1 else "\n".join(pop.ips) if col == 3 else value)
                self.table.setItem(row, col, item)
        self.loading = False
        self.sync_table_metrics()
        self.filter_rows()

    def sync_table_metrics(self):
        header = self.table.horizontalHeader()
        metrics = header.fontMetrics()
        for col, minimum in [(0, 70), (2, 140), (3, 45), (4, 80), (5, 125)]:
            caption = self.table.horizontalHeaderItem(col).text()
            self.table.setColumnWidth(col, max(minimum, metrics.horizontalAdvance(caption) + 24))
        self.table.verticalHeader().setDefaultSectionSize(max(43, self.table.fontMetrics().height() + 16))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.FontChange) and hasattr(self, "table"):
            QTimer.singleShot(0, self.sync_table_metrics)

    def rule_status(self, pop):
        game = self.game.text().strip() if hasattr(self, "game") else ""
        game = os.path.normcase(os.path.abspath(game)) if game else ""
        blocked = set()
        for rule in self.rules:
            program = str(rule.get("program", ""))
            program = os.path.normcase(os.path.abspath(program)) if program else ""
            if (not rule.get("enabled") or rule.get("action") != 0 or rule.get("direction") != 2
                    or not game or program != game):
                continue
            for value in str(rule.get("ips", "")).split(","):
                try:
                    net = ipaddress.ip_network(value.strip(), strict=False)
                    blocked.update(ip for ip in pop.ips if ipaddress.ip_address(ip) in net)
                except ValueError:
                    pass
        if len(blocked) == len(pop.ips):
            return "Закрыто"
        return "Частично" if blocked else "Без правил"

    def latency_text(self, code):
        if code not in self.latencies:
            return "—"
        ms = self.latencies[code]
        return f"{ms} мс" if ms is not None else "Нет ICMP"

    def filter_rows(self):
        term = self.search.text().casefold().strip()
        for row, pop in enumerate(self.pops):
            self.table.setRowHidden(row, term not in f"{pop.code} {pop.name} {pop.region}".casefold())

    def item_changed(self, item):
        if self.loading or item.column() != 0:
            return
        code = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self.allowed.add(code)
        else:
            self.allowed.discard(code)
        self.preset = ""
        self.update_selection()
        self.status.setText("Выбор изменён. Нажми «Применить маршрут», чтобы изменить правила.")

    def update_selection(self):
        self.count.setText(f"{len(self.pops)} точек · разрешено {len(self.allowed)}")
        for key, b in self.preset_buttons.items():
            b.setChecked(key == self.preset)
        self.explanation.setText(PRESETS[self.preset][3] if self.preset in PRESETS else
                                 "Свой маршрут. Состав игроков по языку и стране не гарантируется.")

    def choose_preset(self, key):
        if self.busy:
            return
        known = {p.code for p in self.pops}
        allowed = PRESETS[key][2] & known
        if not allowed:
            self.error("Для этого пресета Valve не опубликовал доступные relay.")
            return
        self.preset, self.allowed = key, allowed
        self.render_table()
        self.update_selection()
        self.status.setText("Пресет выбран. Нажми «Применить маршрут».")

    def allow_all(self):
        self.preset = ""
        self.allowed = {p.code for p in self.pops}
        self.render_table()
        self.update_selection()
        self.status.setText("Выбраны все точки. Применение снимет наши блокировки.")

    def save(self):
        try:
            atomic_json(DATA / "settings.json", {"game": self.game.text().strip(), "allowed": sorted(self.allowed),
                                                "preset": self.preset, "custom": self.custom,
                                                "motion": self.motion_checkbox.isChecked(), "theme": self.theme})
        except OSError as error:
            self.error(str(error))

    def update_theme_icons(self):
        name = "spark-light.svg" if self.theme == "light" else "spark.svg"
        self.brand_mark.setPixmap(QIcon(str(ROOT / "assets/icons" / name)).pixmap(32, 32))
        target = "light" if self.theme == "dark" else "dark"
        icon = "sun.svg" if target == "light" else "moon.svg"
        title = "Включить светлую тему" if target == "light" else "Включить тёмную тему"
        self.theme_button.setIcon(QIcon(str(ROOT / "assets/icons" / icon)))
        self.theme_button.setToolTip(title)
        self.theme_button.setAccessibleName(title)
        for nav in [*self.navs, self.theme_button]:
            nav.update()

    def toggle_theme(self):
        self.set_theme("light" if self.theme == "dark" else "dark")

    def set_theme(self, theme):
        if theme == self.theme:
            return
        shot = self.theme_fade.capture()
        self.stack.finish_transition()
        self.theme = apply_theme(QApplication.instance(), theme)
        self.update_theme_icons()
        self.theme_fade.play(shot)
        self.save()

    def set_motion(self, enabled):
        QApplication.instance().setProperty("relayMotionEnabled", enabled)
        if not enabled:
            self.theme_fade.finish()
            self.stack.finish_transition()
            for item in self.findChildren(MotionButton):
                item.reset_feedback()
        self.save()

    def reload_custom(self):
        self.custom_combo.clear()
        self.custom_combo.addItem("Свои пресеты…", "")
        for name in sorted(self.custom):
            self.custom_combo.addItem(name, name)

    def save_custom(self):
        if not self.allowed:
            self.error("Разреши хотя бы одну точку перед сохранением пресета.")
            return
        name, ok = QInputDialog.getText(self, "Свой пресет", "Название:")
        name = name.strip()[:60]
        if ok and name:
            if name in self.custom and QMessageBox.question(self, "Заменить пресет?", name) != QMessageBox.StandardButton.Yes:
                return
            self.custom[name] = sorted(self.allowed)
            self.reload_custom()
            self.custom_combo.setCurrentIndex(self.custom_combo.findData(name))
            self.save()

    def load_custom(self):
        name = self.custom_combo.currentData()
        if not name:
            return
        saved = set(self.custom[name])
        self.allowed = saved & {p.code for p in self.pops}
        self.preset = ""
        self.render_table()
        self.update_selection()
        missing = saved - {p.code for p in self.pops}
        self.status.setText("Свой пресет выбран. Требуется применение." + (" Часть точек больше не доступна: " + ", ".join(sorted(missing)) if missing else ""))

    def delete_custom(self):
        name = self.custom_combo.currentData()
        if name and QMessageBox.question(self, "Удалить пресет?", name) == QMessageBox.StandardButton.Yes:
            del self.custom[name]
            self.reload_custom()
            self.save()

    def browse(self):
        if self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Выбери deadlock.exe", self.game.text(), "Deadlock (deadlock.exe)")
        if path:
            self.game.setText(str(Path(path)))
            self.save()
            self.render_table()

    def request_admin(self):
        if is_admin():
            return True
        self.status.setText("Нужны права администратора для работы с брандмауэром.")
        if QMessageBox.question(
            self, "Нужны права администратора",
            "Deadlock Relay нужны права администратора для изменения правил брандмауэра.\n\n"
            "Перезапустить приложение от имени администратора? Подтверди запрос Windows.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        ) == QMessageBox.StandardButton.Yes:
            self.elevate()
        return False

    def startup_check(self):
        if self.request_admin():
            self.verify_firewall(self.refresh)

    def verify_firewall(self, ready):
        next_step = []
        def enable():
            success = []
            def enabled(result):
                self.show_rules(result)
                self.status.setText("Брандмауэр включён.")
                success.append(True)
            self.run_job(enable_firewall, enabled, lock=True,
                         finished=lambda: ready() if success else None)
        def checked(result):
            self.show_rules(result)
            try:
                off = disabled_active_profiles(result)
            except RuntimeError as error:
                self.error(str(error))
                return
            if not off:
                next_step.append(ready)
                return
            self.status.setText("Включи брандмауэр Windows перед применением маршрута.")
            answer = QMessageBox.question(
                self, "Брандмауэр выключен",
                "Брандмауэр активной сети выключен, поэтому блокировки серверов не будут работать.\n\n"
                "Включить брандмауэр Windows для активных сетевых профилей?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                next_step.append(enable)
        self.run_job(inspect_rules, checked, lock=True,
                     finished=lambda: next_step[0]() if next_step else None)

    def apply(self):
        if not self.busy and self.request_admin():
            self.verify_firewall(self.apply_ready)

    def apply_ready(self):
        if self.busy:
            return
        try:
            plan = build_plan(self.pops, self.allowed)
            if not is_admin():
                self.error("Нужны права администратора. Открой «Настройки» → «Перезапустить с правами администратора».")
                return
            game = self.game.text().strip()
            if not Path(game).is_file() or Path(game).name.lower() != "deadlock.exe":
                self.navigate(1)
                self.error("Выбери настоящий deadlock.exe в настройках.")
                return
            name = PRESETS[self.preset][0] if self.preset in PRESETS else "Свой маршрут"
            detail = PRESETS[self.preset][3] if self.preset in PRESETS else "Будут доступны только отмеченные точки."
            question = f"{name}\n\n{detail}\n\nРазрешено: {len(self.allowed)}. Правил блокировки: {len(plan)}.\nПрименяй до поиска матча. Правила сохранятся после выхода.\n\nПрименить?"
            if QMessageBox.question(self, "Применение маршрута", question) != QMessageBox.StandardButton.Yes:
                return
            self.save()
            self.status.setText("Применяем правила брандмауэра…")
            def work():
                apply_rules(plan, game)
                return inspect_rules()
            self.run_job(work, self.applied, lock=True)
        except Exception as error:
            self.error(str(error))

    def applied(self, result):
        self.show_rules(result)
        self.status.setText("Правила применены. Можно запускать поиск матча.")

    def reset(self):
        if self.busy:
            return
        if not self.request_admin():
            return
        self.status.setText("Снимаем собственные блокировки…")
        def work():
            remove_rules()
            return inspect_rules()
        self.run_job(work, self.reset_done, lock=True)

    def reset_done(self, result):
        self.show_rules(result)
        self.status.setText("Блокировки Deadlock Relay сняты. Другие правила не изменены.")

    def check_firewall(self):
        if self.busy:
            return
        if self.request_admin():
            self.verify_firewall(lambda: None)

    def show_rules(self, result):
        self.rules = result.get("rules", [])
        enabled = sum(bool(r.get("enabled")) for r in self.rules)
        try:
            off = bool(disabled_active_profiles(result))
            known = True
        except RuntimeError:
            off, known = False, False
        self.badge.setText("Статус неизвестен" if not known else "Firewall выключен" if off else f"Правил: {enabled}" if enabled else "Без блокировок")
        self.badge.setProperty("tone", "warning" if off or not known else "success")
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)
        self.firewall_note.setText("Не удалось определить состояние брандмауэра. Повтори проверку." if not known else "Брандмауэр активного сетевого профиля выключен. Включи его в Windows перед применением маршрута." if off else "Брандмауэр активного сетевого профиля включён.")
        self.render_table()

    def ping(self):
        if self.pinging:
            return
        self.pinging = True
        self.ping_btn.setEnabled(False)
        self.ping_btn.setText("Измеряем…")
        snapshot = list(self.pops)
        generation = self.generation
        def work():
            with ThreadPoolExecutor(max_workers=8) as executor:
                values = list(executor.map(lambda p: (p.code, ping_ip(p.ips[0])), snapshot))
            return generation, dict(values)
        self.run_job(work, self.ping_done, finished=self.ping_finished)

    def ping_done(self, result):
        generation, values = result
        if generation == self.generation:
            self.latencies = values
            self.render_table()

    def ping_finished(self):
        self.pinging = False
        self.ping_btn.setEnabled(True)
        self.ping_btn.setText("Проверить пинг")

    def elevate(self):
        if self.jobs:
            self.error("Дождись завершения текущих операций.")
            return
        import ctypes
        import subprocess
        self.save()
        args = "" if getattr(sys, "frozen", False) else subprocess.list2cmdline([str(ROOT / "main.py")])
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, args, str(ROOT), 1)
        if result > 32:
            self.close()
        else:
            self.error("Запуск с повышенными правами отменён или не удался.")

    def closeEvent(self, event):
        if self.jobs:
            self.status.setText("Дождись завершения операций перед закрытием.")
            event.ignore()
            return
        self.save()
        event.accept()

    def resizeEvent(self, event):
        if hasattr(self, "theme_fade"):
            self.theme_fade.finish()
        super().resizeEvent(event)
        if hasattr(self, "preset_grid"):
            columns = 4 if self.width() >= 1080 else 2
            if getattr(self, "preset_columns", None) == columns:
                return
            self.preset_columns = columns
            while self.preset_grid.count():
                self.preset_grid.takeAt(0)
            for i, b in enumerate(self.preset_buttons.values()):
                self.preset_grid.addWidget(b, i // columns, i % columns)
            self.preset_grid.invalidate()


def prepare_app(app):
    app.setStyle("Fusion")
    # Explicit system font loading also supports the offscreen Qt test platform on Windows.
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name in ["segoeui.ttf", "seguisb.ttf", "segoeuib.ttf"]:
        if (fonts / name).is_file():
            QFontDatabase.addApplicationFont(str(fonts / name))
    app.setFont(QFont("Segoe UI", 10))
    apply_theme(app, "dark")


def launch(offline=False):
    app = QApplication.instance() or QApplication(sys.argv)
    prepare_app(app)
    DATA.mkdir(parents=True, exist_ok=True)
    instance_lock = QLockFile(str(DATA / "instance.lock"))
    if not instance_lock.tryLock(2500):
        QMessageBox.information(None, "Deadlock Relay", "Приложение уже запущено. Открой существующее окно.")
        return 0
    window = Window(offline=offline)
    window.show()
    return app.exec()
