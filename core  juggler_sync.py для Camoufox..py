# core/juggler_sync.py
"""
Синхронизация fingerprint для Camoufox через Juggler.

Camoufox не поддерживает CDP. Fingerprint-параметры передаются:
  - Глобально: через CAMOU_CONFIG environment variable
  - Per-context: через generate_context_fingerprint + addInitScript

Модуль конвертирует FingerprintProfile (Profiles Bank) в оба формата.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Optional

from core.fingerprint_manager import FingerprintProfile


# Маппинг platform → Camoufox navigator.platform
PLATFORM_MAP = {
    "Win32": "Win32",
    "MacIntel": "MacIntel",
    "Linux x86_64": "Linux x86_64",
    "mobile": "Linux armv8l",
}

# Маппинг platform → Camoufox ua_platform
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
    """
    Строит config dict для Camoufox.

    Ключи используют точечную нотацию (navigator.userAgent,
    screen.width и т.д.) — это формат, который понимает
    Camoufox fingerprint injection.
    """
    tz = timezone or fp.pick_timezone() or "UTC"

    config = {
        # ── Navigator ──
        "navigator.userAgent": fp.user_agent,
        "navigator.platform": PLATFORM_MAP.get(fp.platform, fp.platform),
        "navigator.oscpu": _derive_oscpu(fp.platform),
        "navigator.language": locale,
        "navigator.languages": [locale, "en"],
        "navigator.hardwareConcurrency": _pick_cores(fp),
        "navigator.maxTouchPoints": 0 if not fp.mobile else 5,
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

        # ── DevicePixelRatio ──
        "window.devicePixelRatio": fp.device_scale_factor,

        # ── WebGL ──
        "webGl:vendor": fp.webgl_vendor,
        "webGl:renderer": fp.webgl_renderer,

        # ── Timezone ──
        "timezone": tz,

        # ── Geolocation (если нужно — подтянуть из proxy) ──
        # "geolocation:latitude": ...,
        # "geolocation:longitude": ...,
    }

    # mobile-специфика
    if fp.mobile:
        config["navigator.maxTouchPoints"] = 5
        config["navigator.userAgent"] = fp.user_agent  # Mobile в UA

    return config


def _derive_oscpu(platform: str) -> str:
    """Camoufox требует oscpu — для Firefox-совместимости."""
    mapping = {
        "Win32": "Windows NT 10.0; Win64; x64",
        "MacIntel": "Intel Mac OS X 10.15",
        "Linux x86_64": "Linux x86_64",
        "mobile": "Linux armv8l",
    }
    return mapping.get(platform, "Linux x86_64")


def _pick_cores(fp: FingerprintProfile) -> int:
    """Согласованный с профилем hardwareConcurrency."""
    # Реальные распределения: 4/8/12/16
    if fp.platform == "mobile":
        return 8
    if "RTX 40" in fp.webgl_renderer or "M2" in fp.webgl_renderer:
        return 16
    if "RTX 30" in fp.webgl_renderer or "M1" in fp.webgl_renderer:
        return 12
    return 8


def export_camou_config(
    fp: FingerprintProfile,
    path: str = "camou_config.json",
    timezone: Optional[str] = None,
) -> str:
    """
    Экспорт config в JSON-файл для CAMOU_CONFIG env var.
    Используется для глобального режима (один fingerprint на браузер).
    """
    config = build_camoufox_config(fp, timezone=timezone)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    return path


def config_to_env(config: dict) -> dict:
    """
    Конвертирует config в env-переменные для запуска Camoufox.
    """
    env = dict(os.environ)
    env["CAMOU_CONFIG"] = json.dumps(config)
    return env


def build_juggler_init_script(config: dict) -> str:
    """
    Fallback: генерирует addInitScript, который применяет часть
    config на уровне JS. Используется, если per-context config
    через new_context не работает.

    ВАЖНО: Camoufox инжектит fingerprint на уровне C++, поэтому
    этот скрипт — только для полей, которые Camoufox не покрывает
    (например, navigator.userAgentData, если он есть).
    """
    ua = config.get("navigator.userAgent", "")
    platform = config.get("navigator.platform", "")
    languages = config.get("navigator.languages", ["en-US", "en"])
    webgl_vendor = config.get("webGl:vendor", "")
    webgl_renderer = config.get("webGl:renderer", "")

    return f"""
    (() => {{
        try {{
            Object.defineProperty(navigator, 'platform', {{
                get: () => {platform!r}, configurable: true
            }});
        }} catch (e) {{}}
        try {{
            Object.defineProperty(navigator, 'languages', {{
                get: () => {languages!r}, configurable: true
            }});
        }} catch (e) {{}}
        // WebGL fallback — если C++ патч не сработал
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
    """
    High-level API для Camoufox.

    Использование:
        sync = JugglerSync(fp_profile, agent_profile)
        config = sync.build_config()
        # Передать в AsyncCamoufox(config=config) или
        # context = await browser.new_context(**config)
    """

    def __init__(
        self,
        fp: FingerprintProfile,
        *,
        timezone: Optional[str] = None,
        locale: str = "en-US",
    ):
        self.fp = fp
        self.timezone = timezone or fp.pick_timezone()
        self.locale = locale
        self._config: Optional[dict] = None

    def build_config(self) -> dict:
        if self._config is None:
            self._config = build_camoufox_config(
                self.fp, timezone=self.timezone, locale=self.locale
            )
        return self._config

    def export_json(self, path: str = "camou_config.json") -> str:
        return export_camou_config(self.fp, path, self.timezone)

    def env(self) -> dict:
        return config_to_env(self.build_config())

    def init_script(self) -> str:
        return build_juggler_init_script(self.build_config())

    def verify_config(self) -> dict:
        """Проверка согласованности config."""
        c = self.build_config()
        issues = []

        # UA platform vs navigator.platform
        ua = c.get("navigator.userAgent", "")
        plat = c.get("navigator.platform", "")
        if "Windows" in ua and plat != "Win32":
            issues.append(f"UA Windows vs platform {plat}")
        if "Macintosh" in ua and plat != "MacIntel":
            issues.append(f"UA Mac vs platform {plat}")
        if "Linux" in ua and "Linux" not in plat:
            issues.append(f"UA Linux vs platform {plat}")

        # WebGL vendor consistency
        vendor = c.get("webGl:vendor", "")
        renderer = c.get("webGl:renderer", "")
        if plat == "Win32" and "ANGLE" not in renderer:
            issues.append(f"Win32 platform vs non-ANGLE renderer: {renderer}")
        if plat == "MacIntel" and "Apple" not in vendor:
            issues.append(f"MacIntel platform vs non-Apple vendor: {vendor}")

        # Timezone vs locale
        tz = c.get("timezone", "")
        loc = c.get("navigator.language", "")
        if tz.startswith("Asia/") and loc.startswith("de-"):
            issues.append(f"Asia timezone + German locale")

        return {
            "consistent": len(issues) == 0,
            "issues": issues,
            "config": c,
        }