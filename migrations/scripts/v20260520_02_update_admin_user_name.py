from bson import ObjectId
from pymongo.database import Database

from migrations.core.base import IMigrationContext, MigrationBase

TARGET_COLLECTION = "users"
USER_ROGER_ID = ObjectId("6a0c91a3ac86bbd7a3507040")
ORIGINAL_NAME = "Roger Zavala"
UPDATED_NAME = "Roger Zavala (Admin)"

class Migration(MigrationBase):
    """
    Actualiza el nombre del usuario administrador en la colección 'users'.
    """

    def up(self, writer: IMigrationContext) -> None:
        """
        Encola una operación de actualización para el nombre del usuario.
        """
        writer.add_update(
            collection_name=TARGET_COLLECTION,
            filter_query={"_id": USER_ROGER_ID},
            update_query={"$set": {"name": UPDATED_NAME}}
        )

    def down(self, db: Database) -> None:
        """
        Revierte el cambio de nombre al valor original.
        La reversión de datos del writer automático también funcionaría,
        pero esto es más explícito para cambios de infraestructura o lógicos.
        """
        db[TARGET_COLLECTION].update_one(
            {"_id": USER_ROGER_ID},
            {"$set": {"name": ORIGINAL_NAME}}
        )
