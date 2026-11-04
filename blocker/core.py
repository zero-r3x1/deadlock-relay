from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

API = "https://api.steampowered.com/ISteamApps/GetSDRConfig/v1/?appid=1422450"
GROUP = "DeadlockRelay.Managed.v1"
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DATA = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DeadlockRelay"


@dataclass(frozen=True)
class Pop:
    code: str
    name: str
    ips: tuple[str, ...]
    region: str


US = {"atl", "dfw", "iad", "lax", "ord", "sea", "eat", "mwh", "jfk"}
NORTH = {"sto", "sto2", "dsto", "hel"}
EU = {"ams", "fra", "fsn", "dfra", "vie", "dvie", "lhr", "dlhr", "par", "mad", "waw", "sto", "sto2", "dsto", "hel"}
PRESETS = {
    "ru": ("Только RU", "Приближение · Стокгольм", {"sto", "sto2", "dsto"},
           "В API нет российских relay. Оставляем Стокгольм — это приближение, а не отдельный RU-сервер. Русскоязычный состав матча не гарантирован."),
    "eu": ("Только EU", "Европа · без Стокгольма", EU - {"sto", "sto2", "dsto"},
           "Европейские relay, кроме Стокгольма. Игроки из России могут подключаться через европейские точки; исключить их невозможно."),
    "us": ("Только US", "Соединённые Штаты", US,
           "Оставляем только опубликованные Valve relay в США. Гражданство и язык игроков не определяются местом подключения."),
    "cn": ("Только Китай", "Приближение · Гонконг", {"hkg", "hkg4"},
           "Материковых китайских relay в текущей конфигурации Deadlock нет. Используем Гонконг. Это не отдельный китайский пул матчмейкинга."),
}


def region_for(code: str, name: str) -> str:
    if code in US:
        return "US"
    if code in EU:
        return "EU / Север" if code in NORTH else "EU"
    if code.startswith("hkg") or "China" in name:
        return "Китай / HK"
    if code in {"eze", "gru", "lim", "scl"}:
        return "Южная Америка"
    if code == "syd":
        return "Океания"
    if code == "jnb":
        return "Африка"
    return "Азия / прочие"


def parse_config(raw: dict) -> list[Pop]:
    if not isinstance(raw, dict) or not isinstance(raw.get("pops"), dict):
        raise ValueError("Valve вернул неизвестный формат конфигурации")
    try:
        revision = int(raw.get("revision", 0))
        if isinstance(raw.get("revision"), bool) or not 0 < revision < 32503680000:
            raise ValueError()
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Некорректная ревизия конфигурации Valve") from None
    result = []
    for code, item in raw["pops"].items():
        if not isinstance(code, str) or not re.fullmatch(r"[a-z0-9_-]{1,24}", code):
            raise ValueError("Некорректный код relay")
        if not isinstance(item, dict) or not isinstance(item.get("relays", []), list):
            raise ValueError("Некорректное описание relay")
        ips = set()
        for relay in item.get("relays", []):
            if not isinstance(relay, dict):
                raise ValueError("Некорректный адрес relay")
            if relay.get("ipv4"):
                if not isinstance(relay["ipv4"], str):
                    raise ValueError("Некорректный IPv4 в конфигурации")
                address = ipaddress.ip_address(relay["ipv4"])
                if address.version != 4 or not address.is_global:
                    raise ValueError("Непубличный IPv4 в конфигурации")
                ips.add(str(address))
        if ips:
            name = str(item.get("desc", code))
            result.append(Pop(code, name, tuple(sorted(ips)), region_for(code, name)))
    if not result:
        raise ValueError("В конфигурации нет доступных relay")
    return sorted(result, key=lambda p: (p.region, p.name))


def normalize_settings(raw):
    if not isinstance(raw, dict):
        raw = {}
    settings = {
        "game": raw.get("game") if isinstance(raw.get("game"), str) else "",
        "theme": raw.get("theme") if raw.get("theme") in ("dark", "light") else "dark",
        "motion": raw.get("motion") if isinstance(raw.get("motion"), bool) else True,
        "preset": raw.get("preset") if isinstance(raw.get("preset"), str) and raw.get("preset") in PRESETS else "",
        "custom": {},
    }
    allowed = raw.get("allowed")
    if isinstance(allowed, list) and all(isinstance(code, str) for code in allowed):
        settings["allowed"] = allowed
    custom = raw.get("custom")
    if isinstance(custom, dict):
        settings["custom"] = {name: codes for name, codes in custom.items()
                              if isinstance(name, str) and name.strip() and isinstance(codes, list)
                              and all(isinstance(code, str) for code in codes)}
    return settings


def atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def fetch_config() -> dict:
    request = urllib.request.Request(API, headers={"User-Agent": "DeadlockRelay/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = json.load(response)
    parse_config(raw)
    atomic_json(DATA / "sdr-cache.json", raw)
    return raw


def cached_config() -> tuple[dict, str]:
    for path, source in [(DATA / "sdr-cache.json", "Кэш"), (ROOT / "assets/sdr-deadlock.json", "Встроенный снимок")]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
            parse_config(raw)
            return raw, source
        except (OSError, ValueError, KeyError):
            continue
    raise ValueError("Нет конфигурации relay. Подключитесь к интернету.")


def build_plan(pops: list[Pop], allowed: set[str]) -> list[dict]:
    known = {p.code for p in pops}
    if not allowed or not allowed <= known:
        raise ValueError("Выберите хотя бы одну доступную точку; пресет содержит неизвестные relay")
    # Never block an IP shared with an allowed POP.
    protected = {ip for p in pops if p.code in allowed for ip in p.ips}
    return [{"code": p.code, "ips": sorted(set(p.ips) - protected)}
            for p in pops if p.code not in allowed and set(p.ips) - protected]


def find_game() -> str:
    roots = []
    if sys.platform == "win32":
        import winreg
        for hive, key, field in [(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                 (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")]:
            try:
                with winreg.OpenKey(hive, key) as handle:
                    roots.append(Path(winreg.QueryValueEx(handle, field)[0]))
            except OSError:
                pass
    roots.append(Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Steam")
    for root in list(roots):
        try:
            text = (root / "steamapps/libraryfolders.vdf").read_text(encoding="utf-8")
            roots.extend(Path(p.replace("\\\\", "\\")) for p in re.findall(r'"path"\s+"([^"]+)"', text))
        except OSError:
            pass
    for root in roots:
        candidate = root / "steamapps/common/Deadlock/game/bin/win64/deadlock.exe"
        if candidate.is_file():
            return str(candidate.resolve())
    return ""
