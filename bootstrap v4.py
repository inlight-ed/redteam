#!/usr/bin/env python3
# bootstrap4.py — verify_fingerprint + docker-compose + check_artifacts
import os
from pathlib import Path

FILES = {}

# ══════════════════════════════════════════════════════════════════
# 1. tools/verify_fingerprint.py
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/tools/verify_fingerprint.py"] = '''\
"""
Проверка TLS/JA3/JA4/HTTP2 fingerprint через публичные echo-эндпоинты.

Режимы:
  --direct          — без прокси, "сырой" fingerprint Playwright
  --via-proxy       — через impersonate-proxy (127.0.0.1:8080)
  --via-proxy-pysaint — через psaintelligence/impersonate-proxy (127.0.0.1:8899)
  --compare         — сравнить direct и via-proxy с эталоном Chrome

Эталонные значения Chrome 141 (обновлять при смене версии):
  JA4:       t13d1517h2_8daaf6152771_cb7bf5808d99 (пример)
  Akamai H2: 1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p
  Extensions count: ~15-19 (включая GREASE)
  GREASE:    всегда присутствует

Зависимости: httpx, rich
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

import httpx
from rich.console import Console
from rich.table import Table

console = Console()

ENDPOINTS = {
    "tls_peet": "https://tls.peet.ws/api/all",
    "tlsinfo": "https://tlsinfo.me/json",
}

# Эталон Chrome 141 — заменить на актуальные значения,
# снятые с реального Chrome через tls.peet.ws
REFERENCE_CHROME = {
    "ja4": "t13d1517h2_8daaf6152771_cb7bf5808d99",
    "ja3_hash": "cd08e31494f9531f560d64c695473da9",
    "akamai_h2": "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p",
    "extensions_count": 17,
    "has_grease": True,
    "cipher_suites_count": 16,
    "http2_settings_count": 5,  # 4 params + GREASE
}


def parse_tls_peet(data: dict) -> dict:
    """Извлекает JA3/JA4/HTTP2 из ответа tls.peet.ws."""
    tls = data.get("tls", {})
    http2 = data.get("http2", {})
    extensions = tls.get("extensions", [])
    return {
        "ja3_hash": tls.get("ja3_hash"),
        "ja4": tls.get("ja4"),
        "ja3_raw": tls.get("ja3"),
        "extensions_count": len(extensions),
        "has_grease": any(
            e.get("name", "").startswith("GREASE")
            for e in extensions
        ),
        "cipher_suites_count": len(tls.get("ciphers", [])),
        "akamai_h2": http2.get("akamai_fingerprint"),
        "http2_settings_count": len(
            [f for f in http2.get("sent_frames", [])
             if f.get("frame_type") == "SETTINGS"]
        ),
        "tls_version": tls.get("tls_version"),
        "alpn": tls.get("alpn"),
    }


def parse_tlsinfo(data: dict) -> dict:
    """Извлекает JA3/JA4 из ответа tlsinfo.me."""
    return {
        "ja3": data.get("ja3"),
        "ja3_r": data.get("ja3_r"),
        "ja4": data.get("ja4"),
        "ja4_r": data.get("ja4_r"),
    }


def fetch_fingerprint(
    client: httpx.Client,
    url: str,
    endpoint_type: str = "tls_peet",
) -> Optional[dict]:
    try:
        r = client.get(url, timeout=20)
        r.raise_for_status()
        raw = r.json()
        if endpoint_type == "tls_peet":
            return parse_tls_peet(raw)
        return parse_tlsinfo(raw)
    except Exception as e:
        console.print(f"[red]Ошибка {url}: {e}[/red]")
        return None


def run_direct() -> dict:
    """Запросы без прокси."""
    console.print("[yellow]→ Direct (no proxy)[/yellow]")
    result = {}
    with httpx.Client(follow_redirects=True) as client:
        result["tls_peet"] = fetch_fingerprint(
            client, ENDPOINTS["tls_peet"], "tls_peet"
        )
        result["tlsinfo"] = fetch_fingerprint(
            client, ENDPOINTS["tlsinfo"], "tlsinfo"
        )
    return result


