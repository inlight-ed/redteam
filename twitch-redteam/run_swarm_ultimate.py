"""
SWARM ULTIMATE: Масштабирование Абсолютных Агентов
Запускает 5+ агентов параллельно, каждый со своим профилем, прокси и IRC-сессией.
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

# Пул прокси (в демо-режиме используем None, чтобы избежать ошибок DNS)
# В продакшене здесь будут реальные URL: "http://user:pass@proxy.com:port"
RESIDENTIAL_PROXIES = [None, None, None, None, None]

CHAT_MESSAGES = [
    "PogChamp", "LUL", "Nice!", "GG", "Hello chat", 
    "First time here", "Love this stream", "Kappa", "W TWITCH CON"
]

async def run_single_ultimate_agent(agent_id: str, profile, duration_sec: int, channel: str):
    """Полный цикл жизни одного агента в рое."""
    print(f"[{agent_id}] 🚀 Запуск...")
    
    # 1. Выбираем случайный прокси для этого агента
    proxy = random.choice(RESIDENTIAL_PROXIES)
    
    # 2. Инициализация браузера
    manager = CamoufoxManager(headless=True)
    await manager.start()
    
    # 3. Инициализация IRC клиента с уникальным ником
    nickname = f"justinfan{random.randint(10000, 99999)}"
    irc_client = TwitchIRCClient(nickname=nickname)
    
    try:
        # Создаем страницу с fingerprint и прокси
        page = await manager.create_page(profile.profile_id, profile.platform, proxy_url=proxy)
        
        # Подключаемся к IRC
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
            
            # ОТПРАВКА СООБЩЕНИЯ В ЧАТ (30% вероятность за цикл)
            if random.random() < 0.30:
                msg = random.choice(CHAT_MESSAGES)
                try:
                    await irc_client.send_message(channel, msg)
                    chat_count += 1
                    print(f"[{agent_id}] 💬 Чат: '{msg}'")
                except Exception as e:
                    print(f"[{agent_id}] ⚠️ Ошибка чата: {e}")
            
            # Человеческая пауза (1.5 - 4.0 секунды)
            pause = min(lognormal_seconds(median_sec=2.0, sigma=0.6), 4.0)
            await asyncio.sleep(pause)
            
        print(f"[{agent_id}] 🏁 Завершение. Сообщений: {chat_count}")
        listen_task.cancel()
        
    except Exception as e:
        print(f"[{agent_id}] ❌ Критическая ошибка: {e}")
    finally:
        await irc_client.close()
        await manager.close()

async def main():
    print("="*70)
    print("🐝 ЗАПУСК РОЯ ULTIMATE АГЕНТОВ (SWARM v2)")
    print("="*70)
    
    NUM_AGENTS = 5
    DURATION = 35  # 35 секунд для демонстрации параллельной работы
    CHANNEL = "twitch"
    
    # 1. Получаем банк профилей
    bank = FingerprintBank()
    if len(bank.profiles) < NUM_AGENTS:
        print(f"⚠️ В банке только {len(bank.profiles)} профилей. Ограничиваем рой.")
        NUM_AGENTS = len(bank.profiles)
    
    # Выбираем случайные уникальные профили
    selected_profiles = random.sample(bank.profiles, NUM_AGENTS)
    
    # 2. Создаем задачи для всех агентов
    tasks = []
    for i in range(NUM_AGENTS):
        agent_id = f"Agent_{i+1:02d}"
        profile = selected_profiles[i]
        print(f"📋 {agent_id} получит: {profile.profile_id} ({profile.platform})")
        task = run_single_ultimate_agent(agent_id, profile, DURATION, CHANNEL)
        tasks.append(task)
    
    print(f"\n⚡ Запуск {NUM_AGENTS} агентов параллельно на {DURATION} секунд...\n")
    
    # 3. Запускаем всех одновременно
    start_time = time.time()
    await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start_time
    
    print("\n" + "="*70)
    print(f"🏁 ВСЕ АГЕНТЫ ЗАВЕРШИЛИ РАБОТУ (Общее время: {elapsed:.1f} сек)")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())
