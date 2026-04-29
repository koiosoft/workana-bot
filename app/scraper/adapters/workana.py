import re
import os
from datetime import datetime
from urllib.parse import urljoin
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from loguru import logger
from ..base import ScraperPort

class WorkanaScraperAdapter(ScraperPort):
    def __init__(self):
            self.state_file = "./state.json"
            self.browser_profile = {
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
            self.pub_filter = os.getenv("WORKANA_PUBLICATION_FILTER", "1d")
            self.max_pages = int(os.getenv("WORKANA_MAX_PAGES", "30"))
            self.visit_project_pages = os.getenv("WORKANA_VISIT_PROJECT_PAGES", "false").lower() == "true"
            self.max_detail_visits = int(os.getenv("WORKANA_MAX_DETAIL_VISITS", "20"))
            self.jobs_url = (
            f"https://www.workana.com/jobs?category=it-programming"
            f"&language=es"
            f"&publication={self.pub_filter}"
            f"&skills=angular%2Cnode-js%2Cpostgressql%2Cpython%2Creact-js%2Creact-native%2Cvue-js"
            f"&subcategory=web-development"
        )

    @staticmethod
    def _normalize_project_link(href: str | None) -> str:
        if not href:
            return "N/A"
        return urljoin("https://www.workana.com", href)

    async def _is_logged_in(self, page) -> bool:
        return await page.query_selector(".user-avatar") is not None
            
    async def auto_scroll(self, page):
        """Hace scroll hacia abajo para disparar la carga de elementos lazy"""
        logger.info("🖱️ Realizando scroll para cargar todos los proyectos...")
        for _ in range(5): # Scroll 5 veces para asegurar
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500) # Esperar a que carguen los nuevos items
            
    async def get_projects(self) -> list:
        logger.info(f"🕸️ Iniciando scraping exhaustivo (Filtro: {self.pub_filter})...")
        all_projects = []
        max_projects_first_page = None
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context_kwargs = {}
            if os.path.exists(self.state_file) and os.path.getsize(self.state_file) > 0:
                context_kwargs["storage_state"] = self.state_file
                logger.info(f"🔐 Cargando sesión desde {self.state_file}...")
            else:
                logger.warning(f"⚠️ No existe una sesión válida en {self.state_file}.")

            context_kwargs.update(self.browser_profile)
            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()
            
            try:
                # Recorremos páginas de forma dinámica con un tope de seguridad.
                current_page = 1
                while current_page <= self.max_pages:
                    url = f"{self.jobs_url}&page={current_page}"
                    logger.info(f"🔍 Navegando a página {current_page}...")
                    logger.info(f"🔍 URL=  {url}")

                    try:
                        await page.goto(url, wait_until="networkidle", timeout=60000)
                    except PlaywrightTimeoutError:
                        logger.error(f"⏱️ Timeout navegando página {current_page}. Se cierra el flujo.")
                        break

                    if current_page == 1:
                        is_logged_in = await self._is_logged_in(page)
                        logger.info(f"🔎 Sesión activa detectada: {is_logged_in}")

                    # 📸 TOMAR FOTO DE CONTROL
                    screenshot_path = "debug_screenshot.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    logger.info(f"📸 Foto de control guardada en: {screenshot_path}")

                    # OPCIONAL: Ver el contenido del HTML en el log para ver si hay 10 o 19
                    content = await page.content()
                    items_count = content.count('class="project-item')
                    logger.info(f"🔍 Conteo de 'project-item' en el HTML crudo: {items_count}")

                    await self.auto_scroll(page)
                    
                    # Esperar a que el contenedor de proyectos esté presente
                    try:
                        await page.wait_for_selector(".project-item", timeout=15000)
                    except PlaywrightTimeoutError:
                        logger.error(f"⏱️ Timeout esperando proyectos en página {current_page}. Se cierra el flujo.")
                        break
                    job_elements = await page.query_selector_all(".project-item")
                    
                    if not job_elements:
                        logger.info(f"🏁 No se encontraron más proyectos en la página {current_page}.")
                        break

                    page_projects_count = len(job_elements)
                    page_projects: list[dict] = []
                    stop_after_current_page = False
                    if current_page == 1:
                        max_projects_first_page = page_projects_count
                        logger.info(f"📌 Referencia de paginación: {max_projects_first_page} proyectos en página 1.")
                    elif max_projects_first_page and page_projects_count < max_projects_first_page:
                        stop_after_current_page = True
                        logger.info(
                            "🏁 Página con menos proyectos que la primera "
                            f"({page_projects_count} < {max_projects_first_page}). "
                            "No se consultarán más páginas."
                        )

                    for el in job_elements:
                        # 1. Título y Link
                        title_el = await el.query_selector(".project-title")
                        link_el = await el.query_selector(".project-title a")
                        
                        # 2. Detalles (Fecha y Bids)
                        details_el = await el.query_selector(".project-main-details")
                        details_text = await details_el.inner_text() if details_el else ""
                        
                        # 3. Presupuesto
                        budget_el = await el.query_selector(".values")
                        
                        if title_el and link_el:
                            title = (await title_el.inner_text()).strip()
                            href = await link_el.get_attribute("href")
                            link = self._normalize_project_link(href)
                            budget = (await budget_el.inner_text()).strip() if budget_el else "N/A"
                            
                            # Regex para limpiar la fecha y las propuestas
                            date_match = re.search(r'Publicado:\s*(.*?)(?=\s*Propuestas:|$)', details_text)
                            bids_match = re.search(r'Propuestas:\s*(\d+)', details_text)
                            
                            project = {
                                "title": title,
                                "budget": budget,
                                "link": link,
                                "published": date_match.group(1).strip() if date_match else "N/A",
                                "bids": bids_match.group(1) if bids_match else "0",
                                "extracted_at": datetime.utcnow().isoformat()
                            }
                            all_projects.append(project)
                            page_projects.append(project)

                    if self.visit_project_pages:
                        links_to_visit = [
                            project["link"] for project in page_projects if project.get("link") and project["link"] != "N/A"
                        ]
                        if links_to_visit:
                            detail_page = await context.new_page()
                            try:
                                visits_limit = min(len(links_to_visit), self.max_detail_visits)
                                logger.info(
                                    f"🔎 Visitando detalles de proyectos ({visits_limit}/{len(links_to_visit)}) "
                                    f"en página {current_page}..."
                                )
                                for link in links_to_visit[:visits_limit]:
                                    try:
                                        await detail_page.goto(link, wait_until="domcontentloaded", timeout=30000)
                                        await detail_page.wait_for_timeout(700)
                                        logger.info(f"✅ Se abrió detalle de proyecto: {link}")
                                    except PlaywrightTimeoutError:
                                        logger.warning(f"⏱️ Timeout al abrir detalle: {link}")
                            finally:
                                await detail_page.close()

                    if stop_after_current_page:
                        break

                    current_page += 1

                if current_page > self.max_pages:
                    logger.warning(
                        f"⚠️ Se alcanzó el tope de seguridad WORKANA_MAX_PAGES={self.max_pages}."
                    )

                # Guardamos una "foto" de la sesión en el JSON por si acaso
                await context.storage_state(path=self.state_file)
                logger.success(f"📊 Extracción completa: {len(all_projects)} proyectos totales.")
                
            except Exception as e:
                logger.error(f"❌ Error durante el scraping: {e}")
            finally:
                await context.close()
                await browser.close()
                
        return all_projects
