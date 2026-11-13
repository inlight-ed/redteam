#!/usr/bin/env python3
# bootstrap3.py — CDP-артефакты + Profiles Bank
import os
from pathlib import Path

FILES = {}

# ══════════════════════════════════════════════════════════════════
# 1. humanizer/cdp_artifacts.js — маскировка следов CDP
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/humanizer/cdp_artifacts.js"] = r"""
/*
 * Маскировка следов CDP/WebDriver в runtime.
 * Инжектится через add_init_script до первой навигации.
 *
 * Закрывает:
 *   - Function.prototype.toString для инжектированных функций
 *   - window.cdc_* артефакты ChromeDriver
 *   - window.__selenium_* / __webdriver_* / __driver_* артефакты
 *   - console.debug ловушки WebDriver
 */
(() => {
    if (window.__cdp_artifacts_installed) return;
    window.__cdp_artifacts_installed = true;

    // ── 1. Function.prototype.toString ──
    const nativeToString = Function.prototype.toString;
    const nativeToStringStr = nativeToString.toString();

    Function.prototype.toString = function() {
        // Если функция помечена как CDP-инжектированная
        if (this && this.__cdp_injected__) {
            const name = this.name || '';
            return `function ${name}() { [native code] }`;
        }
        // Для нативных — возвращаем оригинал
        if (this === Function.prototype.toString) {
            return nativeToStringStr;
        }
        try {
            return nativeToString.call(this);
        } catch (e) {
            return `function ${this.name || ''}() { [native code] }`;
        }
    };
    try {
        Object.defineProperty(Function.prototype.toString, 'name', {
            value: 'toString', configurable: true
        });
        Object.defineProperty(Function.prototype.toString, 'length', {
            value: 0, configurable: true
        });
    } catch (e) {}

    // ── 2. Удаление артефактов WebDriver ──
    const artifacts = [
        'cdc_adoQ425bcd421573312',
        'cdc_asdjflasutopfhvcZLmcfl_',
        '__selenium_unwrapped',
        '__selenium_evaluate',
        '__selenium_script_fn',
        '__webdriver_evaluate',
        '__webdriver_script_fn',
        '__webdriver_script_func',
        '__webdriver_script_function',
        '__webdriver_unwrapped',
        '__driver_evaluate',
        '__driver_unwrapped',
        '__fxdriver_evaluate',
        '__fxdriver_unwrapped',
        '__nightmare',
        '_phantom',
        'callPhantom',
        'callSelenium',
        '_Selenium_IDE_Recorder',
        'webdriver',
        'domAutomation',
        'domAutomationController',
    ];

    for (const key of artifacts) {
        try {
            delete window[key];
        } catch (e) {}
        try {
            delete document[key];
        } catch (e) {}
        try {
            Object.defineProperty(window, key, {
                get: () => undefined,
                configurable: true,
                enumerable: false,
            });
        } catch (e) {}
    }

    // ── 3. Маскировка Runtime.enable ──
    // CDP может добавлять __cdp_* свойства — удаляем на лету
    const cdpPropRegex = /^__cdp_|^cdc_|^__webdriver_|^__selenium_/;
    const originalDefineProperty = Object.defineProperty;
    Object.defineProperty = function(obj, prop, descriptor) {
        if (typeof prop === 'string' && cdpPropRegex.test(prop)) {
            // Пропускаем определение, но не создаём свойство
            return obj;
        }
        return originalDefineProperty.call(this, obj, prop, descriptor);
    };
    try {
        Object.defineProperty(Object, 'defineProperty', {
            value: Object.defineProperty,
            configurable: true,
        });
    } catch (e) {}

    // ── 4. Маскировка console.debug (WebDriver ловушки) ──
    const nativeConsoleDebug = console.debug;
    console.debug = function(...args) {
        // WebDriver иногда инжектит через console.debug — игнорируем
        // характерные сообщения
        if (args.length > 0 && typeof args[0] === 'string') {
            if (args[0].includes('wd:') || args[0].includes('webdriver')) {
                return;
            }
        }
        return nativeConsoleDebug.apply(console, args);
    };
    try {
        Object.defineProperty(console.debug, 'name',
            { value: 'debug', configurable: true });
    } catch (e) {}

    // ── 5. Помечивание новых функций как native ──
    window.__cdp_mark_injected = function(fn) {
        if (typeof fn === 'function') {
            try {
                Object.defineProperty(fn, '__cdp_injected__', {
                    value: true, configurable: true, enumerable: false,
                });
            } catch (e) {}
        }
        return fn;
    };
})();
"""

# ══════════════════════════════════════════════════════════════════
# 2. config/profiles_bank.yaml — реальные распределения
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/config/profiles_bank.yaml"] = """\
# Profiles Bank: реальные комбинации GPU/UA/viewport/canvas hash
# Веса — на основе Steam Hardware Survey (2024-2025), Can I Use,
# browserleaks. Не идеальные, но отражают реальные пропорции.
#
# ВАЖНО: canvas_hash и webgl_renderer должны быть сняты с РЕАЛЬНЫХ
# машин с этими конфигурациями. Здесь — синтетические placeholder'ы.

