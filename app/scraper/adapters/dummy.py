import random
import os
from datetime import datetime
from loguru import logger
from ..base import ScraperPort

class DummyScraperAdapter(ScraperPort):
    """Adaptador para pruebas sin riesgo"""
    async def get_projects(self) -> list:
        logger.warning("🧪 [DUMMY] Generando datos de prueba...")
        return [{
            "internal_id": f"test_{random.randint(100, 999)}",
            "title": "Proyecto de prueba Hexagonal",
            "description": "Validando arquitectura de puertos y adaptadores.",
            "budget": "100 - 500 USD",
            "link": "https://test.com",
            "extracted_at": datetime.utcnow()
        }]

    async def fetch_full_detail(self, url: str) -> dict:
        logger.warning(f"🧪 [DUMMY] Simulando obtención de detalles para la URL: {url}")
        return {
            "skills": ["Python", "FastAPI", "Docker"],
            "proposals": "5 a 10",
            "published_at": "hace 1 hora",
            "country": "México"
        }