def run_via_proxy(proxy_url: str, verify: bool = False) -> dict:
    """Запросы через impersonate-proxy."""
    console.print(f"[green]→ Via proxy {proxy_url}[/green]")
    result = {}
    with httpx.Client(
        proxy=proxy_url,
        verify=verify,
        follow_redirects=True,
        timeout=30,
    ) as client:
        result["tls_peet"] = fetch_fingerprint(
            client, ENDPOINTS["tls_peet"], "tls_peet"
        )
        result["tlsinfo"] = fetch_fingerprint(
            client, ENDPOINTS["tlsinfo"], "tlsinfo"
        )
    return result


def print_table(data: dict, label: str) -> None:
    table = Table(title=f"Fingerprint — {label}")
    table.add_column("Параметр", style="cyan")
    table.add_column("Значение", style="white")
    table.add_column("Эталон Chrome", style="magenta")
    table.add_column("Match", style="green")

    tp = data.get("tls_peet") or {}
    ti = data.get("tlsinfo") or {}

    checks = [
        ("JA4 (tls.peet)", tp.get("ja4"), REFERENCE_CHROME["ja4"]),
        ("JA3 hash", tp.get("ja3_hash"), REFERENCE_CHROME["ja3_hash"]),
        ("Akamai H2", tp.get("akamai_h2"), REFERENCE_CHROME["akamai_h2"]),
        ("Extensions count", tp.get("extensions_count"),
         REFERENCE_CHROME["extensions_count"]),
        ("Has GREASE", tp.get("has_grease"), REFERENCE_CHROME["has_grease"]),
        ("Cipher suites", tp.get("cipher_suites_count"),
         REFERENCE_CHROME["cipher_suites_count"]),
        ("JA4 (tlsinfo.me)", ti.get("ja4"), REFERENCE_CHROME["ja4"]),
    ]

    for name, val, ref in checks:
        if val is None:
            match = "[dim]—[/dim]"
            val_str = "[dim]—[/dim]"
        elif isinstance(ref, bool):
            match = "[green]✓[/green]" if val == ref else "[red]✗[/red]"
            val_str = str(val)
        elif isinstance(ref, int):
            match = "[green]✓[/green]" if val == ref else "[yellow]~[/yellow]"
            val_str = str(val)
        else:
            match = "[green]✓[/green]" if val == ref else "[red]✗[/red]"
            val_str = str(val)[:50]

        table.add_row(name, val_str, str(ref), match)

    console.print(table)


def print_comparison(direct: dict, via_proxy: dict) -> None:
    table = Table(title="Direct vs Proxy")
    table.add_column("Параметр", style="cyan")
    table.add_column("Direct", style="yellow")
    table.add_column("Via proxy", style="green")

    tp_d = direct.get("tls_peet") or {}
    tp_p = via_proxy.get("tls_peet") or {}

    for key in ["ja4", "ja3_hash", "akamai_h2",
                "extensions_count", "has_grease"]:
        table.add_row(
            key,
            str(tp_d.get(key, "—"))[:40],
            str(tp_p.get(key, "—"))[:40],
        )
    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="Verify TLS/JA3/JA4/HTTP2 fingerprint"
    )
    parser.add_argument("--direct", action="store_true",
                        help="Проверка без прокси")
    parser.add_argument("--via-proxy", action="store_true",
                        help="Через impersonate-proxy (ytkoka, порт 8080)")
    parser.add_argument("--via-proxy-pysaint", action="store_true",
                        help="Через psaintelligence/impersonate-proxy (порт 8899)")
    parser.add_argument("--proxy-url", default="http://127.0.0.1:8080",
                        help="URL прокси")
    parser.add_argument("--compare", action="store_true",
                        help="Сравнить direct и via-proxy")
    parser.add_argument("--no-verify", action="store_true",
                        help="Отключить проверку SSL (для MITM-прокси)")
    args = parser.parse_args()

    console.print("[bold]Fingerprint Verification[/bold]\\n")

    direct = via = None

    if args.direct or args.compare or not (args.via_proxy or args.via_proxy_pysaint):
        direct = run_direct()
        print_table(direct, "Direct")

    if args.via_proxy:
        via = run_via_proxy(args.proxy_url, verify=not args.no_verify)
        print_table(via, "Via ytkoka/impersonate-proxy")

    if args.via_proxy_pysaint:
        via = run_via_proxy("http://127.0.0.1:8899", verify=False)
        print_table(via, "Via psaintelligence/impersonate-proxy")

    if args.compare and direct and via:
        print_comparison(direct, via)

    # Итоговый вердикт
    console.print()
    if direct and direct.get("tls_peet"):
        tp = direct["tls_peet"]
        if tp.get("has_grease") and tp.get("extensions_count", 0) >= 10:
            console.print("[green]✓ Direct fingerprint выглядит как браузер[/green]")
        else:
            console.print("[red]✗ Direct fingerprint — не браузерный[/red]")
            console.print("  → Проверьте, что используется реальный Chromium")
            console.print("  → Возможно, прокси терминирует TLS (MITM)")


