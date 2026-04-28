import asyncio
from playwright_stealth import Stealth
from playwright.async_api import async_playwright
from loguru import logger

async def test_bot_session():
    # Usamos la sintaxis de Stealth que ya sabemos que funciona
    async with Stealth().use_async(async_playwright()) as p:
        logger.info("🚀 Lanzando bot con la sesión guardada...")
        
        # IMPORTANTE: Ya no usamos launch_persistent_context
        # Usamos un navegador normal (puedes poner headless=True si quieres)
        browser = await p.chromium.launch(headless=True) 
        
        # CREAMOS EL CONTEXTO USANDO EL ARCHIVO state.json
        context = await browser.new_context(
            storage_state="state.json",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        try:
            logger.info("🌐 Yendo directo al Dashboard...")
            await page.goto("https://www.workana.com/dashboard")
            
            # Esperamos un poco para que cargue el contenido dinámico
            await page.wait_for_timeout(5000)
            
            # Verificamos si estamos dentro buscando cualquier rastro de tu sesión
            content = await page.content()
            
            if "Roger" in content or "Zavala" in content:
                logger.success("🎯 ¡ÉXITO TOTAL! El bot es reconocido como Roger Zavala.")
            else:
                logger.warning("⚠️ No encontré el nombre en el texto, tomando screenshot para verificar...")
            
            await page.screenshot(path="bot_check.png")
            logger.info("📸 Screenshot guardado como 'bot_check.png' para tu revisión.")

        except Exception as e:
            logger.error(f"❌ Error en la prueba: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_bot_session())