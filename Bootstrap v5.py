#!/usr/bin/env python3
# bootstrap5.py — интеграция патченных браузеров
import os
from pathlib import Path

FILES = {}

# ══════════════════════════════════════════════════════════════════
# 1. core/browser_engine.py — абстракция движков
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/core/browser_engine.py"] = '''\
"""
Абстракция над движками браузеров.

Поддерживаемые движки:
  - playwright        — стандартный Playwright (baseline)
  - patchright        — патченный Playwright + Chromium (C++ патчи)
  - rebrowser         — Playwright + rebrowser-patches (Runtime.enable fix)
  - tilion             — Fortress stealth Chromium (CDP endpoint)
  - camoufox           — патченный Firefox (C++ патчи, без CDP)
  - invisible          — invisible_playwright + патченный Firefox

Каждый движок даёт:
  - launch(headless, args) -> Browser
  - install() -> None (установка бинарника)

Переключение — через config/engine.yaml.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional


ENGINES = {
    "playwright": {
        "module": "playwright.async_api",
        "install_cmd": None,
        "supports_cdp": True,
        "notes": "Baseline. Много automation tells.",
    },
    "patchright": {
        "module": "patchright.async_api",
        "install_cmd": "patchright install chromium",
        "supports_cdp": True,
        "notes": ("Патченный Playwright driver. Убирает Runtime.enable, "
                  "Console.enable, command flag leaks. "
                  "Только Chromium."),
    },
    "rebrowser": {
        "module": "rebrowser_playwright.async_api",
        "install_cmd": None,
        "supports_cdp": True,
        "notes": ("Playwright + rebrowser-patches. "
                  "Runtime.enable fix через изолированные контексты. "
                  "Drop-in replacement."),
    },
    "tilion": {
        "module": "tilion_fortress",
        "install_cmd": None,
        "supports_cdp": True,
        "notes": ("Fortress stealth Chromium. Патчи в C++ source. "
                  "Работает через CDP endpoint (connect_over_cdp). "
                  "Prebuilt binary, без сборки."),
    },
    "camoufox": {
        "module": "camoufox",
        "install_cmd": "python -m camoufox fetch",
        "supports_cdp": False,
        "notes": ("Патченный Firefox. C++ патчи для fingerprint. "
                  "Juggler вместо CDP. Не поддерживает CDP-команды."),
    },
    "invisible": {
        "module": "invisible_playwright",
        "install_cmd": "python -m invisible_playwright fetch",
        "supports_cdp": False,
        "notes": ("Stock Playwright + патченный Firefox binary. "
                  "Детерминированный seed. Не CDP."),
    },
}


@dataclass
class EngineInfo:
    name: str
    module: str
    install_cmd: Optional[str]
    supports_cdp: bool
    notes: str
    available: bool = False


def list_engines() -> list[EngineInfo]:
    result = []
    for name, meta in ENGINES.items():
        available = False
        try:
            __import__(meta["module"])
            available = True
        except ImportError:
            pass
        result.append(EngineInfo(name=name, **meta, available=available))
    return result


def get_engine_module(engine: str):
    """Возвращает модуль async_api для выбранного движка."""
    if engine not in ENGINES:
        raise ValueError(f"Unknown engine: {engine}")
    import importlib
    mod = importlib.import_module(ENGINES[engine]["module"])
    return mod


async def launch_engine(engine: str, headless: bool = True,
                        args: list = None, **kwargs):
    """
    Запускает браузер выбранного движка.
    Возвращает (playwright, browser).
    """
    if engine == "tilion":
        # tilion_fortress запускается через Fortress() и connect_over_cdp
        from tilion_fortress import Fortress
        from playwright.async_api import async_playwright
        fortress = Fortress()
        await fortress.start()
        pw = await async_playwright().start()
        browser = await pw.chromium.connect_over_cdp(fortress.cdp_url)
        return pw, browser, fortress

    if engine == "camoufox":
        from camoufox.async_api import AsyncCamoufox
        # camoufox не поддерживает CDP, но даёт похожий API
        # Возвращаем AsyncCamoufox как context manager
        return None, None, AsyncCamoufox(headless=headless, **kwargs)

    if engine == "invisible":
        from invisible_playwright.async_api import async_playwright
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=headless, args=args or [], **kwargs
        )
        return pw, browser, None

    # playwright / patchright / rebrowser — стандартный API
    mod = get_engine_module(engine)
    pw = await mod.async_playwright().start()
    browser = await pw.chromium.launch(
        headless=headless, args=args or [], **kwargs
    )
    return pw, browser, None
