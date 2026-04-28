import asyncio
from playwright_stealth import Stealth
from playwright.async_api import async_playwright
from loguru import logger

async def capture_forced():
    async with Stealth().use_async(async_playwright()) as p:
        user_data_dir = "./user_data_clean"
        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = context.pages[0]
        
        # Definimos una función interna para guardar el estado en cada navegación
        async def save_state():
            await context.storage_state(path="state.json")
            logger.success(f"💾 Estado guardado! URL actual: {page.url}")

        # Cada vez que la página termine de cargar algo, guardamos
        page.on("load", lambda _: asyncio.create_task(save_state()))

        try:
            logger.info("🌐 Abriendo Workana...")
            await page.goto("https://www.workana.com/login")
            
            logger.warning("👉 LOGUÉATE AHORA.")
            logger.info("El script guardará el 'state.json' automáticamente cuando entres.")
            logger.info("Presiona Ctrl+C en esta terminal SOLO cuando ya estés en tu Dashboard.")

            # Mantenemos el script vivo por 10 minutos o hasta que lo cierres
            await asyncio.sleep(600) 

        except KeyboardInterrupt:
            logger.info("Terminado por el usuario.")
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            await save_state() # Un último guardado antes de salir
            await context.close()

if __name__ == "__main__":
    asyncio.run(capture_forced())