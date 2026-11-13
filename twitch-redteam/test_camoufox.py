import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core.camoufox_manager import CamoufoxManager

async def main():
    print("🦊 Тест Camoufox (Async API)...")
    manager = CamoufoxManager(headless=True)
    await manager.start()
    try:
        page = await manager.create_page("test_agent_1", "Win32")
        await page.goto("https://example.com")
        print(f"✅ Страница загружена: {await page.title()}")
        
        ua = await page.evaluate("() => navigator.userAgent")
        platform = await page.evaluate("() => navigator.platform")
        print(f"📊 User-Agent: {ua[:60]}...")
        print(f"📊 Platform: {platform}")
        
        await page.close()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await manager.close()

if __name__ == "__main__":
    asyncio.run(main())
