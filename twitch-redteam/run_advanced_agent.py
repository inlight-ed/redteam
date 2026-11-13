"""
Финальный интеграционный тест: Camoufox + Fingerprint + IRC + Humanizer
Запускает агента с реалистичным поведением: движения мыши, скроллинг, паузы.
"""
import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.camoufox_manager import CamoufoxManager
from core.fingerprint_bank import FingerprintBank
from core.twitch_irc import TwitchIRCClient
from humanizer.mouse import human_move
from humanizer.timing import lognormal_seconds
from humanizer.scroll import human_scroll, random_scroll_session

async def run_irc_session(channel: str, duration_sec: int):
    """Фоновая задача: подключение и прослушивание IRC чата."""
    print(f"\n📡 [IRC] Подключение к каналу #{channel}...")
    client = TwitchIRCClient(nickname="justinfan12345")
    try:
        await client.connect()
        await client.join_channel(channel)
        print(f"⏳ [IRC] Слушаем чат {duration_sec} секунд...")
        await client.listen(duration_sec)
    except Exception as e:
        print(f"❌ [IRC] Ошибка: {e}")
    finally:
        await client.close()

async def simulate_human_behavior(page, duration_sec: int):
    """
    Эмуляция человеческого поведения: движения мыши, клики, скроллинг.
    """
    import time
    start_time = time.time()
    
    print(f"🎭 [Humanizer] Начинаем эмуляцию поведения на {duration_sec} секунд...")
    
    while (time.time() - start_time) < duration_sec:
        # 1. Случайное движение мыши
        if random.random() < 0.6:  # 60% вероятность
            x = random.randint(100, 1800)
            y = random.randint(100, 900)
            try:
                await human_move(page, x, y)
                print(f"  🖱️  Движение мыши к ({x}, {y})")
            except Exception as e:
                print(f"  ⚠️  Ошибка движения мыши: {e}")
        
        # 2. Случайный клик (реже)
        if random.random() < 0.2:  # 20% вероятность
            x = random.randint(200, 1700)
            y = random.randint(200, 800)
            try:
                await human_move(page, x, y)
                await page.mouse.click(x, y)
                print(f"  👆 Клик в ({x}, {y})")
            except Exception as e:
                print(f"  ⚠️  Ошибка клика: {e}")
        
        # 3. Скроллинг (40% вероятность)
        if random.random() < 0.4:
            direction = random.choices(["down", "up"], weights=[0.8, 0.2])[0]
            distance = random.randint(100, 400)
            try:
                await human_scroll(page, direction, distance)
                print(f"  📜 Скроллинг {direction} на {distance}px")
            except Exception as e:
                print(f"  ⚠️  Ошибка скроллинга: {e}")
        
        # 4. Пауза между действиями (как у реального пользователя)
        pause = lognormal_seconds(median_sec=2.0, sigma=0.7)
        await asyncio.sleep(min(pause, 8.0))  # Максимум 8 секунд
    
    print(f"✅ [Humanizer] Сессия поведения завершена")

async def run_browser_session(profile_id: str, platform: str, duration_sec: int):
    """Основная задача: запуск Camoufox с fingerprint и человеческим поведением."""
    print(f"\n🦊 [Browser] Инициализация Camoufox для профиля {profile_id} ({platform})...")
    manager = CamoufoxManager(headless=True)
    await manager.start()
    
    try:
        page = await manager.create_page(profile_id, platform)
        
        print("🌐 [Browser] Переход на example.com...")
        await page.goto("https://example.com")
        title = await page.title()
        print(f"✅ [Browser] Страница загружена: {title}")
        
        # Проверка применения fingerprint
        ua = await page.evaluate("() => navigator.userAgent")
        plat = await page.evaluate("() => navigator.platform")
        print(f"📊 [Browser] Fingerprint применен:")
        print(f"   UA: {ua[:50]}...")
        print(f"   Platform: {plat}")
        
        # Запускаем эмуляцию человеческого поведения
        await simulate_human_behavior(page, duration_sec)
        
        await page.close()
    except Exception as e:
        print(f"❌ [Browser] Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await manager.close()

async def main():
    print("="*70)
    print("🚀 ЗАПУСК ПРОДВИНУТОГО АГЕНТА (Camoufox + IRC + Humanizer)")
    print("="*70)
    
    DURATION = 30  # Увеличиваем до 30 секунд для демонстрации поведения
    CHANNEL = "twitch"
    
    # 1. Получаем детерминированный fingerprint
    bank = FingerprintBank()
    if not bank.profiles:
        print("❌ Банк профилей пуст!")
        return
    
    profile = random.choice(bank.profiles)
    print(f"🎲 Выбран профиль: {profile.profile_id}")
    
    # 2. Запускаем браузер и IRC параллельно
    try:
        await asyncio.gather(
            run_browser_session(profile.profile_id, profile.platform, DURATION),
            run_irc_session(CHANNEL, DURATION)
        )
    except Exception as e:
        print(f"⚠️ Критическая ошибка в главном цикле: {e}")
    
    print("\n" + "="*70)
    print("🏁 АГЕНТ ЗАВЕРШИЛ РАБОТУ УСПЕШНО")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(main())
