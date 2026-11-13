import asyncio
import random
from behaviors.base import BaseAgent
from humanizer.timing import lognormal_seconds

class ScannerAgent(BaseAgent):
    async def run(self, stream_url):
        channels = [stream_url]
        for ch in channels:
            short_watch = random.randint(10, 30)
            self._log("navigate", url=ch, planned_sec=short_watch)
            try:
                await self.page.goto(ch, wait_until="domcontentloaded")
                await self.install_visibility()
            except Exception as e:
                self._log("navigation_error", error=str(e))
                continue
            await asyncio.sleep(max(0, short_watch - 10))
        self._log("session_end", total_watch_sec=self.state.total_watch_sec)
