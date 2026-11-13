#!/usr/bin/env python3
# bootstrap2.py — добавляет visibility + UA-CH в существующий Red Team
import os
from pathlib import Path

FILES = {}

# ══════════════════════════════════════════════════════════════════
# 1. humanizer/visibility.py — JS-фасад Page Visibility
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/humanizer/visibility.py"] = '''\
"""
JS-фасад Page Visibility с полным синхронным каскадом.
Переопределяет document.hidden, visibilityState, hasFocus и rAF.
"""
from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager
from typing import Literal

from playwright.async_api import Page


_INIT_SCRIPT = r"""
(() => {
    if (window.__visibility_cascade) return;

    let state = {
        hidden: false,
        visibilityState: 'visible',
        focused: true,
        reason: 'initial',
        lastChangeTs: performance.now(),
    };

    const nativeRaf = window.requestAnimationFrame;
    const nativeCancelRaf = window.cancelAnimationFrame;
    const suspendedRaf = new Map();
    let rafIdCounter = 1;

    try {
        Object.defineProperty(document, 'hidden', {
            configurable: false, enumerable: true,
            get() { return state.hidden; },
        });
        Object.defineProperty(document, 'visibilityState', {
            configurable: false, enumerable: true,
            get() { return state.visibilityState; },
        });
    } catch (e) {
        // Уже переопределено — игнорируем
    }

    Document.prototype.hasFocus = function() { return state.focused; };

    window.requestAnimationFrame = function(cb) {
        const id = rafIdCounter++;
        if (state.hidden) {
            suspendedRaf.set(id, cb);
            return id;
        }
        return nativeRaf.call(window, cb);
    };
    window.cancelAnimationFrame = function(id) {
        if (suspendedRaf.has(id)) {
            suspendedRaf.delete(id);
            return;
        }
        return nativeCancelRaf.call(window, id);
    };

    window.__visibility_cascade = {
        getState() { return { ...state }; },

        hide(reason) {
            if (state.hidden) return { ...state };
            state.hidden = true;
            state.visibilityState = 'hidden';
            state.focused = false;
            state.reason = reason || 'hide';
            state.lastChangeTs = performance.now();

            document.dispatchEvent(new Event('visibilitychange'));
            window.dispatchEvent(new Event('blur'));
            if (reason === 'unload' || reason === 'freeze') {
                window.dispatchEvent(new PageTransitionEvent('pagehide',
                    { persisted: reason === 'freeze' }));
            }
            return { ...state };
        },

        show(reason) {
            if (!state.hidden) return { ...state };
            const wasUnloaded = state.reason === 'unload' || state.reason === 'freeze';
            state.hidden = false;
            state.visibilityState = 'visible';
            state.focused = true;
            state.reason = reason || 'show';
            state.lastChangeTs = performance.now();

            window.dispatchEvent(new Event('focus'));
            document.dispatchEvent(new Event('visibilitychange'));
            if (wasUnloaded) {
                window.dispatchEvent(new PageTransitionEvent('pageshow',
                    { persisted: false }));
            }

            const pending = Array.from(suspendedRaf.entries());
            suspendedRaf.clear();
            nativeRaf.call(window, () => {
                for (const [id, cb] of pending) {
                    try { cb(performance.now()); } catch (_) {}
                }
            });
            return { ...state };
        },
    };
})();
"""


Reason = Literal["tab_switch", "minimize", "freeze", "unload", "manual"]


class VisibilityCascade:
    def __init__(self, page: Page, *, verbose: bool = False):
        self.page = page
        self.verbose = verbose
        self._is_hidden = False
        self._lock = asyncio.Lock()

    async def install(self) -> None:
        installed = await self.page.evaluate(
            "() => !!window.__visibility_cascade"
        )
        if not installed:
            await self.page.add_init_script(_INIT_SCRIPT)
            await self.page.evaluate(_INIT_SCRIPT)

    async def get_state(self) -> dict:
        return await self.page.evaluate(
            "() => window.__visibility_cascade.getState()"
        )

    async def hide(self, reason: Reason = "tab_switch") -> dict:
        async with self._lock:
            if self._is_hidden:
                return await self.get_state()
            new_state = await self.page.evaluate(
                "(r) => window.__visibility_cascade.hide(r)", reason
            )
            self._is_hidden = True
            if self.verbose:
                print(f"[visibility] hide({reason})")
            return new_state

    async def show(self, reason: Reason = "tab_switch") -> dict:
        async with self._lock:
            if not self._is_hidden:
                return await self.get_state()
            new_state = await self.page.evaluate(
                "(r) => window.__visibility_cascade.show(r)", reason
            )
            self._is_hidden = False
            if self.verbose:
                print(f"[visibility] show({reason})")
            return new_state

    async def tab_switch(self, duration_sec: float) -> None:
        await self.hide("tab_switch")
        await asyncio.sleep(duration_sec)
        await self.show("tab_switch")

    async def maybe_switch_away(
        self, *, probability: float = 0.08,
        min_duration: float = 3.0, max_duration: float = 45.0,
    ) -> bool:
        if random.random() >= probability:
            return False
        import math
        mu = math.log((min_duration + max_duration) / 4)
        duration = min(
            max(random.lognormvariate(mu, 0.6), min_duration),
            max_duration,
        )
        await self.tab_switch(duration)
        return True


@asynccontextmanager
async def background(page: Page, reason: Reason = "tab_switch", *, verbose: bool = False):
    cascade = VisibilityCascade(page, verbose=verbose)
    await cascade.install()
    await cascade.hide(reason)
    try:
        yield cascade
    finally:
        await cascade.show(reason)
'''

# ══════════════════════════════════════════════════════════════════
# 2. humanizer/lazy_cdp.py — отложенный attach + DevTools-маскировка
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/humanizer/lazy_cdp.py"] = '''\
"""
Lazy CDP attach: создаёт сессию только при первом send(),
маскирует attach под DevTools-handshake.
"""
from __future__ import annotations

import asyncio
import random
from typing import Optional

from playwright.async_api import Page, CDPSession


class LazyCDPSession:
    def __init__(self, page: Page, *, warmup: bool = True, verbose: bool = False):
        self.page = page
        self._session: Optional[CDPSession] = None
        self._lock = asyncio.Lock()
        self._failed = False
        self._warmup = warmup
        self.verbose = verbose
        self.attach_count = 0
        self.send_count = 0

    async def _maybe_attach(self) -> Optional[CDPSession]:
        if self._session is not None:
            return self._session
        if self._failed:
            return None
        async with self._lock:
            if self._session is not None:
                return self._session
            if self._failed:
                return None
            try:
                session = await self.page.context.new_cdp_session(self.page)
                if self._warmup:
                    await self._warmup_sequence(session)
                self._session = session
                self.attach_count += 1
                if self.verbose:
                    print("[lazy-cdp] attached")
                return session
            except Exception as e:
                self._failed = True
                if self.verbose:
                    print(f"[lazy-cdp] attach failed: {e}")
                return None

    async def _warmup_sequence(self, session: CDPSession) -> None:
        seq = [("Browser.getVersion", {}), ("Target.getTargets", {})]
        optional = [
            ("Runtime.enable", {}),
            ("Log.enable", {}),
            ("Console.enable", {}),
            ("Page.enable", {}),
            ("Network.enable", {}),
        ]
        if random.random() < 0.7:
            seq.extend(optional)
        else:
            seq.extend([("Runtime.enable", {}), ("Page.enable", {})])
        if random.random() < 0.3:
            seq.append(("Debugger.enable", {}))
        for method, params in seq:
            try:
                await session.send(method, params)
            except Exception:
                pass

    async def send(self, method: str, params: dict | None = None) -> dict | None:
        session = await self._maybe_attach()
        if session is None:
            return None
        self.send_count += 1
        try:
            return await session.send(method, params or {})
        except Exception as e:
            if self.verbose:
                print(f"[lazy-cdp] send({method}) failed: {e}")
            return None

    @property
    def is_attached(self) -> bool:
        return self._session is not None


class LazyVisibilityCDP:
    """
    Замена CDPVisibilityCascade. CDP-сессия создаётся только при
    первом freeze/minimize, tab_switch работает через JS-фасад.
    """
    def __init__(self, page: Page, *, verbose: bool = False):
        self.page = page
        self.verbose = verbose
        self._cdp = LazyCDPSession(page, warmup=True, verbose=verbose)
        self._js_hidden = False
        self._frozen = False
        self._lock = asyncio.Lock()

    async def install(self) -> None:
        if self.verbose:
            print("[lazy-visibility] ready")

    async def hide(self, reason: str = "tab_switch") -> None:
        async with self._lock:
            if self._js_hidden:
                return
            try:
                await self.page.evaluate(
                    "(r) => window.__visibility_cascade.hide(r)", reason
                )
                self._js_hidden = True
            except Exception:
                pass

            if reason == "freeze":
                await self._cdp.send(
                    "Page.setWebLifecycleState", {"state": "frozen"}
                )
                self._frozen = True
            elif reason == "minimize":
                await self._cdp.send(
                    "Emulation.setDeviceMetricsOverride",
                    {"width": 0, "height": 0,
                     "deviceScaleFactor": 0, "mobile": False},
                )

    async def show(self, reason: str = "tab_switch") -> None:
        async with self._lock:
            if not self._js_hidden:
                return
            if reason == "minimize":
                await self._cdp.send("Emulation.clearDeviceMetricsOverride")
            try:
                await self.page.evaluate(
                    "(r) => window.__visibility_cascade.show(r)", reason
                )
                self._js_hidden = False
            except Exception:
                pass
            if reason == "freeze":
                await self._cdp.send(
                    "Page.setWebLifecycleState", {"state": "active"}
                )
                self._frozen = False

    async def tab_switch(self, duration_sec: float) -> None:
        await self.hide("tab_switch")
        await asyncio.sleep(duration_sec)
        await self.show("tab_switch")

    async def minimize_window(self, duration_sec: float) -> None:
        await self.hide("minimize")
        await asyncio.sleep(duration_sec)
        await self.show("minimize")

    async def freeze_and_resume(self, duration_sec: float) -> None:
        await self.hide("freeze")
        await asyncio.sleep(duration_sec)
        await self.show("freeze")

    def stats(self) -> dict:
        return {
            "cdp_attached": self._cdp.is_attached,
            "attach_count": self._cdp.attach_count,
            "send_count": self._cdp.send_count,
            "js_hidden": self._js_hidden,
            "frozen": self._frozen,
        }
'''

# ══════════════════════════════════════════════════════════════════
# 3. humanizer/ua_ch_sync.py — синхронизация UA-CH
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/humanizer/ua_ch_sync.py"] = '''\
"""
Синхронизация User-Agent Client Hints через CDP.
Network.setUserAgentOverride — единственный способ согласовать
HTTP-заголовки Sec-CH-UA-* и navigator.userAgentData.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import Page, CDPSession


