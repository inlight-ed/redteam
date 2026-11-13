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
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
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
                Object.defineProperty(navigator, 'platform', {{ get: () => {profile.platform!r} }});
                Object.defineProperty(navigator, 'languages', {{ get: () => [{profile.locale!r}, 'en'] }});
                Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
            }} catch (e) {{}}
            window.__mouseX = 0;
            window.__mouseY = 0;
        }})();
        """

    async def close(self):
        if self._browser: await self._browser.close()
        if self._playwright: await self._playwright.stop()
