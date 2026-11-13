#!/usr/bin/env python3
# bootstrap_final.py — патчи + недостающие компоненты + карта проекта
import os
from pathlib import Path

FILES = {}

# ══════════════════════════════════════════════════════════════════
# ИСПРАВЛЕНИЕ 1: core/juggler_sync.py — aarch64 вместо armv8l
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/core/juggler_sync.py"] = '''\
"""
Синхронизация fingerprint для Camoufox через Juggler.

ИСПРАВЛЕНО:
  - PLATFORM_MAP["mobile"] = "Linux aarch64" (было armv8l)
  - _derive_oscpu для mobile = "Linux aarch64"
  - Добавлена поддержка audio/canvas seed для детерминизма
"""
from __future__ import annotations

import json
import os
from typing import Optional

from core.fingerprint_manager import FingerprintProfile


PLATFORM_MAP = {
    "Win32": "Win32",
    "MacIntel": "MacIntel",
    "Linux x86_64": "Linux x86_64",
    "mobile": "Linux aarch64",       # ИСПРАВЛЕНО: было Linux armv8l
}

UA_PLATFORM_MAP = {
    "Win32": "Windows",
    "MacIntel": "macOS",
    "Linux x86_64": "Linux",
    "mobile": "Android",
}


def build_camoufox_config(
    fp: FingerprintProfile,
    *,
    timezone: Optional[str] = None,
    locale: str = "en-US",
) -> dict:
    """Строит config dict для Camoufox с детерминированными seed'ами."""
    tz = timezone or fp.pick_timezone() or "UTC"

    config = {
        # ── Navigator ──
        "navigator.userAgent": fp.user_agent,
        "navigator.platform": PLATFORM_MAP.get(fp.platform, fp.platform),
        "navigator.oscpu": _derive_oscpu(fp.platform),
        "navigator.language": locale,
        "navigator.languages": [locale, "en"],
        "navigator.hardwareConcurrency": _pick_cores(fp),
        "navigator.maxTouchPoints": 5 if fp.mobile else 0,
        "navigator.doNotTrack": None,

        # ── Screen ──
        "screen.width": fp.viewport["width"],
        "screen.height": fp.viewport["height"],
        "screen.availWidth": fp.viewport["width"],
        "screen.availHeight": fp.viewport["height"] - 40,
        "screen.colorDepth": 24,
        "screen.pixelDepth": 24,
        "window.innerWidth": fp.viewport["width"],
        "window.innerHeight": fp.viewport["height"] - 40,
        "window.outerWidth": fp.viewport["width"],
        "window.outerHeight": fp.viewport["height"],
        "window.devicePixelRatio": fp.device_scale_factor,

        # ── WebGL ──
        "webGl:vendor": fp.webgl_vendor,
        "webGl:renderer": fp.webgl_renderer,

        # ── Timezone ──
        "timezone": tz,

        # ── ДЕТЕРМИНИЗМ: фиксированные seed'ы ──
        # Без этого CreepJS фиксирует разные Fingerprint ID per-run
        "fonts:spacing_seed": _stable_seed(fp.id, 1),
        "canvas:seed": _stable_seed(fp.id, 2),
        "audio:seed": _stable_seed(fp.id, 3),
    }

    if fp.mobile:
        config["navigator.maxTouchPoints"] = 5

    return config


def _stable_seed(profile_id: str, salt: int) -> int:
    """Детерминированный seed из id профиля — одинаков при каждом запуске."""
    import hashlib
    h = hashlib.sha256(f"{profile_id}:{salt}".encode()).hexdigest()
    return int(h[:8], 16) % 100000


def _derive_oscpu(platform: str) -> str:
    """ИСПРАВЛЕНО: mobile → Linux aarch64."""
    mapping = {
        "Win32": "Windows NT 10.0; Win64; x64",
        "MacIntel": "Intel Mac OS X 10.15",
        "Linux x86_64": "Linux x86_64",
        "mobile": "Linux aarch64",
    }
    return mapping.get(platform, "Linux x86_64")


def _pick_cores(fp: FingerprintProfile) -> int:
    """Согласованный hardwareConcurrency."""
    if fp.platform == "mobile":
        return 8
    if "RTX 40" in fp.webgl_renderer or "M2" in fp.webgl_renderer:
        return 16
    if "RTX 30" in fp.webgl_renderer or "M1" in fp.webgl_renderer:
        return 12
    return 8