'''

# ══════════════════════════════════════════════════════════════════
# 2. core/browser_factory.py — обновлённый (с engine)
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/core/browser_factory.py"] = '''\
from humanizer.visibility import _INIT_SCRIPT as VISIBILITY_INIT_SCRIPT
from core.fingerprint_manager import build_fingerprint_init_script
from core.browser_engine import launch_engine, list_engines, ENGINES
import asyncio
from pathlib import Path
import yaml


def _load_cdp_artifacts_script() -> str:
    path = Path(__file__).parent.parent / "humanizer" / "cdp_artifacts.js"
    return path.read_text(encoding="utf-8")


def _load_engine_config() -> str:
    path = Path("config/engine.yaml")
    if not path.exists():
        return "playwright"
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    return cfg.get("engine", "playwright")


class BrowserFactory:
    def __init__(self, headless=True, engine: str = None):
        self.headless = headless
        self.engine = engine or _load_engine_config()
        self._playwright = None
        self._browser = None
        self._fortress = None
        self._camoufox_cm = None
        self._lock = asyncio.Lock()
        self._cdp_artifacts_js = _load_cdp_artifacts_script()

        if self.engine not in ENGINES:
            raise ValueError(f"Unknown engine: {self.engine}")

    async def start(self):
        """Запуск браузера выбранного движка."""
        if self.engine == "camoufox":
            # Camoufox работает как async context manager
            from camoufox.async_api import AsyncCamoufox
            self._camoufox_cm = AsyncCamoufox(headless=self.headless)
            self._browser = await self._camoufox_cm.__aenter__()
            return

        self._playwright, self._browser, self._fortress = await launch_engine(
            self.engine,
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

    async def create_context(self, profile, fp_profile=None):
        viewport = fp_profile.viewport if fp_profile else profile.viewport
        user_agent = fp_profile.user_agent if fp_profile else profile.user_agent
        timezone = fp_profile.pick_timezone() if fp_profile else profile.timezone
        locale = profile.locale
        is_mobile = fp_profile.mobile if fp_profile else (profile.platform == "mobile")
        dsf = fp_profile.device_scale_factor if fp_profile else 1.0

        async with self._lock:
            context = await self._browser.new_context(
                viewport=viewport,
                user_agent=user_agent,
                locale=locale,
                timezone_id=timezone,
                proxy={"server": profile.proxy} if profile.proxy else None,
                has_touch=is_mobile,
                is_mobile=is_mobile,
                device_scale_factor=dsf,
            )

        # Порядок init-скриптов критичен
        await context.add_init_script(self._cdp_artifacts_js)
        if fp_profile:
            await context.add_init_script(
                build_fingerprint_init_script(fp_profile)
            )
        await context.add_init_script(VISIBILITY_INIT_SCRIPT)

        return context

    async def close(self):
        if self.engine == "camoufox" and self._camoufox_cm:
            try:
                await self._camoufox_cm.__aexit__(None, None, None)
            except Exception:
                pass
            return
        if self._fortress:
            try:
                await self._fortress.stop()
            except Exception:
                pass
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
'''

# ══════════════════════════════════════════════════════════════════
# 3. config/engine.yaml — выбор движка
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/config/engine.yaml"] = """\
# Выбор движка браузера.
#
# Доступные:
#   playwright  — baseline (без патчей)
#   patchright  — патченный Playwright + Chromium (рекомендуется)
#   rebrowser   — Playwright + rebrowser-patches
#   tilion      — Fortress stealth Chromium (CDP endpoint)
#   camoufox    — патченный Firefox (C++, без CDP)
#   invisible   — stock Playwright + патченный Firefox binary
#
# Для Фаз 1-2 (baseline детекции): playwright
# Для Фаз 3-4 (humanizer + UA-CH): patchright
# Для Фазы 5 (патченный движок): patchright или tilion или camoufox
# Для сравнения движков: меняйте значение и перезапускайте

engine: "patchright"

# Дополнительные параметры для выбранного движка
options:
  patchright:
    # Рекомендация Patchright: использовать реальный Chrome, не Chromium
    channel: "chrome"          # "chrome" | "chromium" | null
    no_viewport: true           # Не переопределять viewport
    headless: false             # Headless detectable → headed
    persistent_context: false   # true для сохранения cookies между runs
    user_data_dir: null         # Путь для persistent context

  camoufox:
    headless: true
    geoip: true                 # Требует camoufox[geoip]
    os: "windows"               # windows | macos | linux
    humanize: true              # Built-in human-like mouse

  tilion:
    headless: true
    persona: null               # Кастомная persona (dict)

  rebrowser:
    channel: "chrome"
    headless: false

  playwright:
    headless: true
"""

# ══════════════════════════════════════════════════════════════════
# 4. requirements-patched.txt — зависимости для патченных движков
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/requirements-patched.txt"] = """\
# Базовые
playwright>=1.40
pyyaml>=6.0
httpx>=0.27
rich>=13.0

# Патченные движки (выберите один или несколько)
patchright>=1.58.0
# rebrowser-playwright>=1.40
# tilion-fortress>=151.0.0
# camoufox[geoip]>=0.4.0
# invisible-playwright>=1.40

# Для визуальной отладки (опционально)
# ipython>=8.0
"""

# ══════════════════════════════════════════════════════════════════
# 5. docker-compose-patched.yml — патченные браузеры в Docker
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/docker-compose-patched.yml"] = """\
# Docker Compose для патченных браузеров.
# Используется вместе с основным docker-compose.yml (impersonate-proxy).
#
# Профили:
#   patchright  — borski/patchright-docker (stealth Chromium)
#   tilion      — tilion/fortress (stealth Chromium, CDP endpoint)
#   camoufox    — yvv4docker/camoufox (patched Firefox)

version: "3.9"

services:
  # ── Patchright в Docker ──
  patchright:
    image: ghcr.io/borski/patchright-docker:latest
    container_name: patchright-browser
    profiles: [patchright]
    # Используется как CLI или script runner
    # Для серверного режима — см. tilion/fortress

  # ── Tilion Fortress (CDP endpoint) ──
  tilion-fortress:
    image: tilion/fortress:latest
    container_name: tilion-fortress
    ports:
      - "127.0.0.1:9222:9222"
    profiles: [tilion]
    # Подключение: p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    # Или через tilion_fortress.Fortress()

  # ── Camoufox в Docker ──
  camoufox:
    image: yvv4docker/camoufox:latest
    container_name: camoufox
    ports:
      - "127.0.0.1:8138:8138"
    profiles: [camoufox]

# ── Использование ──
#
# Запуск patchright (inline):
#   docker run --rm -v ./my_script.py:/scripts/script.py \\
#     ghcr.io/borski/patchright-docker script /scripts/script.py
#
# Запуск tilion (CDP endpoint):
#   docker compose -f docker-compose-patched.yml --profile tilion up -d
#   # В коде: from tilion_fortress import Fortress
#   #         p.chromium.connect_over_cdp("http://127.0.0.1:9222")
#
# Запуск camoufox (proxy):
#   docker compose -f docker-compose-patched.yml --profile camoufox up -d
#   # Прокси на localhost:8138 (http, без auth)
"""

# ══════════════════════════════════════════════════════════════════
# 6. tools/check_engine.py — проверка движка
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/tools/check_engine.py"] = '''\
"""
Проверка доступности движков и их свойств.

Запуск:
  python tools/check_engine.py
  python tools/check_engine.py --engine patchright
  python tools/check_engine.py --benchmark
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from core.browser_engine import list_engines, ENGINES


def print_engines():
    print()
    print("═" * 70)
    print("  Доступные движки браузеров")
    print("═" * 70)
    for info in list_engines():
        status = "✓" if info.available else "✗"
        print(f"  [{status}] {info.name:15s}  {info.notes[:60]}")
        if not info.available and info.install_cmd:
            print(f"      Установка: {info.install_cmd}")
    print()


async def benchmark_engine(engine: str):
    """Запускает движок и проверяет базовые свойства."""
    from core.browser_engine import launch_engine

    print(f"\\n→ Проверка {engine}...")
    try:
        pw, browser, extra = await launch_engine(engine, headless=True)
    except Exception as e:
        print(f"  ✗ Не удалось запустить: {e}")
        return

    try:
        if engine == "camoufox":
            context = await browser.new_context()
        else:
            context = await browser.new_context()
        page = await context.new_page()
        await page.goto("about:blank")

        result = await page.evaluate("""
            () => ({
                userAgent: navigator.userAgent,
                platform: navigator.platform,
                webdriver: navigator.webdriver,
                hasUserAgentData: !!navigator.userAgentData,
                cdcKeys: Object.keys(window).filter(k =>
                    k.startsWith('cdc_') || k.startsWith('$cdc_')
                ),
                toStringWorks: Function.prototype.toString.toString()
                    .includes('[native code]'),
            })
        """)

        print(f"  ✓ Запуск: {result['userAgent'][:60]}...")
        print(f"    platform: {result['platform']}")
        print(f"    webdriver: {result['webdriver']}")
        print(f"    userAgentData: {result['hasUserAgentData']}")
        print(f"    cdc_* keys: {result['cdcKeys']}")
        print(f"    toString native: {result['toStringWorks']}")

        await context.close()
    finally:
        try:
            if extra and hasattr(extra, "stop"):
                await extra.stop()
            elif extra and hasattr(extra, "__aexit__"):
                await extra.__aexit__(None, None, None)
            else:
                await browser.close()
            if pw:
                await pw.stop()
        except Exception:
            pass


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default=None)
    parser.add_argument("--benchmark", action="store_true")
    args = parser.parse_args()

    print_engines()

    if args.engine:
        if args.engine not in ENGINES:
            print(f"✗ Unknown engine: {args.engine}")
            sys.exit(1)
        await benchmark_engine(args.engine)
    elif args.benchmark:
        for info in list_engines():
            if info.available:
                await benchmark_engine(info.name)


if __name__ == "__main__":
    asyncio.run(main())
'''

# ══════════════════════════════════════════════════════════════════
# 7. tools/run_comparison.py — сравнение движков на тестовой странице
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/tools/run_comparison.py"] = '''\
"""
Сравнение движков на bot-detector.rebrowser.net.
Замеряет флаги, которые выставляет детектор для каждого движка.

Запуск:
  python tools/run_comparison.py
"""
from __future__ import annotations

import asyncio
import json
from core.browser_engine import list_engines, launch_engine


DETECTOR_URL = "https://bot-detector.rebrowser.net/"


async def check_engine(engine: str) -> dict:
    result = {"engine": engine, "ok": False, "flags": [], "error": None}
    try:
        pw, browser, extra = await launch_engine(engine, headless=True)
    except Exception as e:
        result["error"] = str(e)
        return result

    try:
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(DETECTOR_URL, timeout=30000)

        # Ждём, пока детектор отработает
        await asyncio.sleep(5)

        # Извлекаем результаты из таблицы
        flags = await page.evaluate("""
            () => {
                const rows = document.querySelectorAll('tr');
                const out = [];
                for (const row of rows) {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 2) {
                        const name = cells[0].innerText.trim();
                        const status = cells[1].innerText.trim();
                        if (name) out.push({name, status});
                    }
                }
                return out;
            }
        """)
        result["flags"] = flags
        result["ok"] = True
        await context.close()
    except Exception as e:
        result["error"] = str(e)
    finally:
        try:
            if extra and hasattr(extra, "stop"):
                await extra.stop()
            elif extra and hasattr(extra, "__aexit__"):
                await extra.__aexit__(None, None, None)
            else:
                await browser.close()
            if pw:
                await pw.stop()
        except Exception:
            pass
    return result


async def main():
    print("\\nСравнение движков на bot-detector.rebrowser.net\\n")
    results = []
    for info in list_engines():
        if not info.available:
            print(f"  ⊘ {info.name}: не установлен")
            continue
        print(f"  → {info.name}...", end=" ", flush=True)
        r = await check_engine(info.name)
        results.append(r)
        if r["ok"]:
            failed = [f for f in r["flags"] if "fail" in f["status"].lower()]
            print(f"провалено: {len(failed)}")
        else:
            print(f"ошибка: {r['error']}")

    print("\\n" + "═" * 60)
    for r in results:
        print(f"\\n{r['engine']}:")
        if r["ok"]:
            for f in r["flags"][:10]:
                marker = "✗" if "fail" in f["status"].lower() else "✓"
                print(f"  {marker} {f['name']}: {f['status']}")
        else:
            print(f"  Ошибка: {r['error']}")


if __name__ == "__main__":
    asyncio.run(main())
'''

# ══════════════════════════════════════════════════════════════════
# 8. run_lab_v5.py — запуск с патченным движком
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/run_lab_v5.py"] = '''\
"""
Запуск Red Team с патченным движком.