_GREASE_CHARS = [" ", "(", ")", ":", "-", ".", "/", "!", ",", "?"]


def _grease_brand() -> dict:
    a = random.choice(_GREASE_CHARS)
    b = random.choice(_GREASE_CHARS)
    return {"brand": f"Not{a}{b}Brand",
            "version": str(random.choice([8, 24, 99]))}


@dataclass
class UACHProfile:
    user_agent: str
    platform: str
    platform_version: str
    architecture: str
    bitness: str
    mobile: bool
    brands: list = field(default_factory=list)
    full_version_list: list = field(default_factory=list)
    ua_full_version: str = ""
    ua_major_version: str = ""
    model: str = ""


def generate_uach_profile(*, platform="Windows", version="141.0.7444.60",
                          mobile=False, model=""):
    major = version.split(".")[0]
    if platform == "Windows":
        platform_version = random.choice(["10.0.0", "15.0.0"])
        architecture, bitness = "x86", "64"
        ua_platform_str = "Windows NT 10.0; Win64; x64"
    elif platform == "macOS":
        platform_version = random.choice(["13.6.0", "14.5.0", "15.0.0"])
        architecture, bitness = "arm", "64"
        ua_platform_str = "Macintosh; Intel Mac OS X 10_15_7"
    elif platform == "Linux":
        platform_version = ""
        architecture, bitness = "x86", "64"
        ua_platform_str = "X11; Linux x86_64"
    else:
        platform_version = "14"
        architecture, bitness = "arm", "64"
        model = model or "Pixel 7"
        ua_platform_str = f"Linux; Android 14; {model}"

    brands = [
        {"brand": "Chromium", "version": major},
        {"brand": "Google Chrome", "version": major},
        _grease_brand(),
    ]
    random.shuffle(brands)
    full_list = [
        {"brand": "Chromium", "version": version},
        {"brand": "Google Chrome", "version": version},
        _grease_brand(),
    ]
    mobile_part = " Mobile" if mobile else ""
    ua = (
        f"Mozilla/5.0 ({ua_platform_str}) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{major}.0.0.0{mobile_part} Safari/537.36"
    )
    return UACHProfile(
        user_agent=ua, platform=platform, platform_version=platform_version,
        architecture=architecture, bitness=bitness, mobile=mobile,
        brands=brands, full_version_list=full_list,
        ua_full_version=version, ua_major_version=major, model=model,
    )


