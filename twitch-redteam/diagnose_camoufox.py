import asyncio
from camoufox.async_api import AsyncCamoufox

async def main():
    print("🔍 Диагностика API Camoufox...")
    
    manager = AsyncCamoufox(
        headless=True,
        canvas_noise=False,
        i_know_what_im_doing=True
    )
    
    browser = await manager.__aenter__()
    
    # 1. Выводим все публичные методы браузера
    print("\n📋 Доступные методы браузера:")
    methods = [m for m in dir(browser) if not m.startswith('_')]
    for m in sorted(methods):
        print(f"  - {m}")
    
    # 2. Пробуем создать страницу без config
    print("\n🧪 Тест 1: new_context() без параметров")
    try:
        context = await browser.new_context()
        print(f"  ✅ Контекст создан: {context}")
        page = await context.new_page()
        print(f"  ✅ Страница создана: {page}")
        await page.goto("https://example.com")
        print(f"  ✅ Страница загружена: {await page.title()}")
        await page.close()
        await context.close()
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
    
    # 3. Пробуем new_page() без параметров
    print("\n🧪 Тест 2: new_page() без параметров")
    try:
        page = await browser.new_page()
        print(f"  ✅ Страница создана: {page}")
        await page.goto("https://example.com")
        print(f"  ✅ Страница загружена: {await page.title()}")
        await page.close()
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
    
    # 4. Проверяем сигнатуру методов
    print("\n📖 Сигнатуры методов:")
    import inspect
    if hasattr(browser, 'new_context'):
        sig = inspect.signature(browser.new_context)
        print(f"  new_context{sig}")
    if hasattr(browser, 'new_page'):
        sig = inspect.signature(browser.new_page)
        print(f"  new_page{sig}")
    
    await browser.close()
    await manager.__aexit__(None, None, None)
    print("\n✅ Диагностика завершена")

if __name__ == "__main__":
    asyncio.run(main())
