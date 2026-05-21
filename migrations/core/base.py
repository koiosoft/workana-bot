from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable, Dict, Any
from pymongo.database import Database

@runtime_checkable
class IMigrationContext(Protocol):
    """
    Interfaz del Gestor de Contexto (ResilientBulkWriter).
    Define las operaciones de loteo que un script de migración puede encolar.
    """

    def add_insert(self, collection_name: str, document: Dict[str, Any]) -> None:
        """
        Encola un documento para ser insertado en una colección específica.
        """
        ...

    def add_update(self, collection_name: str, filter_query: Dict[str, Any], update_query: Dict[str, Any]) -> None:
        """
        Encola una operación de actualización para una colección específica.
        """
        ...

    def add_delete(self, collection_name: str, filter_query: Dict[str, Any]) -> None:
        """
        Encola una operación de eliminación para una colección específica.
        """
        ...


class MigrationBase(ABC):
    """
    Interfaz Abstracta de Migración.
    
    Todo script de migración debe heredar de esta clase e implementar
    los métodos `up` y `down`.
    """

    @abstractmethod
    def up(self, writer: IMigrationContext) -> None:
        """
        Ejecuta la lógica de la migración para "subir" de versión.
        Debe usarse exclusivamente para encolar mutaciones de datos a
        través del `writer`.

        Args:
            writer (IMigrationContext): Proxy para encolar operaciones de escritura.
        """
        pass

    @abstractmethod
    def down(self, db: Database) -> None:
        """
        Ejecuta la lógica para revertir la migración.
        Su alcance se limita a operaciones DDL de infraestructura que escapan
        al rastreo automático (ej. eliminar colecciones, descartar índices).

        Args:
            db (Database): Instancia de la base de datos.
        """
        pass
