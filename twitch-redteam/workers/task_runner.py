import asyncio
from behaviors.lurker import LurkerAgent
from behaviors.chatter import ChatterAgent
from behaviors.scanner import ScannerAgent
from behaviors.multi_tab import MultiTabAgent

AGENT_MAP = {
    "lurker": LurkerAgent, "chatter": ChatterAgent,
    "scanner": ScannerAgent, "multi_tab": MultiTabAgent, "mobile_user": LurkerAgent,
}

async def run_agent(factory, profile, stream_url, logger, semaphore):
    async with semaphore:
        context = await factory.create_context(profile)
        try:
            page = await context.new_page()
            AgentClass = AGENT_MAP[profile.archetype]
            agent = AgentClass(profile, page, logger)
            await agent.run(stream_url)
        except Exception as e:
            logger.write({"agent_id": profile.agent_id, "event": "error", "error": str(e)})
        finally:
            await context.close()