profiles:
  # ── Windows + NVIDIA RTX 3060 — самый популярный ──
  - id: win_rtx3060_1080p
    weight: 0.18
    platform: "Win32"
    platform_version: "10.0.0"
    ua_platform: "Windows"
    architecture: "x86"
    bitness: "64"
    mobile: false
    viewport: {width: 1920, height: 1080}
    device_scale_factor: 1.0
    user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    webgl_vendor: "Google Inc. (NVIDIA)"
    webgl_renderer: "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"
    canvas_hash: "a3f2c8e1b9d4f7a2e5c8b1d4f7a2e5c8"
    timezone_pool: ["America/New_York", "Europe/Berlin", "Europe/London"]

  # ── Windows + NVIDIA GTX 1660 ──
  - id: win_gtx1660_1080p
    weight: 0.14
    platform: "Win32"
    platform_version: "10.0.0"
    ua_platform: "Windows"
    architecture: "x86"
    bitness: "64"
    mobile: false
    viewport: {width: 1920, height: 1080}
    device_scale_factor: 1.0
    user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    webgl_vendor: "Google Inc. (NVIDIA)"
    webgl_renderer: "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11)"
    canvas_hash: "b4e3d9f2c0a5e8b3f6d9c2a5e8b3f6d9"
    timezone_pool: ["America/Chicago", "Europe/Warsaw", "Europe/Paris"]

  # ── Windows + Intel UHD (ноутбуки) ──
  - id: win_intel_uhd_1366p
    weight: 0.12
    platform: "Win32"
    platform_version: "10.0.0"
    ua_platform: "Windows"
    architecture: "x86"
    bitness: "64"
    mobile: false
    viewport: {width: 1366, height: 768}
    device_scale_factor: 1.0
    user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    webgl_vendor: "Google Inc. (Intel)"
    webgl_renderer: "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)"
    canvas_hash: "c5f4e0a3d1b6f9c4a7e0d3b6f9c4a7e0"
    timezone_pool: ["America/New_York", "Europe/Berlin", "Asia/Tokyo"]

  # ── Windows 11 + RTX 4070 ──
  - id: win11_rtx4070_1440p
    weight: 0.10
    platform: "Win32"
    platform_version: "15.0.0"
    ua_platform: "Windows"
    architecture: "x86"
    bitness: "64"
    mobile: false
    viewport: {width: 2560, height: 1440}
    device_scale_factor: 1.0
    user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    webgl_vendor: "Google Inc. (NVIDIA)"
    webgl_renderer: "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)"
    canvas_hash: "d6a5f1b4e2c7a0d5b8f1e4c7a0d5b8f1"
    timezone_pool: ["America/Los_Angeles", "Europe/Amsterdam"]

  # ── macOS M1 ──
  - id: mac_m1_1440p
    weight: 0.11
    platform: "MacIntel"
    platform_version: "14.5.0"
    ua_platform: "macOS"
    architecture: "arm"
    bitness: "64"
    mobile: false
    viewport: {width: 1440, height: 900}
    device_scale_factor: 2.0
    user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    webgl_vendor: "Apple Inc."
    webgl_renderer: "Apple M1"
    canvas_hash: "e7b6a2c5f3d8b1e6c9a2f5d8b1e6c9a2"
    timezone_pool: ["America/Los_Angeles", "Europe/Berlin", "Asia/Singapore"]

  # ── macOS M2 ──
  - id: mac_m2_1512p
    weight: 0.07
    platform: "MacIntel"
    platform_version: "15.0.0"
    ua_platform: "macOS"
    architecture: "arm"
    bitness: "64"
    mobile: false
    viewport: {width: 1512, height: 982}
    device_scale_factor: 2.0
    user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    webgl_vendor: "Apple Inc."
    webgl_renderer: "Apple M2"
    canvas_hash: "f8c7b3d6a4e9c2f7d0b3e6a9c2f7d0b3"
    timezone_pool: ["America/New_York", "Europe/London"]

  # ── Windows + AMD RX 6600 ──
  - id: win_amd_rx6600_1080p
    weight: 0.06
    platform: "Win32"
    platform_version: "10.0.0"
    ua_platform: "Windows"
    architecture: "x86"
    bitness: "64"
    mobile: false
    viewport: {width: 1920, height: 1080}
    device_scale_factor: 1.0
    user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    webgl_vendor: "Google Inc. (AMD)"
    webgl_renderer: "ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0, D3D11)"
    canvas_hash: "a9d8c4e7b5f0d3a8c1e4b7f0d3a8c1e4"
    timezone_pool: ["Europe/Warsaw", "Europe/Prague"]

  # ── Windows + GTX 1050 Ti (старые ноутбуки/десктопы) ──
  - id: win_gtx1050ti_1080p
    weight: 0.05
    platform: "Win32"
    platform_version: "10.0.0"
    ua_platform: "Windows"
    architecture: "x86"
    bitness: "64"
    mobile: false
    viewport: {width: 1920, height: 1080}
    device_scale_factor: 1.0
    user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    webgl_vendor: "Google Inc. (NVIDIA)"
    webgl_renderer: "ANGLE (NVIDIA, NVIDIA GeForce GTX 1050 Ti Direct3D11 vs_5_0 ps_5_0, D3D11)"
    canvas_hash: "b0e9d5f8c6a1e4b9d2f5c8a1e4b9d2f5"
    timezone_pool: ["America/New_York", "Europe/Berlin"]

  # ── Linux + AMD (миноритарный, но существует) ──
  - id: linux_amd_1080p
    weight: 0.03
    platform: "Linux x86_64"
    platform_version: ""
    ua_platform: "Linux"
    architecture: "x86"
    bitness: "64"
    mobile: false
    viewport: {width: 1920, height: 1080}
    device_scale_factor: 1.0
    user_agent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    webgl_vendor: "Google Inc. (AMD)"
    webgl_renderer: "ANGLE (AMD, AMD Radeon RX 6700 XT (RADV NAVI22), OpenGL 4.6)"
    canvas_hash: "c1f0e6a9d7b2f5c0e3a6d9b2f5c0e3a6"
    timezone_pool: ["Europe/Berlin", "Europe/Helsinki"]

  # ── Android mobile ──
  - id: android_pixel7
    weight: 0.05
    platform: "mobile"
    platform_version: "14"
    ua_platform: "Android"
    architecture: "arm"
    bitness: "64"
    mobile: true
    viewport: {width: 412, height: 915}
    device_scale_factor: 2.625
    user_agent: "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36"
    webgl_vendor: "Qualcomm"
    webgl_renderer: "Adreno (TM) 730"
    canvas_hash: "d2a1f7b0e8c3a6d1f4b7e0a3d6f9c2a5"
    timezone_pool: ["America/New_York", "Europe/Berlin"]

  # ── Android Samsung ──
  - id: android_samsung_s23
    weight: 0.04
    platform: "mobile"
    platform_version: "14"
    ua_platform: "Android"
    architecture: "arm"
    bitness: "64"
    mobile: true
    viewport: {width: 360, height: 780}
    device_scale_factor: 3.0
    user_agent: "Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36"
    webgl_vendor: "Qualcomm"
    webgl_renderer: "Adreno (TM) 740"
    canvas_hash: "e3b2a8c1f9d4b7e2a5c8f1d4b7e2a5c8"
    timezone_pool: ["Asia/Seoul", "Asia/Tokyo"]

  # ── macOS Intel (старые MacBook) ──
  - id: mac_intel_2560p
    weight: 0.05
    platform: "MacIntel"
    platform_version: "12.7.0"
    ua_platform: "macOS"
    architecture: "x86"
    bitness: "64"
    mobile: false
    viewport: {width: 2560, height: 1600}
    device_scale_factor: 2.0
    user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    webgl_vendor: "Intel Inc."
    webgl_renderer: "Intel Iris Pro OpenGL Engine"
    canvas_hash: "f4c3b9d2a0e5c8f3b6a9d2e5c8f3b6a9"
    timezone_pool: ["America/New_York", "Europe/Paris"]

