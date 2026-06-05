# extract_session.py
import asyncio
import os
from playwright.async_api import async_playwright
from loguru import logger

async def capture_forced():
    browser_profile = {
        "user_agent": os.getenv(
            "WORKANA_USER_AGENT",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        ),
        "locale": os.getenv("WORKANA_LOCALE", "es-ES"),
        "timezone_id": os.getenv("WORKANA_TIMEZONE", "America/Santo_Domingo"),
        "extra_http_headers": {
            "Accept-Language": os.getenv("WORKANA_ACCEPT_LANGUAGE", "es-ES,es;q=0.9,en;q=0.8")
        },
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, # Necesitamos ver la pantalla para loguearnos
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(**browser_profile)
        page = await context.new_page()
        state_file = "../state.json"
        session_saved = False
        
        try:
            logger.info("🌐 Abriendo Workana para login manual...")
            await page.goto("https://www.workana.com/login")
            
            logger.warning("👉 LOGUÉATE MANUALMENTE.")
            logger.info("Cuando veas tu dashboard, la sesión se guardará en state.json y el script terminará solo.")
            logger.info("Evita Ctrl+C para no interrumpir el guardado.")

            # Esperamos hasta que el usuario cierre el navegador.
            while True:
                await asyncio.sleep(1)
                if page.is_closed():
                    logger.warning("⚠️ Navegador cerrado antes de confirmar avatar; guardando estado final...")
                    break

                # Algunas navegaciones destruyen el contexto JS temporalmente.
                try:
                    avatar = await page.query_selector(".user-avatar")
                    user_menu = await page.query_selector(
                        ".dropdown-user-menu, [data-testid='user-menu'], .user-menu"
                    )
                    current_url = page.url or ""
                    is_login_url = "/login" in current_url
                    is_authenticated_url = any(
                        path in current_url
                        for path in ["/dashboard", "/projects", "/jobs", "/messages"]
                    )
                except Exception:
                    continue

                # Guardar solo cuando hay evidencia real de sesión autenticada.
                is_authenticated = bool(avatar or user_menu or (is_authenticated_url and not is_login_url))
                if is_authenticated and not session_saved:
                    await page.wait_for_timeout(1500)
                    await context.storage_state(path=state_file)
                    session_saved = True
                    logger.success("✅ Sesión detectada y guardada en state.json.")
                    break

        except asyncio.CancelledError:
            logger.warning("⚠️ Ejecución interrumpida antes de finalizar.")
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            try:
                await context.storage_state(path=state_file)
                logger.info("💾 Estado final de sesión exportado a state.json.")
                session_saved = True
            except Exception as e:
                logger.warning(f"No se pudo exportar el estado final: {e}")

            try:
                await context.close()
            except Exception:
                pass
            try:
                await browser.close()
            except Exception:
                pass
            if session_saved:
                logger.info("📂 Archivo state.json listo para usar dentro de Docker.")
            else:
                logger.error("❌ No se pudo guardar state.json en esta ejecución.")

if __name__ == "__main__":
    try:
        asyncio.run(capture_forced())
    except KeyboardInterrupt:
        logger.warning("⛔ Proceso cancelado por teclado.")