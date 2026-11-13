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
                  mouse_events=self.state.mouse_events, tab_blur_events=self.state.tab_blur_events)

    async def _tab_blur(self):
        try:
            mode = random.choices(["tab_switch", "minimize", "freeze"], weights=[0.7, 0.2, 0.1])[0]
            duration = random.uniform(2, 30)
            if mode == "tab_switch":
                await self.visibility.tab_switch(duration)
            self.state.tab_blur_events += 1
        except Exception as e:
            self._log("tab_blur_error", error=str(e))
