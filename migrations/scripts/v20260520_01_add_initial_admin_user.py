from datetime import datetime
from bson import ObjectId
from pymongo.database import Database

from migrations.core.base import MigrationBase
from migrations.core.writer import ResilientBulkWriter

TARGET_COLLECTION = "users"

USER_ROGER = {
    "_id": ObjectId("6a0c91a3ac86bbd7a3507040"),
    "email": "rogerzavala@gmail.com",
    "passwordHash": "$2b$12$cVsLB5BC5Wp10fRKdWn8weYlZNXgcdHV55jBZjKuSw1KkYQO5IiIy",
    "name": "Roger Zavala",
    "role": "admin",
    "createdAt": datetime(2026, 5, 19, 16, 36, 51, 158000),
    "updatedAt": datetime(2026, 5, 19, 20, 7, 42, 722000)
}

class Migration(MigrationBase):
    """
    Asegura que el usuario administrador inicial exista en la colección 'users'.
    Utiliza una operación de 'upsert' para ser idempotente.
    """

    def up(self, writer: ResilientBulkWriter) -> None:
        """
        Inserta o actualiza (upsert) el usuario administrador.
        Si el usuario con esa _id ya existe, se sobreescribirá.
        Si no existe, se insertará.
        """
        writer.add_update_one(
            collection_name=TARGET_COLLECTION,
            query_filter={"_id": USER_ROGER["_id"]},
            update_mutation={"$set": USER_ROGER},
            upsert=True
        )

    def down(self, db: Database) -> None:
        """
        Revierte la migración eliminando únicamente al usuario administrador.
        Esto es más seguro que eliminar la colección completa.
        """
        db[TARGET_COLLECTION].delete_one({"_id": USER_ROGER["_id"]})