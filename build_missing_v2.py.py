#!/usr/bin/env python3
# build_missing.py — добавляет недостающие файлы в twitch-research-v8/
# v8.2: canvas через subpixel, YAML через safe_load, проверка Linux/macOS,
#       seed вычисляется в Python
import os
from pathlib import Path

ROOT = Path("twitch-research-v8")
FILES = {}

# ══════════════════════════════════════════════════════════════════════════
# 1. humanizer/cdp_artifacts.js
# ══════════════════════════════════════════════════════════════════════════

FILES["red-team/humanizer/cdp_artifacts.js"] = r"""
/*
 * Маскировка следов CDP/WebDriver в runtime.
 * Инжектится через add_init_script до первой навигации.
 *
 * v8: добавлены __playwright__binding__ и __pw_* (patchright leak).
 */
(() => {
    if (window.__cdp_artifacts_installed) return;
    window.__cdp_artifacts_installed = true;

    const nativeToString = Function.prototype.toString;
    const nativeToStringStr = nativeToString.toString();

    Function.prototype.toString = function() {
        if (this && this.__cdp_injected__) {
            const name = this.name || '';
            return `function ${name}() { [native code] }`;
        }
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
        '__playwright__binding__',
        '__pwInitScripts',
        '__playwright_evaluate',
        '__pw_manual',
        '__pw_binding__',
    ];

    for (const key of artifacts) {
        try { delete window[key]; } catch (e) {}
        try { delete document[key]; } catch (e) {}
        try {
            Object.defineProperty(window, key, {
                get: () => undefined,
                configurable: true,
                enumerable: false,
            });
        } catch (e) {}
    }

    const cdpPropRegex = /^__cdp_|^cdc_|^__webdriver_|^__selenium_|^__playwright_|^__pw_/;
    const originalDefineProperty = Object.defineProperty;
    Object.defineProperty = function(obj, prop, descriptor) {
        if (typeof prop === 'string' && cdpPropRegex.test(prop)) {
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

    const nativeConsoleDebug = console.debug;
    console.debug = function(...args) {
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

# ══════════════════════════════════════════════════════════════════════════
# 2. config/profiles_bank.yaml
# ══════════════════════════════════════════════════════════════════════════

FILES["red-team/config/profiles_bank.yaml"] = """\
# Profiles Bank: реальные комбинации GPU/UA/viewport/canvas hash
# Веса — на основе Steam Hardware Survey (2024-2025).
#
# ВАЖНО:
#   1. canvas_hash и webgl_renderer должны быть сняты с РЕАЛЬНЫХ машин.
#      Здесь — placeholder'ы. Перед запуском замените на реальные.
#   2. Профили с одинаковым (platform, gpu_family, viewport) ОБЯЗАНЫ
#      иметь одинаковый canvas_hash.
#   3. Linux-профили используют нативный GL renderer, БЕЗ ANGLE.

profiles:
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
    canvas_hash: "a3f2c8e1b9d4f7a2e5c8b1d4f7a2e5c8"
    timezone_pool: ["America/Chicago", "Europe/Warsaw", "Europe/Paris"]

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
    canvas_hash: "a3f2c8e1b9d4f7a2e5c8b1d4f7a2e5c8"
    timezone_pool: ["America/New_York", "Europe/Berlin"]

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
    webgl_vendor: "AMD"
    webgl_renderer: "AMD Radeon RX 6700 XT (RADV NAVI22) (0x73df)"
    canvas_hash: "c1f0e6a9d7b2f5c0e3a6d9b2f5c0e3a6"
    timezone_pool: ["Europe/Berlin", "Europe/Helsinki"]

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

# Сумма весов: 1.00
"""

# ══════════════════════════════════════════════════════════════════════════
# 3. core/fingerprint_manager.py
# ══════════════════════════════════════════════════════════════════════════

FILES["red-team/core/fingerprint_manager.py"] = '''\
"""
Profiles Bank: выбор согласованного fingerprint-профиля.

v8.2:
  ПАТЧ 1: Canvas-модификация через субпиксельные координаты и
          imageSmoothingEnabled, а не через пиксель в углу.

  ПАТЧ 4: Seed вычисляется в Python один раз, передаётся в JS готовым
          числом. В JS нет хеш-функции — меньше работы на каждый вызов
          и меньше сигнатур в Function.prototype.toString.
