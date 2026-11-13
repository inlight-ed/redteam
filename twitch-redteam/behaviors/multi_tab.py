import asyncio
import random
from behaviors.lurker import LurkerAgent

class MultiTabAgent(LurkerAgent):
    async def run(self, stream_url):
        second = await self.page.context.new_page()
        await second.goto("about:blank")
        self._log("second_tab_opened")
        target = self.profile.watch_time_target_sec
        remaining = target
        while remaining > 0:
            chunk = min(random.randint(10, 30), remaining)
            await asyncio.sleep(chunk)
            remaining -= chunk
            await second.bring_to_front()
            await asyncio.sleep(random.uniform(2, 5))
            await self.page.bring_to_front()
            self.state.tab_blur_events += 1
        await second.close()
        self._log("session_end", total_watch_sec=target)