if __name__ == "__main__":
    main()
'''

# ══════════════════════════════════════════════════════════════════
# 2. docker-compose.yml — два варианта impersonate-proxy
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/docker-compose.yml"] = '''\
# Docker Compose для двух impersonate-proxy.
# Выберите один из двух — оба одновременно не нужны.
#
# Вариант A: ytkoka/impersonate-proxy (Go + uTLS)
#   - Точный контроль JA3/JA4, HTTP/2 SETTINGS
#   - Порт 8080 (proxy), 8081 (management API)
#   - Рекомендуется для red-team
#
# Вариант B: psaintelligence/impersonate-proxy (Python + curl_cffi)
#   - Проще, но меньше контроля
#   - Порт 8899
#   - Рекомендуется для быстрого старта

version: "3.9"

services:
  # ── Вариант A: ytkoka/impersonate-proxy ──
  impersonate-proxy-go:
    image: ghcr.io/ytkoka/impersonate-proxy:latest
    container_name: impersonate-proxy-go
    ports:
      - "127.0.0.1:8080:8080"   # proxy
      - "127.0.0.1:8081:8081"   # management API
    volumes:
      - ./config.docker.yaml:/config.yaml:ro
      - ./data:/data
    restart: unless-stopped
    profiles:
      - go

  # ── Вариант B: psaintelligence/impersonate-proxy ──
  impersonate-proxy-pysaint:
    image: ghcr.io/psaintelligence/impersonate-proxy:latest
    container_name: impersonate-proxy-pysaint
    ports:
      - "127.0.0.1:8899:8899"
    volumes:
      - ./certs:/root/.config/impersonate-proxy
    environment:
      - IMPERSONATE_PROXY_IMPERSONATE=chrome
      - IMPERSONATE_PROXY_PORT=8899
    restart: unless-stopped
    profiles:
      - pysaint

# ── Использование ──
#
# Вариант A (Go):
#   docker compose --profile go up -d
#   → proxy:  http://127.0.0.1:8080
#   → API:    http://127.0.0.1:8081/api/config
#   → CA:     ./data/ca.crt
#
# Вариант B (Python):
#   docker compose --profile pysaint up -d
#   → proxy:  http://127.0.0.1:8899
#   → CA:     ./certs/ca.crt
#
# Остановка:
#   docker compose --profile go down
#   docker compose --profile pysaint down
'''

FILES["twitch-redteam/config.docker.yaml"] = '''\
# Конфигурация ytkoka/impersonate-proxy (Go).
# Для Docker: listen на 0.0.0.0, ca_cert/ca_key в /data.

listen: "0.0.0.0:8080"
mgmt_listen: "0.0.0.0:8081"

ca_cert: "/data/ca.crt"
ca_key: "/data/ca.key"

tls:
  preset: "chrome"
  # Альтернативы: firefox | safari | edge | ios | random | golang | custom
  #
  # Для custom mode — раскомментировать и заполнить:
  # custom_hello:
  #   cipher_suites: [...]
  #   extensions: [...]
  #   supported_groups: [...]
  #   signature_algorithms: [...]