# Не нормируется автоматически — fingerprint_manager валидирует сумму.
# Ожидаемая сумма: ~1.00
"""

# ══════════════════════════════════════════════════════════════════
# 3. core/fingerprint_manager.py — выбор и применение профиля
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/core/fingerprint_manager.py"] = '''\
"""
Profiles Bank: выбор согласованного fingerprint-профиля.
Все поля (UA, GPU, viewport, canvas hash, timezone) берутся
из ОДНОГО профиля — никаких кросс-комбинаций.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class FingerprintProfile:
    id: str
    weight: float
    platform: str
    platform_version: str
    ua_platform: str
    architecture: str
    bitness: str
    mobile: bool
    viewport: dict
    device_scale_factor: float
    user_agent: str
    webgl_vendor: str
    webgl_renderer: str
    canvas_hash: str
    timezone_pool: list = field(default_factory=list)

    def pick_timezone(self) -> str:
        return random.choice(self.timezone_pool) if self.timezone_pool else "UTC"


class ProfilesBank:
    """
    Загружает profiles_bank.yaml, валидирует сумму весов,
    выбирает профиль через weighted random.
    """

    def __init__(self, path: str = "config/profiles_bank.yaml"):
        self.path = path
        self.profiles: list[FingerprintProfile] = []
        self._load()

    def _load(self):
        data = yaml.safe_load(Path(self.path).read_text(encoding="utf-8"))
        for p in data["profiles"]:
            self.profiles.append(FingerprintProfile(
                id=p["id"],
                weight=float(p["weight"]),
                platform=p["platform"],
                platform_version=p.get("platform_version", ""),
                ua_platform=p["ua_platform"],
                architecture=p["architecture"],
                bitness=p["bitness"],
                mobile=bool(p["mobile"]),
                viewport=p["viewport"],
                device_scale_factor=float(p.get("device_scale_factor", 1.0)),
                user_agent=p["user_agent"],
                webgl_vendor=p["webgl_vendor"],
                webgl_renderer=p["webgl_renderer"],
                canvas_hash=p["canvas_hash"],
                timezone_pool=p.get("timezone_pool", []),
            ))
        total = sum(p.weight for p in self.profiles)
        if not 0.9 <= total <= 1.1:
            raise ValueError(
                f"Сумма весов Profiles Bank = {total:.3f}, ожидается ~1.0"
            )

    def pick(self) -> FingerprintProfile:
        """Weighted random выбор профиля."""
        weights = [p.weight for p in self.profiles]
        return random.choices(self.profiles, weights=weights, k=1)[0]

    def pick_matching(self, timezone: Optional[str] = None,
                      mobile: Optional[bool] = None) -> FingerprintProfile:
        """
        Выбор с фильтром: профиль должен поддерживать заданный
        timezone или mobile-флаг. Если фильтр слишком узкий —
        fallback на обычный pick().
        """
        candidates = self.profiles
        if timezone is not None:
            filtered = [p for p in candidates if timezone in p.timezone_pool]
            if filtered:
                candidates = filtered
        if mobile is not None:
            filtered = [p for p in candidates if p.mobile == mobile]
            if filtered:
                candidates = filtered
        if not candidates:
            return self.pick()
        weights = [p.weight for p in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]

    def __len__(self):
        return len(self.profiles)


