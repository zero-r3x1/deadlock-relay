from __future__ import annotations

import base64
import ctypes
import json
import os
from pathlib import Path
import subprocess

from .core import GROUP


def is_admin() -> bool:
    return os.name == "nt" and bool(ctypes.windll.shell32.IsUserAnAdmin())


def powershell(script: str, timeout=90):
    executable = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    prefix = "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
    encoded = base64.b64encode((prefix + script).encode("utf-16le")).decode("ascii")
    result = subprocess.run([str(executable), "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                            capture_output=True, encoding="utf-8", errors="replace", timeout=timeout,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[-1800:] or "Ошибка Windows Firewall")
    return json.loads(result.stdout.strip() or "null")


def inspect_rules():
    return powershell(f"""
$p = New-Object -ComObject HNetCfg.FwPolicy2
$items = @($p.Rules | Where-Object {{ $_.Grouping -eq '{GROUP}' }} | ForEach-Object {{
    @{{name=$_.Name; program=$_.ApplicationName; ips=$_.RemoteAddresses; enabled=$_.Enabled; action=$_.Action; direction=$_.Direction; profiles=$_.Profiles; protocol=$_.Protocol}}
}})
@{{rules=$items; currentProfiles=$p.CurrentProfileTypes; enabledProfiles=@(1,2,4 | ForEach-Object {{ @{{profile=$_; enabled=$p.FirewallEnabled($_)}} }})}} | ConvertTo-Json -Depth 5 -Compress
""")


def disabled_active_profiles(result):
    if not isinstance(result, dict):
        raise RuntimeError("Не удалось проверить состояние брандмауэра.")
    current = result.get("currentProfiles", 0)
    entries = result.get("enabledProfiles", [])
    if (not isinstance(current, int) or isinstance(current, bool)
            or not isinstance(entries, list)
            or any(not isinstance(p, dict) or type(p.get("profile")) is not int
                   or type(p.get("enabled")) is not bool for p in entries)):
        raise RuntimeError("Не удалось проверить состояние брандмауэра.")
    profiles = {p["profile"]: p["enabled"] for p in entries}
    active = [p for p in (1, 2, 4) if current & p]
    if not active or any(p not in profiles for p in active):
        raise RuntimeError("Не удалось проверить состояние брандмауэра. Повтори проверку в настройках.")
    return [p for p in active if not profiles[p]]


def enable_firewall():
    if not is_admin():
        raise PermissionError("Для включения брандмауэра нужны права администратора.")
    powershell("""
$p = New-Object -ComObject HNetCfg.FwPolicy2
foreach ($profile in @(1,2,4)) {
    if (($p.CurrentProfileTypes -band $profile) -and -not $p.FirewallEnabled($profile)) {
        $p.FirewallEnabled($profile) = $true
    }
}
'null'
""")
    result = inspect_rules()
    if disabled_active_profiles(result):
        raise RuntimeError("Windows не разрешила включить брандмауэр. Проверь настройки или политику организации.")
    return result


def apply_rules(plan: list[dict], program: str):
    if not is_admin():
        raise PermissionError("Перезапустите приложение от имени администратора для изменения правил.")
    path = Path(program)
    if not path.is_file() or path.name.lower() != "deadlock.exe":
        raise ValueError("Укажите существующий deadlock.exe в папке игры")
    if not plan:
        remove_rules()
        return inspect_rules()
    # Encode data rather than interpolating paths or API strings as shell code.
    payload = base64.b64encode(json.dumps({"program": str(path.resolve()), "rules": plan}).encode()).decode()
    return powershell(f"""
$data = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{payload}')) | ConvertFrom-Json
$p = New-Object -ComObject HNetCfg.FwPolicy2
foreach ($profile in @(1,2,4)) {{ if (($p.CurrentProfileTypes -band $profile) -and -not $p.FirewallEnabled($profile)) {{ throw 'Брандмауэр активного сетевого профиля выключен. Включите его в настройках Windows.' }} }}
$old = @($p.Rules | Where-Object {{ $_.Grouping -eq '{GROUP}' }})
$created = [Collections.Generic.List[string]]::new()
$removed = [Collections.Generic.List[object]]::new()
$batch = [Guid]::NewGuid().ToString('N')
try {{
    foreach ($item in $data.rules) {{
        $r = New-Object -ComObject HNetCfg.FWRule
        $r.Name = 'DeadlockRelay_' + $batch + '_' + $item.code
        $r.Grouping = '{GROUP}'
        $r.Description = 'Deadlock Relay: outgoing relay restriction for Deadlock only'
        $r.ApplicationName = $data.program
        $r.Direction = 2; $r.Action = 0; $r.Protocol = 256; $r.Profiles = 2147483647
        $r.RemoteAddresses = ($item.ips -join ','); $r.Enabled = $true
        $p.Rules.Add($r)
        $created.Add($r.Name)
    }}
    foreach ($r in $old) {{ $p.Rules.Remove($r.Name); $removed.Add($r) }}
}} catch {{
    $original = $_
    foreach ($r in $removed) {{ try {{ $p.Rules.Add($r) }} catch {{}} }}
    foreach ($name in $created) {{ try {{ $p.Rules.Remove($name) }} catch {{}} }}
    throw $original
}}
@{{count=$created.Count}} | ConvertTo-Json -Compress
""")


def remove_rules():
    if not is_admin():
        raise PermissionError("Для снятия блокировок нужны права администратора")
    return powershell(f"""
$p = New-Object -ComObject HNetCfg.FwPolicy2
$names = @($p.Rules | Where-Object {{ $_.Grouping -eq '{GROUP}' }} | ForEach-Object {{ $_.Name }})
foreach ($name in $names) {{ $p.Rules.Remove($name) }}
@{{removed=$names.Count}} | ConvertTo-Json -Compress
""")


def ping_ip(ip: str) -> int | None:
    # .NET ICMP has a bounded timeout and does not rely on localized ping.exe text.
    import ipaddress
    ip = str(ipaddress.IPv4Address(ip))
    try:
        return powershell(f"""
$ping = [Net.NetworkInformation.Ping]::new()
try {{ $r=$ping.Send('{ip}',900); if ($r.Status -eq 'Success') {{ [int]$r.RoundtripTime | ConvertTo-Json }} else {{ 'null' }} }} finally {{ $ping.Dispose() }}
""", timeout=5)
    except (RuntimeError, subprocess.TimeoutExpired):
        return None