"""
from __future__ import annotations

import json
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
    def __init__(self, path: str = "config/profiles_bank.yaml"):
        self.path = path
        self.profiles: list[FingerprintProfile] = []
        self._load()

    def _load(self):
        path = Path(self.path)
        if not path.exists():
            raise FileNotFoundError(
                f"Файл банка профилей не найден: {path.resolve()}"
            )
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise ValueError(f"Ошибка парсинга YAML в {self.path}: {e}")

        if "profiles" not in data:
            raise ValueError(
                f"В файле {self.path} отсутствует ключ 'profiles'"
            )

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
        weights = [p.weight for p in self.profiles]
        return random.choices(self.profiles, weights=weights, k=1)[0]

    def pick_matching(self, timezone: Optional[str] = None,
                      mobile: Optional[bool] = None) -> FingerprintProfile:
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


def _compute_seed(canvas_hash: str) -> int:
    """
    ПАТЧ 4: та же hash-функция, что была в JS ((h << 5) - h + c),
    но вычисляется в Python один раз.

    Эмуляция signed 32-bit int как в JS:
      - h & 0xFFFFFFFF — оставляет только 32 младших бита
      - если старший бит установлен — это отрицательное число
      - abs() даёт модуль
    """
    h = 0
    for ch in canvas_hash:
        h = ((h << 5) - h + ord(ch)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return abs(h)


def _subpixel_offset(seed: int) -> tuple[float, float]:
    """
    Детерминированные субпиксельные смещения на основе seed.
    Диапазон: 0.1-0.9 для x, 0.1-0.9 для y.
    """
    x = 0.1 + ((seed & 0xFF) % 9) * 0.1
    y = 0.1 + (((seed >> 8) & 0xFF) % 9) * 0.1
    return (round(x, 2), round(y, 2))


def build_fingerprint_init_script(profile: FingerprintProfile) -> str:
    """
    JS-скрипт, переопределяющий navigator.*, WebGL vendor/renderer
    и Canvas согласованно с профилем.

    Canvas: субпиксельные координаты + imageSmoothingEnabled.
    Детерминировано по profile.canvas_hash. Не трогает угловые пиксели.
    """
    platform = json.dumps(profile.platform)
    locale = json.dumps("en-US")
    ua_platform = json.dumps(profile.ua_platform)
    webgl_vendor = json.dumps(profile.webgl_vendor)
    webgl_renderer = json.dumps(profile.webgl_renderer)

    seed = _compute_seed(profile.canvas_hash)
    sx, sy = _subpixel_offset(seed)
    smooth = bool(seed & 1)

    seed_js = json.dumps(seed)
    sx_js = json.dumps(sx)
    sy_js = json.dumps(sy)
    smooth_js = json.dumps(smooth)

    return f"""
    (() => {{
        try {{
            Object.defineProperty(navigator, 'platform', {{
                get: () => {platform}, configurable: true
            }});
        }} catch (e) {{}}
        try {{
            Object.defineProperty(navigator, 'languages', {{
                get: () => [{locale}, 'en'], configurable: true
            }});
        }} catch (e) {{}}
        if (navigator.userAgentData) {{
            try {{
                Object.defineProperty(navigator.userAgentData, 'platform', {{
                    get: () => {ua_platform}, configurable: true
                }});
            }} catch (e) {{}}
        }}
        try {{
            Object.defineProperty(navigator, 'webdriver', {{
                get: () => undefined, configurable: true
            }});
        }} catch (e) {{}}

        const patchWebGL = (proto) => {{
            const origGetParam = proto.getParameter;
            proto.getParameter = function(p) {{
                if (p === 37445) return {webgl_vendor};
                if (p === 37446) return {webgl_renderer};
                return origGetParam.call(this, p);
            }};
            try {{
                Object.defineProperty(proto.getParameter, 'name',
                {{ value: 'getParameter', configurable: true }});
            }} catch (e) {{}}
        }};
        if (window.WebGLRenderingContext) patchWebGL(WebGLRenderingContext.prototype);
        if (window.WebGL2RenderingContext) patchWebGL(WebGL2RenderingContext.prototype);

        // ── ПАТЧ 1 + ПАТЧ 4: Canvas через субпиксель ──
        const SUBPIXEL_X = {sx_js};
        const SUBPIXEL_Y = {sy_js};
        const SMOOTHING = {smooth_js};

        const origFillText = CanvasRenderingContext2D.prototype.fillText;
        CanvasRenderingContext2D.prototype.fillText = function(text, x, y, ...rest) {{
            const nx = (typeof x === 'number') ? x + SUBPIXEL_X : x;
            const ny = (typeof y === 'number') ? y + SUBPIXEL_Y : y;
            return origFillText.call(this, text, nx, ny, ...rest);
        }};

        const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
        CanvasRenderingContext2D.prototype.getImageData = function(...args) {{
            if (this.imageSmoothingEnabled !== SMOOTHING) {{
                this.imageSmoothingEnabled = SMOOTHING;
            }}
            return origGetImageData.apply(this, args);
        }};

        window.__mouseX = 0;
        window.__mouseY = 0;
    }})();
    """
'''


# ══════════════════════════════════════════════════════════════════════════
# Проверки после записи
# ══════════════════════════════════════════════════════════════════════════

def verify_canvas_consistency():
    """
    ПАТЧ 2: использует yaml.safe_load вместо regex.
    ПАТЧ 3: проверяет Linux-профили (без ANGLE, без Google Inc.)
            и macOS-профили (Apple/Intel).
    """
    import yaml

    yaml_path = ROOT / "red-team/config/profiles_bank.yaml"
    if not yaml_path.exists():
        return

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    profiles = data["profiles"]

    groups = {}
    for p in profiles:
        renderer = p.get("webgl_renderer", "")
        viewport = (p["viewport"]["width"], p["viewport"]["height"])

        if "NVIDIA" in renderer:
            family = "NVIDIA"
        elif "AMD" in renderer or "Radeon" in renderer:
            family = "AMD"
        elif "Intel" in renderer:
            family = "Intel"
        elif "Apple" in renderer:
            family = "Apple"
        elif "Adreno" in renderer:
            family = "Qualcomm"
        else:
            family = "Other"

        key = (family, viewport)
        groups.setdefault(key, []).append(p)

    print("\nПроверка согласованности canvas_hash:")
    issues = 0
    for key, items in groups.items():
        if len(items) < 2:
            continue
        hashes = {p["canvas_hash"] for p in items}
        if len(hashes) > 1:
            print(f"  ✗ {key}: {len(hashes)} разных canvas_hash "
                  f"у {len(items)} профилей")
            for p in items:
                print(f"      {p['id']}: {p['canvas_hash']}")
            issues += 1
        else:
            print(f"  ✓ {key}: {len(items)} профилей, 1 canvas_hash")

    # ── Linux-профили: нативный GL, без ANGLE, без Google Inc. ──
    print("\nПроверка Linux-профилей:")
    for p in profiles:
        if p["platform"] == "Linux x86_64":
            renderer = p.get("webgl_renderer", "")
            vendor = p.get("webgl_vendor", "")
            if "ANGLE" in renderer:
                print(f"  ✗ {p['id']}: Linux-профиль использует ANGLE "
                      f"(должен быть нативный GL)")
                issues += 1
            elif "Google Inc." in vendor:
                print(f"  ✗ {p['id']}: Linux-профиль имеет vendor "
                      f"'Google Inc.' (должен быть 'AMD'/'NVIDIA'/'Intel')")
                issues += 1
            else:
                print(f"  ✓ {p['id']}: нативный GL renderer")

    # ── macOS-профили: Apple/Intel, без ANGLE ──
    print("\nПроверка macOS-профилей:")
    for p in profiles:
        if p["platform"] == "MacIntel":
            renderer = p.get("webgl_renderer", "")
            vendor = p.get("webgl_vendor", "")
            if "ANGLE" in renderer:
                print(f"  ✗ {p['id']}: macOS-профиль использует ANGLE "
                      f"(должен быть Metal/OpenGL)")
                issues += 1
            elif "Google Inc." in vendor:
                print(f"  ✗ {p['id']}: macOS-профиль имеет vendor "
                      f"'Google Inc.' (должен быть 'Apple Inc.'/'Intel Inc.')")
                issues += 1
            else:
                print(f"  ✓ {p['id']}: macOS-совместимый renderer")

    # ── Android-профили: Qualcomm ──
    print("\nПроверка Android-профилей:")
    for p in profiles:
        if p["platform"] == "mobile":
            vendor = p.get("webgl_vendor", "")
            renderer = p.get("webgl_renderer", "")
            if "Adreno" not in renderer:
                print(f"  ✗ {p['id']}: Android-профиль без Adreno renderer")
                issues += 1
            else:
                print(f"  ✓ {p['id