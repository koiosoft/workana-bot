from .factory import ScraperFactory

# Exportamos la instancia lista para usar (Singleton Pattern)
scraper_service = ScraperFactory.get_scraper()