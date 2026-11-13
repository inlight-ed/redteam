import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.browser_factory import BrowserFactory
from core.scheduler import generate_profile
from behaviors.lurker import LurkerAgent
from telemetry.event_logger import EventLogger

async def main():
    # Путь к тестовой странице
    STREAM_URL = f"file://{Path(__file__).parent / 'test_page.html'}"
    
    print(f"🚀 Запуск тестового агента...")
    print(f"📄 URL: {STREAM_URL}")
    
    # Создаем простой профиль
    proxies = [{"url": "", "country": "US"}]
    profile = generate_profile("test_agent_1", "lurker", proxies)
    profile.watch_time_target_sec = 10  # Всего 10 секунд для теста
    
    # Создаем браузер (headless=False чтобы видеть окно)
    factory = BrowserFactory(headless=True)
    await factory.start()
    
    # Создаем логгер
    Path("logs").mkdir(exist_ok=True)
    logger = EventLogger("logs/test_run.jsonl")
    
    try:
        context = await factory.create_context(profile)
        page = await context.new_page()
        
        agent = LurkerAgent(profile, page, logger)
        await agent.run(STREAM_URL)
        
        print("✅ Тест завершен успешно!")
        print(f"📊 Логи сохранены в: logs/test_run.jsonl")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await factory.close()
        logger.close()

if __name__ == "__main__":
    asyncio.run(main())
