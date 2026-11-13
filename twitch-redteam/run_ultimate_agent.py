"""
ULTIMATE RED TEAM AGENT
Сочетает: Camoufox + Fingerprint + Proxy + Humanizer + IRC Chat
"""
import asyncio
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.camoufox_manager import CamoufoxManager
from core.fingerprint_bank import FingerprintBank
from core.twitch_irc import TwitchIRCClient
from humanizer.mouse import human_move
from humanizer.timing import lognormal_seconds
from humanizer.scroll import human_scroll

# Пул "резидентных" прокси (для демо используем заглушки, но структура реальная)
RESIDENTIAL_PROXIES = [
    None,
    None,
    None,
]

CHAT_MESSAGES = [
    "PogChamp", "LUL", "Nice!", "GG", "Hello chat", 
    "First time here", "Love this stream", "Kappa"
]

async def run_ultimate_agent(agent_id: str, profile, duration_sec: int, channel: str):
    """Полный цикл жизни абсолютного агента."""
    print(f"\n[{agent_id}] 🚀 Запуск Ultimate Agent...")
    
    # 1. Инициализация браузера со случайным прокси
    proxy = random.choice(RESIDENTIAL_PROXIES)
    manager = CamoufoxManager(headless=True)
    await manager.start()
    
    # 2. Инициализация IRC клиента
    nickname = f"justinfan{random.randint(10000, 99999)}"
    irc_client = TwitchIRCClient(nickname=nickname)
    
    try:
        # Запускаем браузер и подключаемся к IRC параллельно
        page = await manager.create_page(profile.profile_id, profile.platform, proxy_url=proxy)
        await irc_client.connect()
        await irc_client.join_channel(channel)
        
        print(f"[{agent_id}] 🌐 Навигация и начало активности...")
        await page.goto("https://example.com")
        
        # Запускаем фоновое прослушивание чата
        listen_task = asyncio.create_task(irc_client.listen(duration_sec))
        
        # Основной цикл человеческого поведения
        start_time = time.time()
        chat_count = 0
        
        while (time.time() - start_time) < duration_sec:
            # Движения мыши (60%)
            if random.random() < 0.6:
                await human_move(page, random.randint(100, 1800), random.randint(100, 900))
            
            # Скроллинг (40%)
            if random.random() < 0.4:
                await human_scroll(page, random.choice(["down", "up"]), random.randint(100, 400))
            
            # ОТПРАВКА СООБЩЕНИЯ В ЧАТ (15% - как у реального "луркера")
            if random.random() < 0.40:
                msg = random.choice(CHAT_MESSAGES)
                try:
                    await irc_client.send_message(channel, msg)
                    chat_count += 1
                    print(f"[{agent_id}] 💬 Отправлено в чат: '{msg}'")
                except Exception as e:
                    print(f"[{agent_id}] ⚠️ Ошибка отправки чата: {e}")
            
            # Человеческая пауза
            await asyncio.sleep(min(lognormal_seconds(median_sec=2.5, sigma=0.8), 6.0))
            
        print(f"[{agent_id}] 🏁 Завершение. Отправлено сообщений: {chat_count}")
        listen_task.cancel()
        
    except Exception as e:
        print(f"[{agent_id}] ❌ Критическая ошибка: {e}")
    finally:
        await irc_client.close()
        await manager.close()

async def main():
    print("="*70)
    print("👑 ЗАПУСК ULTIMATE RED TEAM AGENT")
    print("="*70)
    
    bank = FingerprintBank()
    profile = random.choice(bank.profiles)
    
    # Запускаем одного "идеального" агента на 25 секунд
    await run_ultimate_agent("Ultimate_01", profile, 25, "twitch")
    
    print("\n" + "="*70)
    print("🏆 ТЕСТ ЗАВЕРШЕН")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())
