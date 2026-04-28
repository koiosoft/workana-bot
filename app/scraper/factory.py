
import os
from pathlib import Path
from .adapters import DummyScraperAdapter,WorkanaScraperAdapter
from dotenv import load_dotenv
from loguru import logger
from .base import ScraperPort

class ScraperFactory:
    _instance = None

    @staticmethod
    def get_scraper() -> ScraperPort:
        if ScraperFactory._instance is None:

            load_dotenv() 

            # 2. Leemos la variable (que ya debe estar en el ambiente gracias al compose)
            source = os.getenv("SCRAPER_SOURCE", "dummy").lower()
            logger.info(f"🔍 SCRAPER_SOURCE detectado desde ambiente: '{source}'")

            if source == "workana":
                ScraperFactory._instance = WorkanaScraperAdapter()
            else:
                ScraperFactory._instance =  DummyScraperAdapter()
        
        return ScraperFactory._instance