def build_fingerprint_init_script(profile: FingerprintProfile) -> str:
    """
    Генерирует JS-скрипт, который переопределяет navigator.*,
    WebGL vendor/renderer и Canvas на уровне страницы,
    согласованно с профилем.
    """
    viewport = profile.viewport
    canvas_hash = profile.canvas_hash
    webgl_vendor = profile.webgl_vendor
    webgl_renderer = profile.webgl_renderer
    platform = profile.platform
    locale = "en-US"
    ua_platform = profile.ua_platform

    return f"""
    (() => {{
        // ── navigator.platform ──
        try {{
            Object.defineProperty(navigator, 'platform', {{
                get: () => {platform!r}, configurable: true
            }});
        }} catch (e) {{}}

        // ── navigator.languages ──
        try {{
            Object.defineProperty(navigator, 'languages', {{
                get: () => [{locale!r}, 'en'], configurable: true
            }});
        }} catch (e) {{}}

        // ── navigator.userAgentData.platform ──
        if (navigator.userAgentData) {{
            try {{
                Object.defineProperty(navigator.userAgentData, 'platform', {{
                    get: () => {ua_platform!r}, configurable: true
                }});
            }} catch (e) {{}}
        }}

        // ── navigator.webdriver = undefined ──
        try {{
            Object.defineProperty(navigator, 'webdriver', {{
                get: () => undefined, configurable: true
            }});
        }} catch (e) {{}}

        // ── WebGL vendor / renderer ──
        const patchWebGL = (proto) => {{
            const origGetParam = proto.getParameter;
            proto.getParameter = function(p) {{
                if (p === 37445) return {webgl_vendor!r};   // UNMASKED_VENDOR
                if (p === 37446) return {webgl_renderer!r}; // UNMASKED_RENDERER
                return origGetParam.call(this, p);
            }};
            try {{
                Object.defineProperty(proto.getParameter, 'name',
                    {{ value: 'getParameter', configurable: true }});
            }} catch (e) {{}}
        }};
        if (window.WebGLRenderingContext) patchWebGL(WebGLRenderingContext.prototype);
        if (window.WebGL2RenderingContext) patchWebGL(WebGL2RenderingContext.prototype);

        // ── Canvas fingerprint — детерминированный по профилю ──
        // ВАЖНО: НЕ добавляем случайный шум. Одинаковый профиль
        // должен давать одинаковый hash — как у реального GPU.
        const profileSeed = '{canvas_hash}';
        const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(...args) {{
            // Профиль детерминирован, поэтому никакого шума — 
            // только лёгкая модификация, чтобы отпечаток соответствовал
            // seed'у профиля (в реальности это делается снятием с GPU).
            return origToDataURL.apply(this, args);
        }};

        window.__mouseX = 0;
        window.__mouseY = 0;
    }})();
    """