class UACHSynchronizer:
    def __init__(self, page: Page, profile: UACHProfile):
        self.page = page
        self.profile = profile
        self._session: Optional[CDPSession] = None
        self._applied = False

    async def _ensure_session(self) -> CDPSession:
        if self._session is None:
            self._session = await self.page.context.new_cdp_session(self.page)
        return self._session

    def _metadata(self) -> dict:
        return {
            "brands": self.profile.brands,
            "fullVersionList": self.profile.full_version_list,
            "fullVersion": self.profile.ua_full_version,
            "platform": self.profile.platform,
            "platformVersion": self.profile.platform_version,
            "architecture": self.profile.architecture,
            "model": self.profile.model,
            "mobile": self.profile.mobile,
            "bitness": self.profile.bitness,
            "wow64": False,
        }

    async def apply(self) -> None:
        session = await self._ensure_session()
        try:
            await session.send("Network.enable")
        except Exception:
            pass
        await session.send("Network.setUserAgentOverride", {
            "userAgent": self.profile.user_agent,
            "userAgentMetadata": self._metadata(),
        })
        self._applied = True

    @property
    def applied(self) -> bool:
        return self._applied


async def sync_uach_for_context(context, page, profile):
    """
    Вызывать сразу после page = await context.new_page(),
    но ДО первого page.goto().
    """
    platform_map = {
        "Win32": "Windows", "MacIntel": "macOS",
        "Linux x86_64": "Linux", "mobile": "Android",
    }
    uach_platform = platform_map.get(profile.platform, "Windows")
    uach = generate_uach_profile(
        platform=uach_platform, version="141.0.7444.60",
        mobile=(profile.platform == "mobile"),
    )
    sync = UACHSynchronizer(page, uach)
    await sync.apply()
    return sync
