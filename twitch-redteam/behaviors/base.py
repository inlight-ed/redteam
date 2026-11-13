from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import asyncio
import random
from humanizer.visibility import VisibilityCascade

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
        self.visibility = VisibilityCascade(page, verbose=verbose_visibility)

    async def install_visibility(self):
        await self.visibility.install()

    def _log(self, event, **kwargs):
        payload = {"ts": datetime.utcnow().isoformat(), "agent_id": self.profile.agent_id, "event": event, **kwargs}
        self.state.event_log.append(payload)
        if self.logger:
            self.logger.write(payload)

    @abstractmethod
    async def run(self, stream_url): ...

    async def _maybe_leave_and_return(self):
        if random.random() < self.profile.leave_return_probability:
            pause = random.randint(30, 300)
            self._log("leave", duration_sec=pause)
            await asyncio.sleep(pause)
            self._log("return")
            return True
        return False
