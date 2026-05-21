import os
import sys
import importlib.util
from typing import List, Tuple, Type
import re

from pymongo import DeleteOne, ReplaceOne, InsertOne
from pymongo.database import Database

# Ajustar la ruta para importar desde el directorio raíz del proyecto
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from migrations.core.base import MigrationBase
from migrations.core.writer import ResilientBulkWriter, BACKUP_COLLECTION
from utils.logger import get_logger, critical_alert_handler

# Constantes
HISTORY_COLLECTION = "migration_history"
# La ruta a los scripts ahora es relativa a la ubicación de este archivo
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts'))

class MigrationEngine:
    """
    Orquestador central de migraciones. Descubre, ejecuta y revierte scripts
    de migración de forma secuencial y resiliente.
    """

    def __init__(self, db: Database):
        self.db = db
        self.logger = get_logger(self.__class__.__name__)
        self.db.get_collection(HISTORY_COLLECTION).create_index(
            "version", unique=True
        )

    def _get_migration_scripts(self) -> List[Tuple[str, Type[MigrationBase]]]:
        """
        Descubre, importa y carga dinámicamente los scripts de migración.
        Valida y ordena los scripts por su versión (vYYYYMMDD_NN_desc).
        """
        scripts = []
        if not os.path.exists(SCRIPTS_DIR):
            self.logger.warning(f"El directorio de scripts '{SCRIPTS_DIR}' no existe. No se cargarán migraciones.")
            return scripts

        for filename in sorted(os.listdir(SCRIPTS_DIR)):
            if not filename.endswith(".py") or filename.startswith("__"):
                continue

            match = re.match(r"^(v\d{8}_\d{2})_.*\.py$", filename)
            if not match:
                self.logger.warning(f"El archivo '{filename}' no sigue el formato de nombre esperado y será ignorado.")
                continue
            
            version = match.group(1)
            module_name = filename[:-3]
            filepath = os.path.join(SCRIPTS_DIR, filename)

            spec = importlib.util.spec_from_file_location(module_name, filepath)
            module = importlib.util.module_from_spec(spec)
            
            # Asegurarse de que el módulo pueda encontrar otros módulos del proyecto
            if project_root not in sys.path:
                 sys.path.insert(0, project_root)
            
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, MigrationBase) and attr is not MigrationBase:
                    scripts.append((version, attr))
                    break
        
        return scripts

    def migrate(self):
        """Ejecuta todas las migraciones pendientes en orden cronológico."""
        self.logger.info("Iniciando proceso de migración...")
        all_scripts = self._get_migration_scripts()
        history_collection = self.db[HISTORY_COLLECTION]

        for version, migration_cls in all_scripts:
            migration_record = history_collection.find_one({"version": version})

            if migration_record:
                if migration_record["status"] == "SUCCESS":
                    self.logger.info(f"Migración '{version}' ya ejecutada. Omitiendo.")
                    continue
                elif migration_record["status"] == "CORRUPTED":
                    self.logger.critical(f"La migración '{version}' está en estado CORRUPTED. Abortando ejecución.")
                    sys.exit(1)
            
            self.logger.info(f"Ejecutando migración '{version}'...")
            migration_instance = migration_cls()
            
            try:
                # Usar update_one con upsert para evitar errores de clave duplicada
                # si la migración se está re-ejecutando después de un rollback.
                history_collection.update_one(
                    {"version": version},
                    {"$set": {"status": "PENDING"}},
                    upsert=True
                )

                # El motor crea y gestiona el ciclo de vida del writer.
                # El script de migración solo recibe y utiliza el writer.
                with ResilientBulkWriter(
                    script_version=version,
                    client=self.db.client,
                    db_name=self.db.name
                ) as writer:
                    migration_instance.up(writer)

                history_collection.update_one(
                    {"version": version}, {"$set": {"status": "SUCCESS"}}
                )
                self.logger.info(f"Migración '{version}' completada con éxito.")

            except Exception as e:
                self.logger.error(f"Fallo al ejecutar la migración '{version}': {e}", exc_info=True)
                self.logger.info(f"Iniciando rollback para la migración fallida '{version}'...")
                self._rollback_one(version, migration_instance)
                # El rollback ya maneja el estado CORRUPTED y sale si es necesario.
                break # Detener el proceso de migración

    def rollback(self, steps: int):
        """Revierte las últimas N migraciones ejecutadas con éxito."""
        self.logger.info(f"Iniciando proceso de rollback para las últimas {steps} migraciones.")
        
        migrations_to_rollback = self.db[HISTORY_COLLECTION].find(
            {"status": "SUCCESS"}
        ).sort([("version", -1)]).limit(steps)

        scripts_map = {version: cls for version, cls in self._get_migration_scripts()}

        for migration_record in migrations_to_rollback:
            version = migration_record["version"]
            if version not in scripts_map:
                self.logger.critical(f"No se encontró el script para la migración '{version}'. No se puede revertir.")
                self._mark_as_corrupted(version, "Script de migración no encontrado.")
                sys.exit(1)

            migration_instance = scripts_map[version]()
            self._rollback_one(version, migration_instance)

    def _rollback_one(self, version: str, migration_instance: MigrationBase):
        """Ejecuta el pipeline de rollback híbrido para una única versión."""
        try:
            # --- Fase 1: Down Automático (Capa Orquestador) ---
            self.logger.info(f"Fase 1: Reversión automática de datos para '{version}'...")
            backup_docs = list(self.db[BACKUP_COLLECTION].find({"migration_version": version}))
            
            if backup_docs:
                reverse_ops = []
                for backup in reversed(backup_docs): # Procesar en orden inverso a la creación
                    op_type = backup["op_type"]
                    collection = backup["collection"]
                    if op_type == "insert":
                        reverse_ops.append(DeleteOne({"_id": backup["op_details"]["_id"]}))
                    elif op_type == "update":
                        original_doc = backup["original_document"]
                        reverse_ops.append(ReplaceOne({"_id": original_doc["_id"]}, original_doc))
                    elif op_type == "delete":
                        reverse_ops.append(InsertOne(backup["original_document"]))

                if reverse_ops:
                    self.logger.info(f"Aplicando {len(reverse_ops)} operaciones inversas en '{collection}'...")
                    self.db[collection].bulk_write(reverse_ops)
            
            self.logger.info("Fase 1 completada.")

            # --- Fase 2: Down Programático (Capa Script) ---
            self.logger.info(f"Fase 2: Ejecutando 'down()' programático para '{version}'...")
            migration_instance.down(self.db)
            self.logger.info("Fase 2 completada.")

            # Si todo fue bien, se actualiza el historial
            self.db[HISTORY_COLLECTION].update_one(
                {"version": version}, {"$set": {"status": "ROLLED_BACK"}}
            )
            self.db[BACKUP_COLLECTION].delete_many({"migration_version": version})
            self.logger.info(f"Rollback de '{version}' completado con éxito.")

        except Exception as e:
            error_msg = f"Fallo catastrófico durante el rollback de '{version}': {e}"
            self.logger.critical(error_msg, exc_info=True)
            self._mark_as_corrupted(version, error_msg)
            sys.exit(1)

    def _mark_as_corrupted(self, version: str, reason: str):
        """Marca una migración como corrupta y envía una alerta."""
        self.db[HISTORY_COLLECTION].update_one(
            {"version": version}, {"$set": {"status": "CORRUPTED", "error": reason}}
        )
        alert_message = f"MIGRACIÓN CORRUPTA: La versión '{version}' ha fallado irreversiblemente. Razón: {reason}. Se requiere intervención manual."
        critical_alert_handler(alert_message)
        self.logger.critical(alert_message)
