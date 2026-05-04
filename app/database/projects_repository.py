import hashlib
from datetime import datetime, timezone
from typing import Any
from pymongo import ASCENDING, UpdateOne
from .mongo import get_database
from loguru import logger

class ProjectsRepository:
    def __init__(self):
        self._indexes_ready = False

    @property
    def collection(self):
        """Obtiene la colección de forma dinámica asegurando que la DB ya inició."""
        return get_database()["projects"]

    async def ensure_indexes(self):
        if self._indexes_ready:
            return
        await self.collection.create_index([("link_hash", ASCENDING)], unique=True)
        await self.collection.create_index([("proposal_status", ASCENDING)])
        await self.collection.create_index([("scraped_at", ASCENDING)])
        await self.collection.create_index([("processing_started_at", ASCENDING)])
        self._indexes_ready = True

    @staticmethod
    def _build_hash(project: dict[str, Any]) -> str:
        raw = project.get("link") or f"{project.get('title', '')}|{project.get('budget', '')}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def save_scraped_projects(self, projects: list[dict[str, Any]]) -> dict[str, int]:
        await self.ensure_indexes()
        if not projects:
            return {"inserted": 0, "existing": 0}

        now = datetime.now(timezone.utc).isoformat()
        operations = []
        for project in projects:
            link_hash = self._build_hash(project)
            doc = {
                "title": project.get("title", "N/A"),
                "budget": project.get("budget", "N/A"),
                "link": project.get("link", "N/A"),
                "published": project.get("published", "N/A"),
                "short_description": project.get("short_description", ""),
                "bids": project.get("bids", "0"),
                "source": "workana",
                "proposal_status": "pending",
                "scraped_at": now,
                "link_hash": link_hash,
                "skills": project.get("skills", []),
            }
            operations.append(
                UpdateOne(
                    {"link_hash": link_hash},
                    {
                        "$setOnInsert": doc,
                        "$set": {"updated_at": now},
                    },
                    upsert=True,
                )
            )

        result = await self.collection.bulk_write(operations, ordered=False)
        inserted = int(result.upserted_count or 0)
        existing = len(projects) - inserted
        return {"inserted": inserted, "existing": existing}

    async def get_pending_projects(self, limit: int = 20) -> list[dict[str, Any]]:
        await self.ensure_indexes()
        cursor = self.collection.find(
            {"proposal_status": "pending"},
            {"_id": 0, "title": 1, "budget": 1, "link": 1, "published": 1, "link_hash": 1},
        ).sort("scraped_at", ASCENDING).limit(limit)
        return await cursor.to_list(length=limit)

    async def claim_pending_projects(self, limit: int = 20) -> list[dict[str, Any]]:
        await self.ensure_indexes()
        
        # 1. Obtenemos primero los IDs que vamos a bloquear
        # Solo traemos el campo _id y link_hash para que sea ultra rápido
        cursor = self.collection.find(
            {"proposal_status": "pending"},
            {"link_hash": 1}
        ).limit(limit)
        
        pending_items = await cursor.to_list(length=limit)
        if not pending_items:
            return []

        link_hashes = [p["link_hash"] for p in pending_items if p.get("link_hash")]
        now = datetime.now(timezone.utc).isoformat()

        # 2. INTENTO ATÓMICO DE BLOQUEO
        # Usamos update_many con el filtro de "pending" para asegurar que 
        # si otro proceso nos ganó de mano, no "re-bloqueamos" nada.
        result = await self.collection.update_many(
            {
                "link_hash": {"$in": link_hashes}, 
                "proposal_status": "pending" # <-- CRÍTICO: Doble verificación
            },
            {
                "$set": {
                    "proposal_status": "processing", 
                    "processing_started_at": now, 
                    "updated_at": now
                }
            },
        )

        # Si no logramos marcar ninguno (modified_count == 0), significa que otro proceso los tomó
        if result.modified_count == 0:
            return []

        # 3. RECUPERACIÓN FINAL
        # Solo traemos los que ESTE proceso logró marcar con éxito
        cursor = self.collection.find(
            {
                "link_hash": {"$in": link_hashes}, 
                "proposal_status": "processing",
                "processing_started_at": now # Filtramos por nuestra marca de tiempo
            },
            {
                "_id": 0, "title": 1, "budget": 1, "link": 1, 
                "published": 1, "short_description": 1, "link_hash": 1, "bids": 1
            },
        ).sort("scraped_at", ASCENDING)
        
        return await cursor.to_list(length=limit)

    async def mark_projects_status(self, link_hashes: list[str], status: str) -> int:
        await self.ensure_indexes()
        if not link_hashes:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        result = await self.collection.update_many(
            {"link_hash": {"$in": link_hashes}},
            {"$set": {"proposal_status": status, "updated_at": now}},
        )
        return int(result.modified_count or 0)

    async def update_project_analysis(self, link_hash: str, score: int, reason: str, status: str = "analyzed") -> bool:
        """
        Actualiza un proyecto con los resultados del análisis de la IA.
        """
        await self.ensure_indexes()
        now = datetime.now(timezone.utc).isoformat()
        
        result = await self.collection.update_one(
            {"link_hash": link_hash},
            {
                "$set": {
                    "ai_score": score,
                    "ai_reason": reason,
                    "proposal_status": status,
                    "updated_at": now,
                    "analyzed_at": now
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"✅ Proyecto {link_hash} actualizado con score {score}.")
            return True
        
        logger.warning(f"⚠️ No se pudo actualizar el análisis para el hash: {link_hash}")
        return False