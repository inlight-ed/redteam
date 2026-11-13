from __future__ import annotations
import asyncio
import random
from contextlib import asynccontextmanager
from typing import Literal
from playwright.async_api import Page

_INIT_SCRIPT = r"""
(() => {
    if (window.__visibility_cascade) return;
    let state = { hidden: false, visibilityState: 'visible', focused: true, reason: 'initial', lastChangeTs: performance.now() };
    const nativeRaf = window.requestAnimationFrame;
    const nativeCancelRaf = window.cancelAnimationFrame;
    const suspendedRaf = new Map();
    let rafIdCounter = 1;

    try {
        Object.defineProperty(document, 'hidden', { configurable: false, enumerable: true, get() { return state.hidden; } });
        Object.defineProperty(document, 'visibilityState', { configurable: false, enumerable: true, get() { return state.visibilityState; } });
    } catch (e) {}
    Document.prototype.hasFocus = function() { return state.focused; };

    window.requestAnimationFrame = function(cb) {
        const id = rafIdCounter++;
        if (state.hidden) { suspendedRaf.set(id, cb); return id; }
        return nativeRaf.call(window, cb);
    };
    window.cancelAnimationFrame = function(id) {
        if (suspendedRaf.has(id)) { suspendedRaf.delete(id); return; }
        return nativeCancelRaf.call(window, id);
    };

    window.__visibility_cascade = {
        getState() { return { ...state }; },
        hide(reason) {
            if (state.hidden) return { ...state };
            state.hidden = true; state.visibilityState = 'hidden'; state.focused = false; state.reason = reason || 'hide'; state.lastChangeTs = performance.now();
            document.dispatchEvent(new Event('visibilitychange'));
            window.dispatchEvent(new Event('blur'));
            return { ...state };
        },
        show(reason) {
            if (!state.hidden) return { ...state };
            state.hidden = false; state.visibilityState = 'visible'; state.focused = true; state.reason = reason || 'show'; state.lastChangeTs = performance.now();
            window.dispatchEvent(new Event('focus'));
            document.dispatchEvent(new Event('visibilitychange'));
            const pending = Array.from(suspendedRaf.entries());
            suspendedRaf.clear();
            nativeRaf.call(window, () => { for (const [id, cb] of pending) { try { cb(performance.now()); } catch (_) {} } });
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
        installed = await self.page.evaluate("() => !!window.__visibility_cascade")
        if not installed:
            await self.page.add_init_script(_INIT_SCRIPT)
            await self.page.evaluate(_INIT_SCRIPT)

    async def get_state(self) -> dict:
        return await self.page.evaluate("() => window.__visibility_cascade.getState()")

    async def hide(self, reason: Reason = "tab_switch") -> dict:
        async with self._lock:
            if self._is_hidden: return await self.get_state()
            new_state = await self.page.evaluate("(r) => window.__visibility_cascade.hide(r)", reason)
            self._is_hidden = True
            if self.verbose: print(f"[visibility] hide({reason})")
            return new_state

    async def show(self, reason: Reason = "tab_switch") -> dict:
        async with self._lock:
            if not self._is_hidden: return await self.get_state()
            new_state = await self.page.evaluate("(r) => window.__visibility_cascade.show(r)", reason)
            self._is_hidden = False
            if self.verbose: print(f"[visibility] show({reason})")
            return new_state

    async def tab_switch(self, duration_sec: float) -> None:
        await self.hide("tab_switch")
        await asyncio.sleep(duration_sec)
        await self.show("tab_switch")
