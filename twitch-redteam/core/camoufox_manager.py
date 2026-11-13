import hashlib
from camoufox.async_api import AsyncCamoufox

class CamoufoxManager:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._manager = None
        self._browser = None
    
    async def start(self):
        """Запуск Camoufox."""
        self._manager = AsyncCamoufox(
            headless=self.headless,
            canvas_noise=False,
            i_know_what_im_doing=True
        )
        self._browser = await self._manager.__aenter__()
        print("✅ Camoufox инициализирован (async)")
        return self._browser
    
    def build_fingerprint_config(self, profile_id: str, platform: str = "Win32") -> dict:
        """Строит конфигурацию fingerprint."""
        seed = hashlib.sha256(profile_id.encode()).hexdigest()
        webgl_vendor = "NVIDIA Corporation" if platform == "Win32" else "Intel Inc."
        webgl_renderer = "NVIDIA GeForce RTX 3060" if platform == "Win32" else "Intel Iris Pro"
        return {
            "user_agent": self._get_ua(platform, seed),
            "platform": platform,
            "hardware_concurrency": 8,
            "device_memory": 8,
            "webgl_vendor": webgl_vendor,
            "webgl_renderer": webgl_renderer,
            "canvas_seed": int(seed[:8], 16) % 10000,
            "audio_seed": int(seed[8:16], 16) % 10000,
            "fonts_seed": int(seed[16:24], 16) % 10000,
        }
    
    def _get_ua(self, platform: str, seed: str) -> str:
        """Генерирует User-Agent."""
        chrome_version = 120 + (int(seed[:2], 16) % 20)
        if platform == "Win32":
            return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36"
        elif platform == "MacIntel":
            return f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36"
        else:
            return f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version}.0.0.0 Safari/537.36"
    
    def _build_init_script(self, config: dict) -> str:
        """Создает JavaScript для переопределения fingerprint."""
        return f"""
        (() => {{
            // Переопределяем platform
            Object.defineProperty(navigator, 'platform', {{
                get: () => '{config['platform']}',
                configurable: true
            }});
            
            // Переопределяем hardwareConcurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {{
                get: () => {config['hardware_concurrency']},
                configurable: true
            }});
            
            // Переопределяем deviceMemory
            Object.defineProperty(navigator, 'deviceMemory', {{
                get: () => {config['device_memory']},
                configurable: true
            }});
            
            // Переопределяем WebGL
            const origGetParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(param) {{
                if (param === 37445) return '{config['webgl_vendor']}';
                if (param === 37446) return '{config['webgl_renderer']}';
                return origGetParameter.call(this, param);
            }};
            
            if (window.WebGL2RenderingContext) {{
                const origGetParameter2 = WebGL2RenderingContext.prototype.getParameter;
                WebGL2RenderingContext.prototype.getParameter = function(param) {{
                    if (param === 37445) return '{config['webgl_vendor']}';
                    if (param === 37446) return '{config['webgl_renderer']}';
                    return origGetParameter2.call(this, param);
                }};
            }}
        }})();
        """
    
    async def create_page(self, profile_id: str, platform: str = "Win32"):
        """Создаёт контекст и страницу с fingerprint."""
        if not self._browser:
            raise RuntimeError("Camoufox не инициализирован.")
        
        config = self.build_fingerprint_config(profile_id, platform)
        
        # Создаем контекст с базовыми параметрами
        context = await self._browser.new_context(
            user_agent=config['user_agent'],
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1920, "height": 1080}
        )
        
        # Внедряем JavaScript для специфичных настроек fingerprint
        init_script = self._build_init_script(config)
        await context.add_init_script(init_script)
        
        # Создаем страницу
        page = await context.new_page()
        return page
    
    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._manager:
            await self._manager.__aexit__(None, None, None)
        print("✅ Camoufox закрыт")
