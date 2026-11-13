import asyncio
import random
from behaviors.lurker import LurkerAgent
from humanizer.timing import poisson_events

CHAT_TEMPLATES = ["lol", "nice play", "gg", "pog", "let's go"]

class ChatterAgent(LurkerAgent):
    async def run(self, stream_url):
        self._log("navigate", url=stream_url)
        await self.page.goto(stream_url, wait_until="domcontentloaded")
        await self.install_visibility()
        
        target = self.profile.watch_time_target_sec
        chat_times = poisson_events(self.profile.chat_probability_per_min, target / 60.0)
        
        elapsed = 0
        for t in chat_times:
            wait = t - elapsed
            if wait > 0:
                await asyncio.sleep(wait)
            elapsed = t
            await self._send_chat()
        
        remaining = target - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
            
        self._log("session_end", total_watch_sec=int(target), chat_sent=self.state.chat_sent)

    async def _send_chat(self):
        try:
            # На тестовой странице просто логируем
            text = random.choice(CHAT_TEMPLATES)
            self.state.chat_sent += 1
            self._log("chat_sent", text=text)
        except Exception as e:
            self._log("chat_error", error=str(e))