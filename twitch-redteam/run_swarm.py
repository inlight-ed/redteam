"""
Масштабирование: Запуск роя (swarm) продвинутых агентов.
Каждый агент работает в изолированном контексте со своим уникальным fingerprint.
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

async def run_irc_session(agent_id: str, channel: str, duration_sec: int):
    """Фоновая задача: подключение и прослушивание IRC чата."""
    # Уникальный ник для каждого агента, чтобы избежать конфликтов на Twitch
    nickname = f"justinfan{random.randint(10000, 99999)}"
    print(f"[{agent_id}] 📡 Подключение к каналу #{channel} как {nickname}...")
    
    client = TwitchIRCClient(nickname=nickname)
    try:
        await client.connect()
        await client.join_channel(channel)
        print(f"[{agent_id}] ⏳ Слушаем чат {duration_sec} секунд...")
        await client.listen(duration_sec)
    except Exception as e:
        print(f"[{agent_id}] ❌ [IRC] Ошибка: {e}")
    finally:
        await client.close()

async def simulate_human_behavior(agent_id: str, page, duration_sec: int):
    """Эмуляция человеческого поведения для конкретного агента."""
    start_time = time.time()
    
    while (time.time() - start_time) < duration_sec:
        # 1. Движение мыши (60% вероятность)
        if random.random() < 0.6:
            x = random.randint(100, 1800)
            y = random.randint(100, 900)
            try:
                await human_move(page, x, y)
            except Exception:
                pass
        
        # 2. Скроллинг (40% вероятность)
        if random.random() < 0.4:
            direction = random.choices(["down", "up"], weights=[0.8, 0.2])[0]
            distance = random.randint(100, 400)
            try:
                await human_scroll(page, direction, distance)
            except Exception:
                pass
        
        # 3. Пауза между действиями (логнормальное распределение)
        pause = lognormal_seconds(median_sec=2.0, sigma=0.7)
        await asyncio.sleep(min(pause, 5.0))

async def run_browser_session(agent_id: str, profile, duration_sec: int):
    """Основная задача: запуск Camoufox с fingerprint и человеческим поведением."""
    print(f"[{agent_id}] 🦊 Инициализация Camoufox ({profile.platform})...")
    manager = CamoufoxManager(headless=True)
    await manager.start()
    
    try:
        page = await manager.create_page(profile.profile_id, profile.platform)
        
        print(f"[{agent_id}] 🌐 Переход на example.com...")
        await page.goto("https://example.com")
        
        # Быстрая проверка применения fingerprint
        plat = await page.evaluate("() => navigator.platform")
        print(f"[{agent_id}] 📊 Fingerprint применен: Platform={plat}")
        
        # Запускаем эмуляцию человеческого поведения
        await simulate_human_behavior(agent_id, page, duration_sec)
        
        await page.close()
    except Exception as e:
        print(f"[{agent_id}] ❌ [Browser] Ошибка: {e}")
    finally:
        await manager.close()

async def run_single_advanced_agent(agent_id: str, profile, duration_sec: int, channel: str):
    """Запускает полный цикл одного агента (Браузер + IRC параллельно)."""
    try:
        await asyncio.gather(
            run_browser_session(agent_id, profile, duration_sec),
            run_irc_session(agent_id, channel, duration_sec)
        )
        print(f"[{agent_id}] 🏁 Агент завершил работу успешно")
    except Exception as e:
        print(f"[{agent_id}] ⚠️ Критическая ошибка агента: {e}")

async def main():
    print("="*70)
    print("🚀 ЗАПУСК РОЯ АГЕНТОВ (SWARM MODE)")
    print("="*70)
    
    NUM_AGENTS = 5  # Количество параллельных агентов
    DURATION = 20   # Время работы каждого агента в секундах
    CHANNEL = "twitch"
    
    # 1. Получаем банк профилей
    bank = FingerprintBank()
    if len(bank.profiles) < NUM_AGENTS:
        print(f"⚠️ В банке только {len(bank.profiles)} профилей, ограничиваем количество агентов.")
        NUM_AGENTS = len(bank.profiles)
    
    # Выбираем случайные уникальные профили для каждого агента
    selected_profiles = random.sample(bank.profiles, NUM_AGENTS)
    
    # 2. Создаем задачи для всех агентов
    tasks = []
    for i in range(NUM_AGENTS):
        agent_id = f"Agent_{i+1:02d}"
        profile = selected_profiles[i]
        print(f"📋 {agent_id} получит профиль: {profile.profile_id} ({profile.platform})")
        
        task = run_single_advanced_agent(agent_id, profile, DURATION, CHANNEL)
        tasks.append(task)
    
    print(f"\n⚡ Запуск {NUM_AGENTS} агентов параллельно на {DURATION} секунд...\n")
    
    # 3. Запускаем всех одновременно
    start_time = time.time()
    await asyncio.gather(*tasks)
    elapsed = time.time() - start_time
    
    print("\n" + "="*70)
    print(f"🏁 ВСЕ АГЕНТЫ ЗАВЕРШИЛИ РАБОТУ (Общее время: {elapsed:.1f} сек)")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())