def export_camou_config(fp, path="camou_config.json", timezone=None) -> str:
    config = build_camoufox_config(fp, timezone=timezone)
    Path(path).write_text(json.dumps(config, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    return path


def config_to_env(config: dict) -> dict:
    env = dict(os.environ)
    env["CAMOU_CONFIG"] = json.dumps(config)
    return env


def build_juggler_init_script(config: dict) -> str:
    """Fallback JS-скрипт для полей, не покрытых C++ патчами."""
    platform = config.get("navigator.platform", "")
    languages = config.get("navigator.languages", ["en-US", "en"])
    webgl_vendor = config.get("webGl:vendor", "")
    webgl_renderer = config.get("webGl:renderer", "")
    return f"""
    (() => {{
        try {{
            Object.defineProperty(navigator, 'platform',
                {{ get: () => {platform!r}, configurable: true }});
            Object.defineProperty(navigator, 'languages',
                {{ get: () => {languages!r}, configurable: true }});
        }} catch (e) {{}}
        const patchGL = (proto) => {{
            const orig = proto.getParameter;
            proto.getParameter = function(p) {{
                if (p === 37445) return {webgl_vendor!r};
                if (p === 37446) return {webgl_renderer!r};
                return orig.call(this, p);
            }};
        }};
        if (window.WebGLRenderingContext) patchGL(WebGLRenderingContext.prototype);
        if (window.WebGL2RenderingContext) patchGL(WebGL2RenderingContext.prototype);
    }})();
    """


class JugglerSync:
    def __init__(self, fp, *, timezone=None, locale="en-US"):
        self.fp = fp
        self.timezone = timezone or fp.pick_timezone()
        self.locale = locale
        self._config = None

    def build_config(self) -> dict:
        if self._config is None:
            self._config = build_camoufox_config(
                self.fp, timezone=self.timezone, locale=self.locale)
        return self._config

    def export_json(self, path="camou_config.json") -> str:
        return export_camou_config(self.fp, path, self.timezone)

    def env(self) -> dict:
        return config_to_env(self.build_config())

    def init_script(self) -> str:
        return build_juggler_init_script(self.build_config())

    def verify_config(self) -> dict:
        return verify_full_consistency(self.build_config())


def verify_full_consistency(config: dict) -> dict:
    """
    Полная проверка согласованности config:
      - UA vs platform
      - oscpu vs platform
      - WebGL vendor/renderer vs platform
      - Timezone vs language
      - UA-CH присутствие (аномалия для Firefox)
    """
    issues = []
    ua = config.get("navigator.userAgent", "")
    platform = config.get("navigator.platform", "")
    oscpu = config.get("navigator.oscpu", "")
    vendor = config.get("webGl:vendor", "")
    renderer = config.get("webGl:renderer", "")
    tz = config.get("timezone", "")
    lang = config.get("navigator.language", "")

    if "Windows" in ua and platform != "Win32":
        issues.append(f"UA Windows vs platform {platform}")
    if "Macintosh" in ua and platform != "MacIntel":
        issues.append(f"UA macOS vs platform {platform}")
    if "Android" in ua and "aarch64" not in platform:
        issues.append(f"Android UA vs platform {platform}")

    if platform == "Win32" and "Windows" not in oscpu:
        issues.append(f"platform Win32 vs oscpu {oscpu}")
    if platform == "MacIntel" and "Mac" not in oscpu:
        issues.append(f"platform MacIntel vs oscpu {oscpu}")

    if platform == "Win32" and "ANGLE" not in renderer:
        issues.append(f"Win32 vs non-ANGLE renderer: {renderer}")
    if platform == "MacIntel" and "Apple" not in vendor:
        issues.append(f"MacIntel vs non-Apple vendor: {vendor}")

    if tz.startswith("Asia/") and lang.startswith("de-"):
        issues.append(f"Asia tz + German lang")
    if tz.startswith("America/") and lang.startswith("ja-"):
        issues.append(f"US tz + Japanese lang")

    return {"consistent": len(issues) == 0, "issues": issues, "config": config}
'''

# ══════════════════════════════════════════════════════════════════
# ИСПРАВЛЕНИЕ 2: core/browser_factory.py — объединение init-скриптов
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/core/browser_factory.py"] = '''\
"""
BrowserFactory с исправленным порядком init-скриптов.

ИСПРАВЛЕНО:
  - Три add_init_script объединены в один (Playwright не гарантирует порядок)
  - Ветка camoufox использует CamoufoxContextManager (не browser.new_context)
  - Проверка согласованности fp_profile при создании
"""
from humanizer.visibility import _INIT_SCRIPT as VISIBILITY_INIT_SCRIPT
from core.fingerprint_manager import build_fingerprint_init_script
from core.browser_engine import launch_engine, ENGINES
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
        if self.engine == "camoufox":
            from camoufox.async_api import AsyncCamoufox
            self._camoufox_cm = AsyncCamoufox(headless=self.headless)
            self._browser = await self._camoufox_cm.__aenter__()
            return

        self._playwright, self._browser, self._fortress = await launch_engine(
            self.engine, headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

    def _build_combined_init_script(self, profile, fp_profile) -> str:
        """
        Объединяет три скрипта в один, гарантируя порядок:
          1. cdp_artifacts — перехват Object.defineProperty ДО всего
          2. fingerprint — согласованный отпечаток
          3. visibility — каскад Page Visibility
        """
        if fp_profile:
            fp_script = build_fingerprint_init_script(fp_profile)
        else:
            fp_script = self._fp_script(profile)

        return "\n;\n".join([
            self._cdp_artifacts_js,
            fp_script,
            VISIBILITY_INIT_SCRIPT,
        ])

    async def create_context(self, profile, fp_profile=None):
        if self.engine == "camoufox":
            return await self._create_camoufox_context(profile, fp_profile)

        viewport = fp_profile.viewport if fp_profile else profile.viewport
        user_agent = fp_profile.user_agent if fp_profile else profile.user_agent
        timezone = fp_profile.pick_timezone() if fp_profile else profile.timezone
        is_mobile = fp_profile.mobile if fp_profile else (profile.platform == "mobile")
        dsf = fp_profile.device_scale_factor if fp_profile else 1.0

        async with self._lock:
            context = await self._browser.new_context(
                viewport=viewport,
                user_agent=user_agent,
                locale=profile.locale,
                timezone_id=timezone,
                proxy={"server": profile.proxy} if profile.proxy else None,
                has_touch=is_mobile,
                is_mobile=is_mobile,
                device_scale_factor=dsf,
            )

        # ОДИН add_init_script — порядок гарантирован
        combined = self._build_combined_init_script(profile, fp_profile)
        await context.add_init_script(combined)

        return context

    async def _create_camoufox_context(self, profile, fp_profile):
        """Camoufox: использует отдельный context manager."""
        from core.camoufox_context_manager import CamoufoxContextManager
        if fp_profile is None:
            return await self._browser.new_context()
        mgr = CamoufoxContextManager(self._browser, fp_profile, profile)
        return await mgr.create()

    def _fp_script(self, profile):
        return f"""
        (() => {{
            try {{
                Object.defineProperty(navigator, 'platform',
                    {{ get: () => {profile.platform!r}, configurable: true }});
                Object.defineProperty(navigator, 'languages',
                    {{ get: () => [{profile.locale!r}, 'en'], configurable: true }});
                Object.defineProperty(navigator, 'webdriver',
                    {{ get: () => undefined, configurable: true }});
            }} catch (e) {{}}
            window.__mouseX = 0;
            window.__mouseY = 0;
        }})();
        """

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
# НОВЫЙ КОМПОНЕНТ 3: core/camoufox_context_manager.py
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/core/camoufox_context_manager.py"] = '''\
"""
Правильное создание per-context fingerprint в Camoufox.

ВАЖНО: Camoufox НЕ принимает произвольный config в browser.new_context().
Per-context config работает через AsyncNewContext с параметром config.
"""
from __future__ import annotations

from core.juggler_sync import JugglerSync


class CamoufoxContextManager:
    """
    Создаёт per-context fingerprint для Camoufox.

    Использование:
        mgr = CamoufoxContextManager(browser, fp_profile, agent_profile)
        context = await mgr.create()
    """

    def __init__(self, browser, fp_profile, agent_profile):
        self.browser = browser
        self.fp = fp_profile
        self.agent = agent_profile

    async def create(self):
        try:
            from camoufox.async_api import AsyncNewContext
        except ImportError:
            # Fallback для старых версий camoufox
            return await self._fallback_create()

        sync = JugglerSync(
            self.fp,
            timezone=self.fp.pick_timezone() or self.agent.timezone,
            locale=self.agent.locale,
        )
        config = sync.build_config()

        # Проверка согласованности перед созданием
        report = sync.verify_config()
        if not report["consistent"]:
            print(f"[camoufox] config issues for {self.fp.id}: "
                  f"{report['issues']}")

        proxy = None
        if self.agent.proxy:
            proxy = {"server": self.agent.proxy}

        context = await AsyncNewContext(
            self.browser,
            config=config,
            proxy=proxy,
        )
        return context

    async def _fallback_create(self):
        """Fallback: обычный контекст + init_script."""
        sync = JugglerSync(self.fp, timezone=self.fp.pick_timezone(),
                           locale=self.agent.locale)
        context = await self.browser.new_context()
        await context.add_init_script(sync.init_script())
        return context
'''

# ══════════════════════════════════════════════════════════════════
# НОВЫЙ КОМПОНЕНТ 4: tools/verify_camoufox.py
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/tools/verify_camoufox.py"] = '''\
"""
Проверка Camoufox через INLINE <script>, а не page.evaluate.

ВАЖНО: с beta.29 add_init_script не доходит до page world.
page.evaluate() может вернуть правильные значения, тогда как
сайт видит другое. Этот скрипт проверяет то, что ВИДИТ САЙТ.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from core.fingerprint_manager import ProfilesBank
from core.juggler_sync import JugglerSync


INLINE_PROBE = """
<!doctype html>
<html><head><title>pending</title></head>
<body>
<script>
(() => {
    const probe = {
        platform: navigator.platform,
        userAgent: navigator.userAgent,
        oscpu: navigator.oscpu || null,
        language: navigator.language,
        languages: navigator.languages,
        hardwareConcurrency: navigator.hardwareConcurrency,
        maxTouchPoints: navigator.maxTouchPoints,
        dpr: window.devicePixelRatio,
        screenW: screen.width,
        screenH: screen.height,
        webglVendor: null,
        webglRenderer: null,
        canvasHash: null,
        hasUserAgentData: !!navigator.userAgentData,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    };

    try {
        const c = document.createElement('canvas');
        const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
        if (gl) {
            const dbg = gl.getExtension('WEBGL_debug_renderer_info');
            if (dbg) {
                probe.webglVendor = gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL);
                probe.webglRenderer = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
            }
        }
    } catch (e) {}

    try {
        const c = document.createElement('canvas');
        c.width = 200; c.height = 50;
        const x = c.getContext('2d');
        x.textBaseline = 'top';
        x.font = '14px Arial';
        x.fillStyle = '#f60';
        x.fillRect(125, 1, 62, 20);
        x.fillStyle = '#069';
        x.fillText('Fingerprint test', 2, 15);
        probe.canvasHash = c.toDataURL().slice(-32);
    } catch (e) {}

    document.title = JSON.stringify(probe);
})();
</script>
</body></html>
"""


async def main():
    bank = ProfilesBank("config/profiles_bank.yaml")
    fp = bank.pick()
    print(f"Профиль: {fp.id}")

    try:
        from camoufox.async_api import AsyncCamoufox, AsyncNewContext
    except ImportError:
        print("✗ camoufox не установлен. Установите: pip install 'camoufox[geoip]'")
        return

    sync = JugglerSync(fp)
    config = sync.build_config()

    async with AsyncCamoufox(headless=True) as browser:
        try:
            context = await AsyncNewContext(browser, config=config)
        except Exception:
            context = await browser.new_context()
            await context.add_init_script(sync.init_script())

        page = await context.new_page()
        data_url = "data:text/html;charset=utf-8," + INLINE_PROBE.replace(
            "\n", "").replace("#", "%23")
        await page.goto(data_url)

        title = await page.title()
        try:
            probe = json.loads(title)
        except Exception:
            probe = {"raw_title": title}

        print("\\n=== Что видит сайт (inline probe) ===")
        for k, v in probe.items():
            print(f"  {k}: {v}")

        print("\\n=== Согласованность ===")
        report = sync.verify_config()
        if report["consistent"]:
            print("  ✓ Config согласован")
        else:
            for issue in report["issues"]:
                print(f"  ✗ {issue}")

        # Проверка на beta.29 regression
        if probe.get("platform") != config.get("navigator.platform"):
            print(f"\\n  ⚠ РЕГРЕССИЯ beta.29: сайт видит platform={probe.get('platform')},"
                  f" config={config.get('navigator.platform')}")
        if probe.get("hasUserAgentData"):
            print(f"\\n  ⚠ userAgentData присутствует — аномалия для Firefox")

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
'''

# ══════════════════════════════════════════════════════════════════
# НОВЫЙ КОМПОНЕНТ 5: tools/fingerprint_consistency.py
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/tools/fingerprint_consistency.py"] = '''\
"""
Проверка согласованности всех профилей в Profiles Bank.

Запуск:
  python tools/fingerprint_consistency.py
  python tools/fingerprint_consistency.py --engine camoufox
"""
import argparse
from core.fingerprint_manager import ProfilesBank


def check_profile_chromium(fp) -> list[str]:
    issues = []
    if fp.platform == "Win32" and "ANGLE" not in fp.webgl_renderer:
        issues.append(f"Win32 vs non-ANGLE renderer")
    if fp.platform == "MacIntel" and "Apple" not in fp.webgl_vendor:
        issues.append(f"MacIntel vs non-Apple vendor")
    if fp.platform == "Linux x86_64" and "ANGLE" in fp.webgl_renderer:
        issues.append(f"Linux vs ANGLE renderer (Windows-specific)")
    if fp.mobile and fp.platform != "mobile":
        issues.append(f"mobile=True vs platform={fp.platform}")
    if fp.platform == "mobile" and not fp.mobile:
        issues.append(f"platform=mobile vs mobile=False")
    return issues


def check_profile_camoufox(fp) -> list[str]:
    from core.juggler_sync import JugglerSync
    sync = JugglerSync(fp)
    report = sync.verify_config()
    return report["issues"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default="chromium",
                        choices=["chromium", "camoufox"])
    args = parser.parse_args()

    bank = ProfilesBank("config/profiles_bank.yaml")
    print(f"Проверка {len(bank.profiles)} профилей "
          f"для движка: {args.engine}\\n")

    total_issues = 0
    for fp in bank.profiles:
        if args.engine == "camoufox":
            issues = check_profile_camoufox(fp)
        else:
            issues = check_profile_chromium(fp)

        if issues:
            print(f"  ✗ {fp.id}:")
            for i in issues:
                print(f"      - {i}")
            total_issues += len(issues)
        else:
            print(f"  ✓ {fp.id}")

    print(f"\\nИтого: {total_issues} проблем")


if __name__ == "__main__":
    main()
'''

# ══════════════════════════════════════════════════════════════════
# ИСПРАВЛЕНИЕ 6: tools/check_juggler.py — с UA-CH и полной проверкой
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/tools/check_juggler.py"] = '''\
"""
Проверка Camoufox config с полной согласованностью.
"""
import argparse
from core.fingerprint_manager import ProfilesBank
from core.juggler_sync import JugglerSync, verify_full_consistency


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=None)
    parser.add_argument("--all", action="store_true",
                        help="Проверить все профили")
    args = parser.parse_args()

    bank = ProfilesBank("config/profiles_bank.yaml")

    if args.all:
        for fp in bank.profiles:
            report = JugglerSync(fp).verify_config()
            status = "✓" if report["consistent"] else "✗"
            print(f"  [{status}] {fp.id}")
            for issue in report["issues"]:
                print(f"      - {issue}")
        return

    if args.profile:
        fp = next((p for p in bank.profiles if p.id == args.profile), None)
        if not fp:
            print(f"Профиль {args.profile} не найден")
            return
    else:
        fp = bank.pick()

    print(f"Профиль: {fp.id}")
    sync = JugglerSync(fp)
    config = sync.build_config()
    report = verify_full_consistency(config)

    print(f"\\nСогласованность: {report['consistent']}")
    for issue in report["issues"]:
        print(f"  ✗ {issue}")

    print("\\nПолный config:")
    for k, v in config.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
'''

# ══════════════════════════════════════════════════════════════════
# 7. PROJECT_MAP.txt — карта проекта
# ══════════════════════════════════════════════════════════════════

PROJECT_MAP = """\
================================================================================
RED/BLUE TEAM RESEARCH STAND — Карта проекта (v6)
================================================================================

Полная структура после всех шести bootstrap'ов.

================================================================================
BLUE TEAM (twitch-antifraud/)
================================================================================

twitch-antifraud/
├── data/
│   ├── schema.py                    ViewerSession dataclass
│   └── synthetic_generator.py       Генератор органики + ботов
├── features/
│   └── pipeline.py                  16 признаков (stat/behav/network/account)
├── models/
│   ├── isolation_forest.py          Unsupervised baseline
│   ├── autoencoder.py               Semi-supervised
│   └── ensemble.py                  IF + AE с весами
├── evaluation/
│   └── metrics.py                   ROC-AUC, PR-AUC, F1, best_threshold
├── run_demo.py                      end-to-end демо
└── requirements.txt

Запуск:
  cd twitch-antifraud
  pip install -r requirements.txt
  python run_demo.py

================================================================================
RED TEAM (twitch-redteam/) — 6 bootstrap'ов
================================================================================

twitch-redteam/
│
├── config/
│   ├── pool.yaml                    Pods × agents
│   ├── agents.yaml                  Архетипы с весами
│   ├── proxies.csv                  Geo-matched прокси
│   ├── profiles_bank.yaml           12 fingerprint-профилей
│   ├── engine.yaml                  Выбор движка (patchright/camoufox/...)
│   ├── config.docker.yaml           ytkoka/impersonate-proxy
│   └── config.docker.pysaint.yaml   psaintelligence/impersonate-proxy
│
├── core/
│   ├── browser_engine.py            Абстракция 6 движков
│   ├── browser_factory.py           Создание contexts (ИСПРАВЛЕНО: 1 init)
│   ├── fingerprint_manager.py       ProfilesBank + build_fingerprint_init_script
│   ├── camoufox_context_manager.py  Per-context Camoufox (НОВЫЙ)
│   ├── juggler_sync.py              Camoufox config (ИСПРАВЛЕНО: aarch64)
│   ├── scheduler.py                 generate_profile + pick_archetype
│   └── session_store.py             (placeholder)
│
├── behaviors/
│   ├── base.py                      BaseAgent + AgentProfile
│   ├── lurker.py                    Только смотрит
│   ├── chatter.py                   + чат (Poisson)
│   ├── scanner.py                   Переключает каналы
│   └── multi_tab.py                 Вторая вкладка
│
├── humanizer/
│   ├── mouse.py                     Безье + тремор
│   ├── scroll.py                    (в timing)
│   ├── timing.py                    Логнормальные паузы
│   ├── keyboard.py                  (встроено в chatter)
│   ├── visibility.py                JS-фасад Page Visibility
│   ├── visibility_cdp.py            CDP freeze (оригинал)
│   ├── lazy_cdp.py                  Lazy attach + LazyVisibilityCDP
│   ├── ua_ch_sync.py                UA-CH синхронизация (только Chromium)
│   ├── cdp_artifacts.js             Маскировка CDP/WebDriver артефактов
│   └── __init__.py
│
├── perception/                      (опционально, AI-чат)
│   ├── audio_capture.py
│   ├── chat_observer.py
│   └── reaction_engine.py
│
├── workers/
│   ├── pod_entry.py                 K8s точка входа
│   └── task_runner.py               run_agent с UA-CH + fp_profile
│
├── telemetry/
│   └── event_logger.py              JSONL logger
│
├── templates/
│   ├── Dockerfile
│   ├── configmap.yaml
│   └── kubernetes-indexed-job.yaml  500 агентов
│
├── tools/
│   ├── check_artifacts.py           Полная проверка (7 checks)
│   ├── check_engine.py              Доступность движков + benchmark
│   ├── check_juggler.py             Camoufox config (ИСПРАВЛЕНО)
│   ├── verify_camoufox.py           Inline probe (НОВЫЙ)
│   ├── verify_fingerprint.py        JA3/JA4/Akamai H2
│   ├── fingerprint_consistency.py   Проверка всех профилей (НОВЫЙ)
│   ├── run_comparison.py            Сравнение движков на bot-detector
│   ├── run_verify.sh                Полный цикл
│   └── switch_engine.sh             Быстрое переключение движка
│
├── docker-compose.yml               impersonate-proxy (Go + Python)
├── docker-compose-patched.yml       patchright + tilion + camoufox
│
├── requirements.txt                 Базовые
├── requirements-patched.txt         Патченные движки
│
├── run_lab.py                       10 агентов (bootstrap 1)
├── run_lab_advanced.py              + visibility (bootstrap 2)
├── run_lab_v3.py                    + Profiles Bank (bootstrap 3)
├── run_lab_v5.py                    + патченный движок (bootstrap 5)
│
└── logs/

================================================================================
ЗАПУСК — ПОШАГОВЫЙ
================================================================================

1) Создание структуры:
   python bootstrap.py
   python bootstrap2.py
   python bootstrap3.py
   python bootstrap4.py
   python bootstrap5.py
   python bootstrap_final.py

2) Установка зависимостей:
   cd twitch-redteam
   pip install -r requirements.txt
   pip install -r requirements-patched.txt
   patchright install chromium   # или: python -m camoufox fetch

3) Проверки:
   python tools/check_artifacts.py
   python tools/check_engine.py
   python tools/fingerprint_consistency.py --engine chromium
   python tools/fingerprint_consistency.py --engine camoufox
   python tools/check_juggler.py --all

4) Прокси:
   mkdir -p data && sudo chown 65532:65532 data
   docker compose --profile go up -d
   python tools/verify_fingerprint.py --via-proxy --no-verify

5) Локальный запуск:
   # отредактируйте STREAM_URL в run_lab_v5.py
   python run_lab_v5.py

6) Camoufox проверка:
   bash tools/switch_engine.sh camoufox
   python tools/verify_camoufox.py

7) K8s (500 агентов):
   docker build -t twitch-redteam:latest -f templates/Dockerfile .
   kubectl create namespace redteam-lab
   kubectl apply -f templates/configmap.yaml
   kubectl apply -f templates/kubernetes-indexed-job.yaml

================================================================================
ЧТО ИСПРАВЛЕНО В v6
================================================================================

1. juggler_sync.py: PLATFORM_MAP["mobile"] → "Linux aarch64"
2. juggler_sync.py: _derive_oscpu mobile → "Linux aarch64"
3. juggler_sync.py: детерминированные seed'ы (fonts/canvas/audio)
4. browser_factory.py: три add_init_script объединены в один
5. camoufox_context_manager.py: правильный per-context config
6. verify_camoufox.py: проверка через inline script (не evaluate)
7. fingerprint_consistency.py: согласованность всех профилей
8. check_juggler.py: полная проверка с UA-CH

================================================================================
ЧТО ОСТАЁТСЯ УЯЗВИМЫМ
================================================================================

1. system-ui font leak (Camoufox): macOS-профили на Linux-хосте палятся
   → Решение: отдельные контейнеры или исключить macOS-профили

2. add_init_script не доходит до page world в beta.29+
   → Решение: Camoufox <= beta.28, или использовать C++ config

3. Target.attachToTarget виден на Browser-домене
   → Решение: tilion/fortress или прозрачный прокси

4. HTTP/2 SETTINGS без impersonate-proxy = Chromium fingerprint
   → Решение: обязательное использование impersonate-proxy

5. Порядок init-скриптов в старых версиях Playwright
   → Решение: объединение в один (сделано в v6)

================================================================================
ЭТИЧЕСКИЕ ОГРАНИЧЕНИЯ
================================================================================

- Только собственные тестовые каналы.
- Никакой монетизации.
- Disclosure в security@twitch.tv до публикации.
- Синтетические данные в приоритете.
- Не передавать работающие методы обхода третьим лицам.

================================================================================
"""

FILES["twitch-redteam/PROJECT_MAP.txt"] = PROJECT_MAP


def write_all():
    for rel, content in FILES.items():
        p = Path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        print(f"  ok {rel}")


if __name__ == "__main__":
    write_all()
    print()
    print("Done. Финальные шаги:")
    print()
    print("  1. Проверить, что все предыдущие bootstrap'ы запущены")
    print("  2. cd twitch-redteam")
    print("  3. python tools/fingerprint_consistency.py --engine camoufox")
    print("  4. python tools/check_juggler.py --all")
    print("  5. bash tools/switch_engine.sh camoufox && python tools/verify_camoufox.py")
    print()
    print("  Карта проекта: twitch-redteam/PROJECT_MAP.txt")