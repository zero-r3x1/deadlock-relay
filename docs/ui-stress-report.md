# Break UI + Animate — Deadlock Relay

## Scope and source

Skills read from https://github.com/emilkowalski/skills/tree/main/skills/break-ui and https://github.com/emilkowalski/skills/tree/main/skills/animate, including CATALOG.md and RECIPES.md. Applied to the existing Qt desktop interface; browser-only instructions were adapted to native Qt captures. No browser, firewall write, or production test data was used.

The Break UI playbook explicitly requires reporting before fixing. Findings below are intentionally not patched by this review. Animation implementation is independent.

## Rendered-data map

| Field | Boundary | Limit / optional |
|---|---|---|
| Relay code | Valve pops key → parse_config | 1–24 ASCII characters, required |
| City / description | Valve pops.desc | Unbounded; optional, missing falls back to code but empty string stays empty |
| IPv4 count / tooltips | Valve relays.ipv4 | Public IPv4 validation; list length unbounded |
| Region | region_for | Fixed set of labels |
| Ping | ping_ip → latencies | Integer milliseconds or None; not sampled in stress harness |
| Firewall text | inspect_rules → rule_status | Three local labels; real system operations disabled in harness |
| Revision / date / source | API revision, cache label | Revision presence checked; no explicit date range schema |
| Total / allowed / summary | pops, allowed | Collection length; no grouping of large numbers |
| Preset label / explanation | PRESETS | Fixed local text |
| Custom preset name | settings.custom, input dialog | New names truncated to 60 chars; imported settings have no schema limit |
| Selected codes | settings.allowed / custom preset | Intersection with published codes |
| Game path | detected Steam path / line edit | No explicit text limit; must exist and end in deadlock.exe when applying |
| Status, errors, paths | operations / DATA | Wrapped labels or dialogs; text length not explicitly capped everywhere |
| List length | parsed pops / search | No matches possible; valid API list must not be empty |

Images, avatars, money, email fields, browser zoom, mobile touch, and RTL layout are not product features. They were not simulated as if supported. Test widths reflect the native supported minimum (1080px), ordinary desktop (1320px), and wide desktop (1920px). 200% means doubled font sizes, not a claim about Windows DPI testing.

## What broke

| # | Severity | Field / worst case | Verified result | Proposed fix / location |
|---|---|---|---|---|
| 1 | Broken | All text doubled to 200% | Sidebar titles, logo, preset details and table headers clip. Text can no longer be read in full. | Compute minimum sizes from font metrics; let cards grow; reflow controls. `blocker/ui.py:144`, `blocker/ui.py:148`, `blocker/ui.py:713`; `blocker/style.qss`: fixed control sizing. |
| 2 | Fragile | Custom preset name of 60 plausible Cyrillic characters with underscores | Selected name is clipped; combo has no tooltip with its full value. Action buttons remain reachable. | Full-name tooltip and content-sized popup, without expanding the whole form. `blocker/ui.py:536` (reload_custom). |
| 3 | Ugly | Exactly one available relay | Counter says “1 точек”. | Russian plural rules or neutral “Точки: 1”. `blocker/ui.py:490` (update_selection). |
| 4 | Fragile | Search returns zero matches | Empty table with no explanation; total counter still refers to all loaded entries. | Explicit “Ничего не найдено” and clear-filter action; visible/total count. `blocker/ui.py:473` (filter_rows). |
| 5 | Fragile | Long realistic provider name / unbroken backbone identifier | Row elides its title; tooltip contains IPs only, so the full title cannot be recovered there. | Include full title and code alongside IPs in tooltip. `blocker/ui.py:434` (render_table). |

All five were visually verified in native offscreen Qt captures. No code change was made to simulate a break; fixtures enter through install_config and the normal preset/latency/search data boundaries.

## Decisions

- Prefer full title + tooltip for long relay names, keeping compact rows.
- Prefer a neutral count label over maintaining Russian inflection rules.
- For 200% text, allow taller cards and scroll the content; preserve access to the persistent action bar.

## What held up

- Normal and worst-case desktop layouts keep save/delete/apply controls reachable at supported widths.
- 0ms, 999ms and missing ICMP results render without invalid numbers.
- CJK/Cyrillic and literal HTML-like text remain text; no markup execution.
- Empty string names retain a relay code as an identifier in the table.
- Search/no results does not delete the chosen route.
- Single relay and 1,000-row capacity fixtures render without crashes.
- 1,000-row full installation/render took roughly 92–176 ms in the capture run. This measures synchronous fixture rendering, not scroll FPS; it is a capacity check, not an expected current Valve dataset size.
- Normal data remains at 33 relay points; no synthetic data enters the release bundle.

## Dev toggle

Run `.venv/Scripts/python tools/ui_stress.py`. Toggle: Demo data / Worst case / Empty / One / 1,000 rows, plus Text 100% / 200%. This standalone development window uses a temporary settings directory and disables system operations. It is excluded from PyInstaller's entry-point dependency graph.

Capture command: `.venv/Scripts/python tools/ui_stress.py --capture <directory>`.

## Motion shipped

- Gate: occasional/tens-per-day mouse press; purpose: feedback. No animated navigation, reading data, or keyboard activation.
- Qt QPropertyAnimation on button opacity only: 0.90 → 1, 160ms, cubic-bezier(0.23, 1, 0.32, 1).
- Interrupted release stops at its current value; hide/disable restores opacity. Touch-synthesized mouse presses are not animated.
- Windows client-area animation preference and a persistent application setting control motion. No animation library was installed.
- New tests cover mouse completion, keyboard activation, reduced motion, and disabling mid-press.
- Native offscreen tests confirm state/timing behavior. Subjective feel and touch behavior on physical hardware remain manual checks.
