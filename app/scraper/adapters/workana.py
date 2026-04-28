import random
import os
from datetime import datetime
from playwright.async_api import async_playwright
from loguru import logger
from ..base import ScraperPort

class WorkanaScraperAdapter(ScraperPort):
    def __init__(self):
            self.user_data_dir = "./browser_data"
            self.login_url = "https://www.workana.com/login"
            self.state_file = "state.json"
            self.jobs_url = "https://www.workana.com/jobs?language=es&skills=angular%2Cjavascript%2Cnode-js%2Cpostgressql%2Cpython%2Creact-native%2Cvue-js"

    """Adaptador para pruebas sin riesgo"""
    async def get_projects(self) -> list:
        logger.info("🕸️ Iniciando scraping en Workana...")
        projects = []
        
        async with async_playwright() as p:
            # Lanzamos el navegador persistente (mantiene login)
            context = await p.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            
            page = await context.new_page()
            
            try:
                # 1. Navegar a la lista de proyectos
                await page.goto(self.jobs_url, wait_until="networkidle")
                
                # 2. Seleccionar los contenedores de proyectos
                # Nota: Los selectores de Workana pueden cambiar, estos son los estándar
                job_elements = await page.query_selector_all(".project-item")
                
                for el in job_elements[:10]: # Limitamos a los 10 más recientes
                    title_el = await el.query_selector(".project-title")
                    budget_el = await el.query_selector(".values")
                    link_el = await el.query_selector(".project-title a")
                    
                    if title_el and link_el:
                        title = (await title_el.inner_text()).strip()
                        budget = (await budget_el.inner_text()).strip() if budget_el else "N/A"
                        link = "https://www.workana.com" + await link_el.get_attribute("href")
                        
                        projects.append({
                            "title": title,
                            "budget": budget,
                            "link": link,
                            "extracted_at": datetime.utcnow()
                        })
                
                logger.success(f"📊 {len(projects)} proyectos extraídos de Workana.")
                
            except Exception as e:
                logger.error(f"❌ Error durante el scraping: {e}")
            finally:
                await context.close()
                
        return projects

    async def login(self) -> bool:
        """Intenta loguearse y devuelve True si tuvo éxito"""
        email = os.getenv("WORKANA_EMAIL")
        password = os.getenv("WORKANA_PASS")
        
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=True, # En Docker siempre True
                args=["--no-sandbox"]
            )
            page = context.pages[0]
            
            try:
                await page.goto(self.login_url)
                # Si ya estamos logueados (vemos el avatar), saltamos
                if await page.query_selector(".user-avatar"):
                    logger.info("✅ Ya existe una sesión activa.")
                    return True

                await page.fill('input[name="email"]', email)
                await page.fill('input[name="password"]', password)
                await page.click('button[type="submit"]')
                
                await page.wait_for_timeout(5000) # Esperamos que cargue el dashboard
                
                if await page.query_selector(".user-avatar"):
                    logger.success("🔑 Login exitoso en Workana")
                    return True
                
                return False
            finally:
                await context.close()