Перед запуском:
  1. Установите выбранный движок:
       pip install -r requirements-patched.txt
       patchright install chromium   # если выбрали patchright
  2. Укажите движок в config/engine.yaml
  3. Замените YOUR_TEST_CHANNEL в STREAM_URL
"""
import asyncio
import random
from core.browser_factory import BrowserFactory
from core.scheduler import generate_profile, pick_archetype
from core.fingerprint_manager import ProfilesBank
from workers.task_runner import run_agent
from telemetry.event_logger import EventLogger


async def main():
    STREAM_URL = "https://www.twitch.tv/YOUR_TEST_CHANNEL"
    N_AGENTS = 10

    agents_cfg = {
        "templates": {
            "lurker": {"weight": 0.5},
            "chatter": {"weight": 0.2},
            "scanner": {"weight": 0.2},
            "multi_tab": {"weight": 0.1},
        }
    }

    bank = ProfilesBank("config/profiles_bank.yaml")
    print(f"Profiles Bank: {len(bank)} профилей")

    proxies = [{"url": "", "country": "US"}]

    profiles = []
    for i in range(N_AGENTS):
        arch = pick_archetype(agents_cfg, i)
        ap, fp = generate_profile(f"agent_{i}", arch, proxies, bank=bank)
        ap.watch_time_target_sec = 90
        profiles.append((ap, fp))

    factory = BrowserFactory(headless=True)
    print(f"Движок: {factory.engine}")
    await factory.start()

    logger = EventLogger("logs/run_lab_v5.jsonl")
    semaphore = asyncio.Semaphore(5)

    try:
        tasks = [
            run_agent(factory, ap, fp, STREAM_URL, logger, semaphore)
            for ap, fp in profiles
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await factory.close()
        logger.close()

    print("Готово. См. logs/run_lab_v5.jsonl")


if __name__ == "__main__":
    asyncio.run(main())
'''

# ══════════════════════════════════════════════════════════════════
# 9. tools/switch_engine.sh — быстрое переключение движка
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/tools/switch_engine.sh"] = '''\
#!/usr/bin/env bash
# Быстрое переключение движка в config/engine.yaml.
# Использование: bash tools/switch_engine.sh patchright
set -e

ENGINE="$1"
if [ -z "$ENGINE" ]; then
    echo "Использование: $0 <engine>"
    echo "Доступные: playwright patchright rebrowser tilion camoufox invisible"
    exit 1
fi

CONFIG="config/engine.yaml"
if [ ! -f "$CONFIG" ]; then
    echo "✗ $CONFIG не найден. Запустите bootstrap5.py"
    exit 1
fi

# Меняем значение engine: "..." через sed
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/^engine: .*/engine: \\"$ENGINE\\"/" "$CONFIG"
else
    sed -i "s/^engine: .*/engine: \\"$ENGINE\\"/" "$CONFIG"
fi

echo "✓ Движок переключён на: $ENGINE"
grep "^engine:" "$CONFIG"
'''


def write_all():
    for rel, content in FILES.items():
        p = Path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        print(f"  ok {rel}")

    # chmod +x
    for script in ["twitch-redteam/tools/switch_engine.sh"]:
        try:
            os.chmod(script, 0o755)
        except Exception:
            pass


if __name__ == "__main__":
    write_all()
    print()
    print("Done. Next steps:")
    print()
    print("  1. Установить базовые зависимости:")
    print("     cd twitch-redteam && pip install -r requirements.txt")
    print()
    print("  2. Установить патченные движки (выберите один или несколько):")
    print("     pip install patchright")
    print("     patchright install chromium")
    print("     # ИЛИ")
    print("     pip install 'camoufox[geoip]' && python -m camoufox fetch")
    print("     # ИЛИ")
    print("     pip install tilion-fortress")
    print("     # ИЛИ")
    print("     pip install rebrowser-playwright")
    print()
    print("  3. Проверить доступные движки:")
    print("     python tools/check_engine.py")
    print()
    print("  4. Переключить движок (или отредактировать config/engine.yaml):")
    print("     bash tools/switch_engine.sh patchright")
    print()
    print("  5. Сравнить движки на детекторе:")
    print("     python tools/run_comparison.py")
    print()
    print("  6. Запустить Red Team с патченным движком:")
    print("     # отредактируйте STREAM_URL в run_lab_v5.py")
    print("     python run_lab_v5.py")