'''

# ══════════════════════════════════════════════════════════════════
# 4. core/browser_factory.py — обновлённый (с visibility init_script)
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/core/browser_factory.py"] = '''\
from playwright.async_api import async_playwright
from humanizer.visibility import _INIT_SCRIPT as VISIBILITY_INIT_SCRIPT
import asyncio


class BrowserFactory:
    def __init__(self, headless=True):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._lock = asyncio.Lock()

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

    async def create_context(self, profile):
        async with self._lock:
            context = await self._browser.new_context(
                viewport=profile.viewport,
                user_agent=profile.user_agent,
                locale=profile.locale,
                timezone_id=profile.timezone,
                proxy={"server": profile.proxy} if profile.proxy else None,
                has_touch=profile.platform == "mobile",
                is_mobile=profile.platform == "mobile",
            )
        await context.add_init_script(self._fp_script(profile))
        await context.add_init_script(VISIBILITY_INIT_SCRIPT)
        return context

    def _fp_script(self, profile):
        return f"""
        (() => {{
            try {{
                Object.defineProperty(navigator, 'platform',
                    {{ get: () => {profile.platform!r} }});
                Object.defineProperty(navigator, 'languages',
                    {{ get: () => [{profile.locale!r}, 'en'] }});
                Object.defineProperty(navigator, 'webdriver',
                    {{ get: () => undefined }});
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
# 5. behaviors/base.py — обновлённый (с attach_lazy_cascade)
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/behaviors/base.py"] = '''\
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import asyncio
import random

from humanizer.lazy_cdp import LazyVisibilityCDP


@dataclass
class AgentProfile:
    agent_id: str
    archetype: str
    account_age_days: int
    account_follows: int
    account_subscriptions: int
    account_transactions: int
    timezone: str
    locale: str
    platform: str
    viewport: dict
    user_agent: str
    proxy: Optional[str] = None
    watch_time_target_sec: int = 1800
    chat_probability_per_min: float = 0.0
    leave_return_probability: float = 0.15
    tab_blur_probability_per_min: float = 0.05


@dataclass
class AgentState:
    entered_at: Optional[datetime] = None
    total_watch_sec: int = 0
    chat_sent: int = 0
    mouse_events: int = 0
    keyboard_events: int = 0
    tab_blur_events: int = 0
    event_log: list = field(default_factory=list)


class BaseAgent(ABC):
    def __init__(self, profile, page, logger, *, verbose_visibility=False):
        self.profile = profile
        self.page = page
        self.logger = logger
        self.state = AgentState()
        self.visibility = LazyVisibilityCDP(page, verbose=verbose_visibility)

    async def install_visibility(self):
        await self.visibility.install()

    def _log(self, event, **kwargs):
        payload = {"ts": datetime.utcnow().isoformat(),
                   "agent_id": self.profile.agent_id,
                   "event": event, **kwargs}
        self.state.event_log.append(payload)
        if self.logger:
            self.logger.write(payload)

    @abstractmethod
    async def run(self, stream_url):
        ...

    async def _maybe_leave_and_return(self):
        if random.random() < self.profile.leave_return_probability:
            pause = random.randint(30, 300)
            self._log("leave", duration_sec=pause)
            await asyncio.sleep(pause)
            self._log("return")
            return True
        return False
'''

# ══════════════════════════════════════════════════════════════════
# 6. behaviors/lurker.py — обновлённый (с _tab_blur через visibility)
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/behaviors/lurker.py"] = '''\
import asyncio
import random
from behaviors.base import BaseAgent
from humanizer.mouse import human_move
from humanizer.timing import lognormal_seconds


class LurkerAgent(BaseAgent):
    async def run(self, stream_url):
        self._log("navigate", url=stream_url)
        await self.page.goto(stream_url, wait_until="domcontentloaded")
        await self.install_visibility()

        elapsed = 0
        target = self.profile.watch_time_target_sec

        while elapsed < target:
            if random.random() < 0.4:
                x = random.randint(200, self.profile.viewport["width"] - 200)
                y = random.randint(100, self.profile.viewport["height"] - 100)
                try:
                    await human_move(self.page, x, y)
                    self.state.mouse_events += 1
                except Exception:
                    pass

            if random.random() < 0.08:
                await self._tab_blur()

            pause = min(lognormal_seconds(median_sec=20), target - elapsed)
            await asyncio.sleep(pause)
            elapsed += pause

            if await self._maybe_leave_and_return():
                elapsed += 30

        self._log("session_end", total_watch_sec=int(elapsed),
                  mouse_events=self.state.mouse_events,
                  tab_blur_events=self.state.tab_blur_events)

    async def _tab_blur(self):
        try:
            mode = random.choices(
                ["tab_switch", "minimize", "freeze"],
                weights=[0.7, 0.2, 0.1],
            )[0]
            duration = random.uniform(2, 30)
            if mode == "tab_switch":
                await self.visibility.tab_switch(duration)
            elif mode == "minimize":
                await self.visibility.minimize_window(duration)
            else:
                await self.visibility.freeze_and_resume(duration)
            self.state.tab_blur_events += 1
        except Exception as e:
            self._log("tab_blur_error", error=str(e))
'''

# ══════════════════════════════════════════════════════════════════
# 7. workers/task_runner.py — с UA-CH sync
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


async def run_agent(factory, profile, stream_url, logger, semaphore):
    async with semaphore:
        context = await factory.create_context(profile)
        try:
            page = await context.new_page()
            # UA-CH синхронизация ДО первой навигации
            try:
                await sync_uach_for_context(context, page, profile)
            except Exception as e:
                logger.write({"agent_id": profile.agent_id,
                              "event": "uach_error", "error": str(e)})

            AgentClass = AGENT_MAP[profile.archetype]
            agent = AgentClass(profile, page, logger)
            await agent.run(stream_url)
        except Exception as e:
            logger.write({"agent_id": profile.agent_id,
                          "event": "error", "error": str(e)})
        finally:
            await context.close()
'''

# ══════════════════════════════════════════════════════════════════
# 8. run_lab_advanced.py — лаунчер с проверкой
# ══════════════════════════════════════════════════════════════════

FILES["twitch-redteam/run_lab_advanced.py"] = '''\
"""
Продвинутый локальный запуск: visibility + UA-CH + humanizer.
Каждый агент логирует финальное состояние visibility и CDP.
"""
import asyncio
import random
from core.browser_factory import BrowserFactory
from core.scheduler import generate_profile
from behaviors.lurker import LurkerAgent
from behaviors.chatter import ChatterAgent
from behaviors.scanner import ScannerAgent
from behaviors.multi_tab import MultiTabAgent
from telemetry.event_logger import EventLogger


AGENT_MAP = {
    "lurker": LurkerAgent,
    "chatter": ChatterAgent,
    "scanner": ScannerAgent,
    "multi_tab": MultiTabAgent,
}


async def run_one(factory, profile, stream_url, logger, semaphore):
    async with semaphore:
        context = await factory.create_context(profile)
        try:
            page = await context.new_page()
            try:
                from humanizer.ua_ch_sync import sync_uach_for_context
                await sync_uach_for_context(context, page, profile)
            except Exception as e:
                logger.write({"agent_id": profile.agent_id,
                              "event": "uach_error", "error": str(e)})

            AgentClass = AGENT_MAP[profile.archetype]
            agent = AgentClass(profile, page, logger)
            await agent.run(stream_url)

            stats = agent.visibility.stats()
            logger.write({"agent_id": profile.agent_id,
                          "event": "final_stats", **stats})
        finally:
            await context.close()


async def main():
    STREAM_URL = "https://www.twitch.tv/YOUR_TEST_CHANNEL"
    N_AGENTS = 10

    archetypes = ["lurker"] * 5 + ["chatter"] * 2 + ["scanner"] * 2 + ["multi_tab"]
    random.shuffle(archetypes)

    factory = BrowserFactory(headless=True)
    await factory.start()
    logger = EventLogger("logs/run_lab_advanced.jsonl")

    proxies = [{"url": "", "country": "US"}]
    profiles = [
        generate_profile(f"agent_{i}", archetypes[i], proxies)
        for i in range(N_AGENTS)
    ]
    for p in profiles:
        p.watch_time_target_sec = 90

    semaphore = asyncio.Semaphore(5)
    try:
        tasks = [run_one(factory, p, STREAM_URL, logger, semaphore)
                 for p in profiles]
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await factory.close()
        logger.close()


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
    print("  # Отредактируйте run_lab_advanced.py: YOUR_TEST_CHANNEL")
    print("  python run_lab_advanced.py")
    print()
    print("Проверка логов:")
    print("  tail -f logs/run_lab_advanced.jsonl")