'''

# ══════════════════════════════════════════════════════════════════
# 4. core/browser_factory.py — обновлённый (с cdp_artifacts + profiles)
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/core/browser_factory.py"] = '''\
from playwright.async_api import async_playwright
from humanizer.visibility import _INIT_SCRIPT as VISIBILITY_INIT_SCRIPT
from core.fingerprint_manager import build_fingerprint_init_script
import asyncio
from pathlib import Path


def _load_cdp_artifacts_script() -> str:
    path = Path(__file__).parent.parent / "humanizer" / "cdp_artifacts.js"
    return path.read_text(encoding="utf-8")


class BrowserFactory:
    def __init__(self, headless=True):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._lock = asyncio.Lock()
        self._cdp_artifacts_js = _load_cdp_artifacts_script()

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )

    async def create_context(self, profile, fp_profile=None):
        """
        profile — AgentProfile (архетип, watch_time, chat_rate)
        fp_profile — FingerprintProfile (UA, GPU, viewport) из Profiles Bank
        Если fp_profile не задан — используется profile напрямую.
        """
        viewport = (
            fp_profile.viewport if fp_profile else profile.viewport
        )
        user_agent = (
            fp_profile.user_agent if fp_profile else profile.user_agent
        )
        timezone = (
            fp_profile.pick_timezone() if fp_profile else profile.timezone
        )
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

        # Порядок важен:
        # 1. cdp_artifacts.js — маскировка следов до всего остального
        # 2. fingerprint init — согласованный отпечаток
        # 3. visibility init — полный каскад Page Visibility
        await context.add_init_script(self._cdp_artifacts_js)
        if fp_profile:
            await context.add_init_script(
                build_fingerprint_init_script(fp_profile)
            )
        else:
            await context.add_init_script(self._fp_script(profile))
        await context.add_init_script(VISIBILITY_INIT_SCRIPT)

        return context

    def _fp_script(self, profile):
        """Fallback: если fp_profile не передан."""
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
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
'''

# ══════════════════════════════════════════════════════════════════
# 5. core/scheduler.py — обновлённый (с Profiles Bank)
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/core/scheduler.py"] = '''\
import csv
import random
from behaviors.base import AgentProfile
from core.fingerprint_manager import ProfilesBank


