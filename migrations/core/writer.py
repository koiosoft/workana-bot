"""
Módulo para la escritura resiliente de operaciones de base de datos en migraciones.
"""
import logging
from collections import defaultdict
from typing import Dict, List, Any

from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
from pymongo.operations import DeleteMany, InsertOne, UpdateMany, UpdateOne


BACKUP_COLLECTION = "migration_backup"

class ResilientBulkWriter:
    """
    Gestor de contexto para operaciones de escritura masiva resilientes y
    multi-colección. Implementa una estrategia de Write-Ahead Logging (WAL)
    para garantizar la atomicidad y la capacidad de rollback de las migraciones.

    Actúa como un proxy sobre pymongo, interceptando operaciones de escritura
    (insert, update, delete) y ejecutándolas en un proceso de dos fases al
    finalizar un bloque de contexto `with`.

    Fase 1: (Respaldo Global) Escribe un registro de todas las operaciones
             pendientes en una colección de respaldo (`migration_backup`).
             Esto incluye el estado original de los documentos para
             actualizaciones y eliminaciones.

    Fase 2: (Ejecución de Negocio) Aplica las operaciones de negocio reales
             a sus colecciones de destino correspondientes.

    Si ocurre una excepción dentro del bloque `with`, ninguna operación se
    ejecuta, garantizando que no haya cambios parciales en la base de datos.
    """

    def __init__(self, script_version: str, client: MongoClient, db_name: str):
        """
        Inicializa el gestor de escritura.

        Args:
            script_version (str): El identificador de la versión del script de
                                  migración.
            client (MongoClient): El cliente de pymongo conectado a la base de
                                  datos.
            db_name (str): El nombre de la base de datos de negocio.
        """
        if not script_version or not isinstance(script_version, str):
            raise ValueError("script_version debe ser un string no vacío.")
        if not isinstance(client, MongoClient):
            raise TypeError("client debe ser una instancia de pymongo.MongoClient.")
        if not db_name or not isinstance(db_name, str):
            raise ValueError("db_name debe ser un string no vacío.")

        self.script_version = script_version
        self.db = client[db_name]
        self.backup_collection_name = "migration_backup"

        # Cola para operaciones de negocio, indexada por nombre de colección
        self._business_ops: Dict[str, List[Any]] = defaultdict(list)
        # Cola única y global para las operaciones de respaldo
        self._backup_ops: List[InsertOne] = []

        logging.info(f"ResilientBulkWriter inicializado para el script '{self.script_version}'.")

    def __enter__(self):
        """Habilita el entorno seguro del gestor de contexto."""
        logging.debug(f"Entrando en el bloque de contexto para '{self.script_version}'.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Cierra el bloque de contexto y ejecuta la persistencia en dos fases.
        Si se produjo una excepción, aborta todas las operaciones.
        """
        if exc_type is not None:
            logging.error(
                f"Excepción detectada en el bloque de migración '{self.script_version}': {exc_val}. "
                "Abortando todas las operaciones de base de datos."
            )
            self._cleanup()
            # Propaga la excepción para que el orquestador la maneje
            return False

        try:
            self._commit()
        except BulkWriteError as e:
            logging.critical(
                "Error de escritura masiva durante el commit para el script "
                f"'{self.script_version}': {e.details}"
            )
            # Propaga para que el orquestador active el protocolo de reversión
            raise
        except Exception as e:
            logging.critical(
                "Error inesperado durante el commit para el script "
                f"'{self.script_version}': {e}"
            )
            raise
        finally:
            self._cleanup()

        # Indica que cualquier excepción interna (si la hubiera) fue manejada
        return True

    def _cleanup(self):
        """Limpia las colas de operaciones en memoria."""
        self._business_ops.clear()
        self._backup_ops.clear()
        logging.debug("Colas de operaciones del ResilientBulkWriter limpiadas.")

    def _commit(self):
        """
        Ejecuta la persistencia atómica en dos fases.
        """
        # Si no hay operaciones, no hacer nada.
        if not self._backup_ops and not any(self._business_ops.values()):
            logging.info("No hay operaciones de escritura pendientes. Commit finalizado.")
            return

        # --- Fase 1: Persistencia Atómica del Respaldo (WAL) ---
        if self._backup_ops:
            logging.info(
                f"Fase 1: Iniciando escritura de {len(self._backup_ops)} "
                f"operaciones de respaldo en '{self.backup_collection_name}'."
            )
            backup_collection = self.db[self.backup_collection_name]
            backup_collection.bulk_write(self._backup_ops, ordered=True)
            logging.info("Fase 1: Respaldo global completado con éxito.")
        else:
            logging.info("Fase 1: No hay operaciones de respaldo para escribir.")

        # --- Fase 2: Persistencia Atómica de Negocio ---
        if any(self._business_ops.values()):
            logging.info("Fase 2: Iniciando aplicación de operaciones de negocio.")
            for collection_name, ops in self._business_ops.items():
                if ops:
                    logging.info(
                        f"Aplicando {len(ops)} operaciones en la colección '{collection_name}'."
                    )
                    collection = self.db[collection_name]
                    collection.bulk_write(ops, ordered=True)
            logging.info("Fase 2: Operaciones de negocio aplicadas con éxito.")
        else:
            logging.info("Fase 2: No hay operaciones de negocio para aplicar.")

    def add_insert(self, collection_name: str, document: Dict[str, Any]):
        """
        Encola una operación de inserción.

        Args:
            collection_name (str): La colección de destino.
            document (Dict): El documento a insertar.
        """
        if "_id" not in document:
            document["_id"] = ObjectId()

        # Acción de Negocio
        self._business_ops[collection_name].append(InsertOne(document))

        # Acción de Respaldo
        backup_doc = {
            "migration_version": self.script_version,
            "collection": collection_name,
            "op_type": "insert",
            "op_details": {"_id": document["_id"]},
            "original_document": None,
        }
        self._backup_ops.append(InsertOne(backup_doc))
        logging.debug(f"Encolada operación INSERT para el documento ID {document['_id']} en '{collection_name}'.")

    def add_update_one(self, collection_name: str, query_filter: Dict[str, Any], update_mutation: Dict[str, Any], upsert: bool = False):
        """
        Encola una operación de actualización de un único documento.

        Args:
            collection_name (str): La colección de destino.
            query_filter (Dict): El filtro para encontrar el documento a actualizar.
            update_mutation (Dict): La operación de actualización de pymongo.
            upsert (bool): Si es True, realiza una operación de 'upsert'.
        """
        # Acción de Respaldo Preventiva
        target_collection = self.db[collection_name]
        doc_to_update = target_collection.find_one(query_filter)

        if doc_to_update:
            # Backup para una operación de UPDATE
            backup_doc = {
                "migration_version": self.script_version,
                "collection": collection_name,
                "op_type": "update",
                "op_details": {"filter": query_filter, "mutation": update_mutation},
                "original_document": doc_to_update,
            }
            self._backup_ops.append(InsertOne(backup_doc))
        elif upsert:
            # Backup para una operación de INSERT (resultado de un upsert)
            # El rollback de esto es un delete, por eso el op_type es 'insert'.
            upserted_id = query_filter.get("_id")
            if "$set" in update_mutation and "_id" in update_mutation["$set"]:
                upserted_id = update_mutation["$set"]["_id"]

            if not upserted_id:
                 raise ValueError("Upsert con add_update_one requiere un _id predecible en el query_filter o en la mutación $set para garantizar el rollback.")

            backup_doc = {
                "migration_version": self.script_version,
                "collection": collection_name,
                "op_type": "insert",
                "op_details": {"_id": upserted_id},
                "original_document": None,
            }
            self._backup_ops.append(InsertOne(backup_doc))

        # Acción de Negocio (solo si hay algo que hacer)
        if doc_to_update or upsert:
            self._business_ops[collection_name].append(UpdateOne(query_filter, update_mutation, upsert=upsert))
            logging.debug(f"Encolada operación UpdateOne (upsert={upsert}) en '{collection_name}'.")
        else:
            logging.warning(f"UpdateOne en '{collection_name}' con filtro {query_filter} no encontró documento y upsert es False. No se encolará operación.")

    def add_update(self, collection_name: str, filter_query: Dict[str, Any], update_query: Dict[str, Any]):
        """
        Encola una operación de actualización masiva.

        Args:
            collection_name (str): La colección de destino.
            filter_query (Dict): El filtro para encontrar documentos a actualizar.
            update_query (Dict): La operación de actualización de pymongo.
        """
        # Acción de Respaldo Preventiva
        target_collection = self.db[collection_name]
        docs_to_update = list(target_collection.find(filter_query))

        if not docs_to_update:
            logging.warning(
                f"UPDATE en '{collection_name}' con filtro {filter_query} no encontró "
                "documentos. La operación no se encolará."
            )
            return

        for doc in docs_to_update:
            backup_doc = {
                "migration_version": self.script_version,
                "collection": collection_name,
                "op_type": "update",
                "op_details": {"filter": filter_query, "mutation": update_query},
                "original_document": doc,
            }
            self._backup_ops.append(InsertOne(backup_doc))

        # Acción de Negocio
        self._business_ops[collection_name].append(UpdateMany(filter_query, update_query))
        logging.debug(f"Encolada operación UPDATE para {len(docs_to_update)} documentos en '{collection_name}'.")

    def add_delete(self, collection_name: str, query_filter: Dict[str, Any]):
        """
        Encola una operación de eliminación masiva.

        Args:
            collection_name (str): La colección de destino.
            query_filter (Dict): El filtro para encontrar documentos a eliminar.
        """
        # Acción de Respaldo Preventiva
        target_collection = self.db[collection_name]
        docs_to_delete = list(target_collection.find(query_filter))

        if not docs_to_delete:
            logging.warning(
                f"DELETE en '{collection_name}' con filtro {query_filter} no encontró "
                "documentos. La operación no se encolará."
            )
            return

        for doc in docs_to_delete:
            backup_doc = {
                "migration_version": self.script_version,
                "collection": collection_name,
                "op_type": "delete",
                "op_details": {"filter": query_filter},
                "original_document": doc,
            }
            self._backup_ops.append(InsertOne(backup_doc))

        # Acción de Negocio
        self._business_ops[collection_name].append(DeleteMany(query_filter))
        logging.debug(f"Encolada operación DELETE para {len(docs_to_delete)} documentos en '{collection_name}'.")