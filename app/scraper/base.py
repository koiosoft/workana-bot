from abc import ABC, abstractmethod
from typing import List, Dict

class ScraperPort(ABC):
    """
    Puerto: Define la interfaz que cualquier scraper debe cumplir.
    """
    @abstractmethod
    async def get_projects(self) -> List[Dict]:
        pass

    @abstractmethod
    async def fetch_full_detail(self, url: str) -> dict:
        pass

