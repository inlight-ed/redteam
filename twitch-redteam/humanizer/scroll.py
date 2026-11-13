"""
Эмуляция скроллинга страницы с человеческими паттернами.
"""
import asyncio
import random
from humanizer.timing import lognormal_seconds

async def human_scroll(page, direction: str = "down", distance: int = None):
    """
    Эмулирует скроллинг страницы с случайными паузами.
    
    Args:
        page: Playwright/Camoufox page объект
        direction: "down" или "up"
        distance: Расстояние в пикселях (если None, случайное)
    """
    if distance is None:
        distance = random.randint(100, 500)
    
    step = 50 if direction == "down" else -50
    total_scrolled = 0
    
    while abs(total_scrolled) < distance:
        # Скроллим на небольшой шаг
        await page.mouse.wheel(0, step)
        total_scrolled += step
        
        # Случайная пауза между шагами (как у реального пользователя)
        pause = lognormal_seconds(median_sec=0.3, sigma=0.5)
        await asyncio.sleep(min(pause, 2.0))  # Ограничиваем максимум 2 секундами
    
    # Финальная пауза после скроллинга
    await asyncio.sleep(lognormal_seconds(median_sec=1.0, sigma=0.4))

async def random_scroll_session(page, duration_sec: int):
    """
    Сессия случайного скроллинга в течение заданного времени.
    Имитирует поведение пользователя, который читает страницу.
    """
    import time
    start_time = time.time()
    
    while (time.time() - start_time) < duration_sec:
        # Случайное направление (чаще вниз)
        direction = random.choices(["down", "up"], weights=[0.8, 0.2])[0]
        distance = random.randint(100, 400)
        
        await human_scroll(page, direction, distance)
        
        # Пауза между сессиями скроллинга (чтение контента)
        pause = lognormal_seconds(median_sec=3.0, sigma=0.6)
        await asyncio.sleep(min(pause, 10.0))
