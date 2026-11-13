import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.browser_factory import BrowserFactory
from core.scheduler import generate_profile
from behaviors.lurker import LurkerAgent
from behaviors.chatter import ChatterAgent
from behaviors.scanner import ScannerAgent
from telemetry.event_logger import EventLogger

AGENT_CLASSES = {
    "lurker": LurkerAgent,
    "chatter": ChatterAgent,
    "scanner": ScannerAgent,
}

async def run_single_agent(agent_id: str, archetype: str, factory, logger, stream_url: str):
    proxies = [{"url": "", "country": "US"}]
    profile = generate_profile(agent_id, archetype, proxies)
    profile.watch_time_target_sec = 15 
    
    context = await factory.create_context(profile)
    try:
        page = await context.new_page()
        AgentClass = AGENT_CLASSES.get(archetype, LurkerAgent)
        agent = AgentClass(profile, page, logger)
        print(f"  ▶️  Запуск: {agent_id} (архетип: {archetype})")
        await agent.run(stream_url)
        print(f"  ✅ Завершен: {agent_id}")
    except Exception as e:
        print(f"  ❌ Ошибка в {agent_id}: {e}")
        logger.write({"agent_id": agent_id, "event": "fatal_error", "error": str(e)})
    finally:
        await context.close()

async def main():
    STREAM_URL = "https://example.com"
    NUM_AGENTS = 3
    ARCHETYPES = ["lurker", "chatter", "scanner"]
    
    print(f"🚀 Инициализация браузера для {NUM_AGENTS} агентов...")
    factory = BrowserFactory(headless=True)
    await factory.start()
    
    Path("logs").mkdir(exist_ok=True)
    logger = EventLogger("logs/multi_test_run.jsonl")
    
    tasks = []
    for i in range(NUM_AGENTS):
        agent_id = f"multi_agent_{i+1}"
        archetype = ARCHETYPES[i % len(ARCHETYPES)]
        task = run_single_agent(agent_id, archetype, factory, logger, STREAM_URL)
        tasks.append(task)
    
    print(f"⚡ Запуск {NUM_AGENTS} агентов параллельно...\n")
    await asyncio.gather(*tasks)
    
    print("\n🏁 Все агенты завершили работу.")
    await factory.close()
    logger.close()
    print("📊 Логи сохранены в: logs/multi_test_run.jsonl")

if __name__ == "__main__":
    asyncio.run(main())