http:
  header_order:
    - "Host"
    - "User-Agent"
    - "Accept"
    - "Accept-Language"
    - "Accept-Encoding"
    - "Sec-Ch-Ua"
    - "Sec-Ch-Ua-Mobile"
    - "Sec-Ch-Ua-Platform"
  # client_ip: "1.2.3.4"   # spoof X-Forwarded-For / True-Client-IP

http2:
  enabled: true
  settings:
    - { id: 1, val: 65536 }    # HEADER_TABLE_SIZE
    - { id: 2, val: 0 }        # ENABLE_PUSH
    - { id: 4, val: 6291456 }  # INITIAL_WINDOW_SIZE
    - { id: 6, val: 262144 }   # MAX_HEADER_LIST_SIZE
  window_update: 15663105
'''

FILES["twitch-redteam/config.docker.pysaint.yaml"] = '''\
# Конфигурация psaintelligence/impersonate-proxy (Python + curl_cffi).
# Управляется через ENV или CLI-флаги. Этот файл — для справки.

port: 8899
host: "0.0.0.0"
impersonate: "chrome"
cffi_defaults: true
strip_client_leak_headers: true
session_pool_max: 32
connect_timeout: 10.0
read_timeout: 300.0
ca_dir: "/root/.config/impersonate-proxy"
'''

# ══════════════════════════════════════════════════════════════════
# 3. tools/check_artifacts.py — обновлённый (согласованность)
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/tools/check_artifacts.py"] = '''\
"""
Полная проверка Red Team стека:

  1. Отсутствие CDP/WebDriver артефактов
  2. Function.prototype.toString для нативных функций
  3. Согласованность: navigator.platform vs navigator.userAgentData.platform
  4. Согласованность: WebGL vendor/renderer vs navigator.platform
  5. Согласованность: timezone vs locale vs user_agent
  6. Детерминированность canvas hash (один профиль → один hash)
  7. Проверка Page Visibility каскада

Запуск:
  python tools/check_artifacts.py
  python tools/check_artifacts.py --profile win_rtx3060_1080p
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

from core.fingerprint_manager import ProfilesBank, build_fingerprint_init_script
from humanizer.visibility import _INIT_SCRIPT as VISIBILITY_INIT_SCRIPT


ARTIFACTS = [
    "cdc_adoQ425bcd421573312",
    "__selenium_unwrapped",
    "__selenium_evaluate",
    "__webdriver_evaluate",
    "__webdriver_script_fn",
    "__driver_evaluate",
    "__fxdriver_evaluate",
    "_phantom",
    "callPhantom",
    "callSelenium",
    "domAutomation",
    "domAutomationController",
]


CHECK_SCRIPT = r"""
() => {
    const result = {
        cdp_artifacts_found: [],
        toString_native: false,
        platform: null,
        ua_data_platform: null,
        ua_data_brands: null,
        webgl_vendor: null,
        webgl_renderer: null,
        timezone: null,
        locale: null,
        user_agent: null,
        canvas_hash: null,
        visibility_state: null,
        visibility_hidden: null,
        has_focus: null,
        errors: [],
    };

    // 1. Артефакты
    for (const key of ['cdc_adoQ425bcd421573312',
                        '__selenium_unwrapped', '__webdriver_evaluate',
                        '__driver_evaluate', '__fxdriver_evaluate',
                        '_phantom', 'callPhantom', 'callSelenium',
                        'domAutomation', 'domAutomationController']) {
        if (key in window) result.cdp_artifacts_found.push(key);
    }

    // 2. toString
    try {
        const str = Function.prototype.toString.toString();
        result.toString_native = str.includes('[native code]');
    } catch (e) {
        result.errors.push('toString: ' + e.message);
    }

    // 3. navigator.platform
    result.platform = navigator.platform;

    // 4. navigator.userAgentData
    if (navigator.userAgentData) {
        result.ua_data_platform = navigator.userAgentData.platform;
        result.ua_data_brands = navigator.userAgentData.brands;
    }

    // 5. WebGL
    try {
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        if (gl) {
            const dbg = gl.getExtension('WEBGL_debug_renderer_info');
            if (dbg) {
                result.webgl_vendor = gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL);
                result.webgl_renderer = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
            }
        }
    } catch (e) {
        result.errors.push('webgl: ' + e.message);
    }

    // 6. Timezone + locale
    try {
        result.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch (e) {}
    result.locale = navigator.language;

    // 7. User-Agent
    result.user_agent = navigator.userAgent;

    // 8. Canvas hash
    try {
        const canvas = document.createElement('canvas');
        canvas.width = 200; canvas.height = 50;
        const ctx = canvas.getContext('2d');
        ctx.textBaseline = 'top';
        ctx.font = '14px Arial';
        ctx.fillStyle = '#f60';
        ctx.fillRect(125, 1, 62, 20);
        ctx.fillStyle = '#069';
        ctx.fillText('Fingerprint test', 2, 15);
        result.canvas_hash = canvas.toDataURL().slice(-32);
    } catch (e) {
        result.errors.push('canvas: ' + e.message);
    }

    // 9. Visibility
    result.visibility_state = document.visibilityState;
    result.visibility_hidden = document.hidden;
    result.has_focus = document.hasFocus();

    return result;
}
"""


def print_header(title: str) -> None:
    print()
    print("═" * 60)
    print(f"  {title}")
    print("═" * 60)


def check_artifacts(result: dict) -> bool:
    print_header("1. CDP / WebDriver артефакты")
    found = result.get("cdp_artifacts_found", [])
    if found:
        print(f"  ✗ Найдены артефакты: {found}")
        return False
    print("  ✓ Все артефакты удалены")
    return True


def check_to_string(result: dict) -> bool:
    print_header("2. Function.prototype.toString")
    if result.get("toString_native"):
        print("  ✓ toString возвращает [native code]")
        return True
    print("  ✗ toString не нативный")
    return False


def check_platform_consistency(result: dict) -> bool:
    print_header("3. navigator.platform vs userAgentData.platform")

    platform = result.get("platform")
    ua_platform = result.get("ua_data_platform")

    print(f"  navigator.platform:        {platform}")
    print(f"  userAgentData.platform:    {ua_platform}")

    if not ua_platform:
        print("  ⚠ userAgentData недоступен (проверьте CDP UA-CH sync)")
        return False

    # Маппинг платформ
    platform_map = {
        "Win32": "Windows",
        "Win64": "Windows",
        "MacIntel": "macOS",
        "Linux x86_64": "Linux",
        "Linux armv8l": "Linux",
    }
    expected = platform_map.get(platform, platform)

    if expected == ua_platform:
        print(f"  ✓ Согласовано: {platform} ↔ {ua_platform}")
        return True
    print(f"  ✗ РАССИНХРОН: {platform} → ожидается {expected}, "
          f"получено {ua_platform}")
    return False


def check_webgl_consistency(result: dict) -> bool:
    print_header("4. WebGL vendor/renderer vs platform")

    platform = result.get("platform", "")
    vendor = result.get("webgl_vendor") or ""
    renderer = result.get("webgl_renderer") or ""

    print(f"  platform:  {platform}")
    print(f"  WebGL vendor:   {vendor}")
    print(f"  WebGL renderer: {renderer}")

    if not vendor and not renderer:
        print("  ⚠ WebGL debug renderer недоступен")
        return False

    platform_map = {
        "Win32": ["ANGLE", "Direct3D", "D3D11"],
        "MacIntel": ["Apple", "Metal", "OpenGL"],
        "Linux x86_64": ["Mesa", "AMD", "NVIDIA", "Intel"],
    }
    expected_markers = platform_map.get(platform, [])

    if any(m.lower() in (vendor + renderer).lower()
           for m in expected_markers):
        print("  ✓ WebGL согласован с platform")
        return True

    if platform == "Win32" and "ANGLE" not in renderer:
        print("  ✗ Windows platform, но WebGL renderer не ANGLE/Direct3D")
        return False
    if platform == "MacIntel" and "Apple" not in vendor:
        print("  ✗ macOS platform, но WebGL vendor не Apple")
        return False

    print("  ⚠ Возможный рассинхрон WebGL и platform")
    return False


def check_timezone_locale(result: dict) -> bool:
    print_header("5. Timezone vs locale vs user_agent")

    tz = result.get("timezone", "")
    locale = result.get("locale", "")
    ua = result.get("user_agent", "")

    print(f"  timezone: {tz}")
    print(f"  locale:   {locale}")

    # Проверка: несоответствие европейского timezone и азиатского locale
    eu_tz = ["Europe/", "Atlantic/"]
    asia_tz = ["Asia/", "Australia/"]
    us_tz = ["America/"]

    issues = []

    if any(tz.startswith(t) for t in asia_tz) and locale.startswith("de-"):
        issues.append("Asia timezone + German locale")

    if any(tz.startswith(t) for t in us_tz) and locale.startswith("ja-"):
        issues.append("US timezone + Japanese locale")

    if "Linux" in ua and result.get("platform") == "Win32":
        issues.append("UA Linux vs platform Win32")

    if issues:
        for issue in issues:
            print(f"  ✗ {issue}")
        return False

    print("  ✓ Timezone, locale, UA согласованы")
    return True


def check_canvas_determinism(page, fp_profile) -> bool:
    print_header("6. Canvas hash — детерминированность")

    # Запрос canvas hash дважды
    hash1 = page.evaluate(
        "() => {"
        "  const c = document.createElement('canvas');"
        "  c.width = 200; c.height = 50;"
        "  const ctx = c.getContext('2d');"
        "  ctx.textBaseline = 'top';"
        "  ctx.fillStyle = '#f60';"
        "  ctx.fillRect(125, 1, 62, 20);"
        "  return c.toDataURL().slice(-32);"
        "}"
    )
    # Второй запрос
    hash2 = page.evaluate(
        "() => {"
        "  const c = document.createElement('canvas');"
        "  c.width = 200; c.height = 50;"
        "  const ctx = c.getContext('2d');"
        "  ctx.textBaseline = 'top';"
        "  ctx.fillStyle = '#f60';"
        "  ctx.fillRect(125, 1, 62, 20);"
        "  return c.toDataURL().slice(-32);"
        "}"
    )

    print(f"  Hash #1: {hash1}")
    print(f"  Hash #2: {hash2}")

    if hash1 == hash2:
        print("  ✓ Canvas hash детерминирован")
        return True
    print("  ✗ Canvas hash нестабилен — детектор пометит как аномалию")
    return False


def check_visibility(page) -> bool:
    print_header("7. Page Visibility каскад")

    from humanizer.visibility import VisibilityCascade

    cascade = VisibilityCascade(page)
    await cascade.install()

    # Регистрируем обработчики
    await page.evaluate("""
        () => {
            window.__vis_events = [];
            document.addEventListener('visibilitychange', () => {
                window.__vis_events.push({
                    hidden: document.hidden,
                    vs: document.visibilityState,
                    focus: document.hasFocus(),
                });
            });
        }
    """)

    await cascade.hide("tab_switch")
    await cascade.show("tab_switch")

    events = await page.evaluate("() => window.__vis_events")

    print(f"  События: {json.dumps(events, indent=4)}")

    if len(events) >= 2:
        hide_event = events[0]
        show_event = events[-1]
        ok = (hide_event.get("hidden") is True
              and hide_event.get("vs") == "hidden"
              and hide_event.get("focus") is False
              and show_event.get("hidden") is False
              and show_event.get("vs") == "visible"
              and show_event.get("focus") is True)
        if ok:
            print("  ✓ Каскад visibility корректен")
            return True
        print("  ✗ Каскад visibility некорректен")
        return False

    print(f"  ✗ Получено {len(events)} событий, ожидалось 2")
    return False


async def main():
    parser = argparse.ArgumentParser(
        description="Полная проверка Red Team стека"
    )
    parser.add_argument("--profile", default=None,
                        help="ID профиля из Profiles Bank")
    parser.add_argument("--url", default="about:blank",
                        help="URL для тестовой навигации")
    args = parser.parse_args()

    bank = ProfilesBank("config/profiles_bank.yaml")
    if args.profile:
        fp = next((p for p in bank.profiles if p.id == args.profile), None)
        if not fp:
            print(f"✗ Профиль {args.profile} не найден")
            return
    else:
        fp = bank.pick()

    print(f"Используемый профиль: {fp.id}")

    cdp_artifacts_js = Path(
        "humanizer/cdp_artifacts.js"
    ).read_text(encoding="utf-8")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport=fp.viewport,
            user_agent=fp.user_agent,
            locale="en-US",
            timezone_id=fp.pick_timezone(),
            device_scale_factor=fp.device_scale_factor,
            has_touch=fp.mobile,
            is_mobile=fp.mobile,
        )

        # Порядок init-скриптов — как в browser_factory.py
        await context.add_init_script(cdp_artifacts_js)
        await context.add_init_script(build_fingerprint_init_script(fp))
        await context.add_init_script(VISIBILITY_INIT_SCRIPT)

        page = await context.new_page()
        await page.goto(args.url)

        result = await page.evaluate(CHECK_SCRIPT)

        checks = [
            check_artifacts(result),
            check_to_string(result),
            check_platform_consistency(result),
            check_webgl_consistency(result),
            check_timezone_locale(result),
            await check_canvas_determinism(page, fp),
            await check_visibility(page),
        ]

        print()
        print("═" * 60)
        passed = sum(checks)
        total = len(checks)
        if passed == total:
            print(f"  РЕЗУЛЬТАТ: ✓ {passed}/{total} проверок пройдено")
        else:
            print(f"  РЕЗУЛЬТАТ: ✗ {passed}/{total} проверок пройдено")
        print("═" * 60)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
'''

# ══════════════════════════════════════════════════════════════════
# 4. tools/run_verify.sh — обёртка
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/tools/run_verify.sh"] = '''\
#!/usr/bin/env bash
# Полный цикл проверки Red Team стека.
set -e

cd "$(dirname "$0")/.."

echo "=== 1. Проверка артефактов и согласованности ==="
python tools/check_artifacts.py "$@"

echo
echo "=== 2. Проверка fingerprint (direct) ==="
python tools/verify_fingerprint.py --direct

echo
if docker ps --format '{{.Names}}' | grep -q impersonate-proxy; then
    echo "=== 3. Проверка fingerprint (via proxy) ==="
    python tools/verify_fingerprint.py --via-proxy --no-verify
else
    echo "=== 3. Proxy не запущен ==="
    echo "Запустите: docker compose --profile go up -d"
    echo "Затем:    python tools/verify_fingerprint.py --via-proxy --no-verify"
fi

echo
echo "=== Готово ==="
'''

FILES["twitch-redteam/tools/__init__.py"] = ""


def write_all():
    for rel, content in FILES.items():
        p = Path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        print(f"  ok {rel}")

    # Делаем shell-скрипт исполняемым
    os.chmod("twitch-redteam/tools/run_verify.sh", 0o755)
    print("  chmod +x twitch-redteam/tools/run_verify.sh")


if __name__ == "__main__":
    write_all()
    print()
    print("Done. Next steps:")
    print()
    print("  1. Установить зависимости:")
    print("     cd twitch-redteam && pip install httpx rich")
    print()
    print("  2. Проверить артефакты и согласованность (без прокси):")
    print("     python tools/check_artifacts.py")
    print()
    print("  3. Запустить impersonate-proxy:")
    print("     mkdir -p data && chown 65532:65532 data")
    print("     docker compose --profile go up -d")
    print()
    print("  4. Проверить fingerprint через прокси:")
    print("     python tools/verify_fingerprint.py --via-proxy --no-verify")
    print()
    print("  5. Сравнить direct vs proxy:")
    print("     python tools/verify_fingerprint.py --compare")
    print()
    print("  6. Полный цикл:")
    print("     bash tools/run_verify.sh")