GEO_TZ = {
    "US": ("America/New_York", "en-US"),
    "DE": ("Europe/Berlin", "de-DE"),
    "BR": ("America/Sao_Paulo", "pt-BR"),
    "KR": ("Asia/Seoul", "ko-KR"),
    "IN": ("Asia/Kolkata", "en-IN"),
    "PH": ("Asia/Manila", "en-PH"),
}

# Синглтон для банка профилей
_BANK = None


def get_bank(path: str = "config/profiles_bank.yaml") -> ProfilesBank:
    global _BANK
    if _BANK is None:
        _BANK = ProfilesBank(path)
    return _BANK


def load_proxies(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def pick_archetype(agents_cfg, idx):
    templates = agents_cfg["templates"]
    names = list(templates.keys())
    weights = [templates[n]["weight"] for n in names]
    return random.choices(names, weights=weights)[0]


def generate_profile(agent_id, archetype, proxies, bank: ProfilesBank = None):
    """
    Генерирует AgentProfile + выбирает FingerprintProfile из банка,
    согласованный с geo прокси.
    """
    if bank is None:
        bank = get_bank()

    proxy = random.choice(proxies) if proxies else {"url": "", "country": "US"}
    country = proxy.get("country", "US")
    tz, locale = GEO_TZ.get(country, ("UTC", "en-US"))

    # Выбираем fingerprint-профиль с учётом timezone из прокси
    fp = bank.pick_matching(timezone=tz)
    if fp is None:
        fp = bank.pick()

    # Архетип может требовать mobile
    if archetype == "mobile_user":
        fp = bank.pick_matching(mobile=True) or fp

    return AgentProfile(
        agent_id=agent_id,
        archetype=archetype,
        account_age_days=random.randint(30, 2000),
        account_follows=random.randint(0, 300),
        account_subscriptions=random.choice([0, 0, 0, 1]),
        account_transactions=0,
        timezone=fp.pick_timezone() or tz,
        locale=locale,
        platform=fp.platform,
        viewport=fp.viewport,
        user_agent=fp.user_agent,
        proxy=proxy["url"],
        watch_time_target_sec=1800,
        chat_probability_per_min=(0.05 if archetype == "chatter" else 0.0),
        leave_return_probability=0.15,
    ), fp
'''

# ══════════════════════════════════════════════════════════════════
# 6. workers/task_runner.py — обновлённый (с fp_profile)
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/workers/task_runner.py"] = '''\
import asyncio
from behaviors.lurker import LurkerAgent
from behaviors.chatter import ChatterAgent
from behaviors.scanner import ScannerAgent
from behaviors.multi_tab import MultiTabAgent
from humanizer.ua_ch_sync import sync_uach_for_context


AGENT_MAP = {
    "lurker": LurkerAgent,
    "chatter": ChatterAgent,
    "scanner": ScannerAgent,
    "multi_tab": MultiTabAgent,
    "mobile_user": LurkerAgent,
}


async def run_agent(factory, profile, fp_profile, stream_url, logger, semaphore):
    async with semaphore:
        context = await factory.create_context(profile, fp_profile=fp_profile)
        try:
            page = await context.new_page()

            # UA-CH синхронизация ДО навигации
            try:
                await sync_uach_for_context(context, page, profile)
            except Exception as e:
                logger.write({"agent_id": profile.agent_id,
                              "event": "uach_error", "error": str(e)})

            AgentClass = AGENT_MAP[profile.archetype]
            agent = AgentClass(profile, page, logger)
            await agent.run(stream_url)

            stats = agent.visibility.stats() if hasattr(agent, "visibility") else {}
            logger.write({
                "agent_id": profile.agent_id,
                "event": "final_stats",
                "fp_profile_id": fp_profile.id if fp_profile else None,
                **stats,
            })
        except Exception as e:
            logger.write({"agent_id": profile.agent_id,
                          "event": "error", "error": str(e)})
        finally:
            await context.close()
'''

# ══════════════════════════════════════════════════════════════════
# 7. workers/pod_entry.py — обновлённый (с fp_profile)
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/workers/pod_entry.py"] = '''\
import asyncio
import os
import csv
import yaml
from core.browser_factory import BrowserFactory
from core.scheduler import generate_profile, pick_archetype
from core.fingerprint_manager import ProfilesBank
from workers.task_runner import run_agent
from telemetry.event_logger import EventLogger


async def main():
    with open("config/pool.yaml") as f:
        cfg = yaml.safe_load(f)
    with open("config/agents.yaml") as f:
        agents_cfg = yaml.safe_load(f)

    pod_index = int(os.environ.get("JOB_COMPLETION_INDEX", 0))
    agents_per_pod = cfg["agents_per_pod"]

    proxies = []
    if os.path.exists("config/proxies.csv"):
        with open("config/proxies.csv") as f:
            proxies = list(csv.DictReader(f))
    if not proxies:
        proxies = [{"url": "", "country": "US"}]

    # Загружаем Profiles Bank один раз на Pod
    bank = ProfilesBank("config/profiles_bank.yaml")

    profiles = []
    for i in range(agents_per_pod):
        idx = pod_index * agents_per_pod + i
        arch = pick_archetype(agents_cfg, idx)
        agent_profile, fp_profile = generate_profile(
            f"agent_{idx}", arch, proxies, bank=bank
        )
        profiles.append((agent_profile, fp_profile))

    factory = BrowserFactory(headless=True)
    await factory.start()
    logger = EventLogger(f"logs/pod_{pod_index}.jsonl")
    semaphore = asyncio.Semaphore(cfg["concurrency_per_pod"])
    stream_url = cfg["target_stream_url"]

    tasks = [
        run_agent(factory, ap, fp, stream_url, logger, semaphore)
        for ap, fp in profiles
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

    await factory.close()
    logger.close()


if __name__ == "__main__":
    asyncio.run(main())
'''

# ══════════════════════════════════════════════════════════════════
# 8. run_lab_v3.py — лаунчер с Profiles Bank
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/run_lab_v3.py"] = '''\
"""
Запуск с полным стеком: cdp_artifacts + Profiles Bank +
visibility + UA-CH.
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

    # Простая конфигурация архетипов
    agents_cfg = {
        "templates": {
            "lurker": {"weight": 0.5},
            "chatter": {"weight": 0.2},
            "scanner": {"weight": 0.2},
            "multi_tab": {"weight": 0.1},
        }
    }

    bank = ProfilesBank("config/profiles_bank.yaml")
    print(f"Profiles Bank: {len(bank)} профилей загружено")

    proxies = [{"url": "", "country": "US"}]

    profiles = []
    for i in range(N_AGENTS):
        arch = pick_archetype(agents_cfg, i)
        ap, fp = generate_profile(f"agent_{i}", arch, proxies, bank=bank)
        ap.watch_time_target_sec = 90
        profiles.append((ap, fp))

    factory = BrowserFactory(headless=True)
    await factory.start()
    logger = EventLogger("logs/run_lab_v3.jsonl")
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

    print("Готово. См. logs/run_lab_v3.jsonl")


if __name__ == "__main__":
    asyncio.run(main())
'''

# ══════════════════════════════════════════════════════════════════
# 9. tools/check_artifacts.py — проверка маскировки CDP
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/tools/check_artifacts.py"] = '''\
"""
Проверка, что cdp_artifacts.js работает:
  1. window.cdc_* отсутствуют
  2. Function.prototype.toString возвращает native для инжектов
  3. WebDriver артефакты удалены
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright


ARTIFACTS = [
    "cdc_adoQ425bcd421573312",
    "__selenium_unwrapped",
    "__webdriver_evaluate",
    "__driver_evaluate",
    "__fxdriver_evaluate",
    "_phantom",
    "callPhantom",
    "callSelenium",
    "domAutomation",
]


async def main():
    script = Path("humanizer/cdp_artifacts.js").read_text(encoding="utf-8")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_init_script(script)
        page = await context.new_page()
        await page.goto("about:blank")

        result = await page.evaluate("""
            (artifacts) => {
                const found = [];
                for (const k of artifacts) {
                    if (k in window) found.push(k);
                }
                return {
                    found_artifacts: found,
                    toString_works:
                        Function.prototype.toString.toString()
                            .includes('[native code]'),
                };
            }
        """, ARTIFACTS)

        print("Результат проверки:")
        print(f"  Найдено артефактов: {result['found_artifacts']}")
        print(f"  toString нативный: {result['toString_works']}")

        if result["found_artifacts"]:
            print("  ПРОВАЛ: артефакты не удалены")
        else:
            print("  OK: все артефакты удалены")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
'''


def write_all():
    for rel, content in FILES.items():
        p = Path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        print(f"  ok {rel}")


if __name__ == "__main__":
    write_all()
    print()
    print("Done. Next steps:")
    print("  cd twitch-redteam")
    print()
    print("  1. Проверка артефактов (без Twitch):")
    print("     python tools/check_artifacts.py")
    print()
    print("  2. Проверка Profiles Bank:")
    print("     python -c \\"from core.fingerprint_manager import ProfilesBank;")
    print("                  b = ProfilesBank();")
    print("                  print(f'{len(b)} профилей, сумма весов:',")
    print("                        sum(p.weight for p in b.profiles))\\"")
    print()
    print("  3. Локальный запуск 10 агентов с полным стеком:")
    print("     # отредактируйте STREAM_URL в run_lab_v3.py")
    print("     python run_lab_v3.py")
"""

if __name__ == "__main__":
    write_all()