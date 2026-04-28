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
