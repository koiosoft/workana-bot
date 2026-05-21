import argparse
import sys
import os
import re
from datetime import datetime
# Añadir el directorio raíz del proyecto al sys.path
# Esto permite que el script encuentre módulos como 'database'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)


from database.connection import get_db_connection, close_db_connection
from migrations.core.engine import MigrationEngine

MIGRATION_TEMPLATE = '''from migrations.core.base import MigrationBase
from migrations.core.writer import ResilientBulkWriter
from pymongo.database import Database

# El nombre de la colección objetivo
TARGET_COLLECTION = "projects"

class Migration(MigrationBase):
    """
    Descripción de lo que hace esta migración.
    """
    def up(self, writer: ResilientBulkWriter) -> None:
        """
        Define las operaciones de subida (cambios a aplicar).
        Utiliza SIEMPRE el 'writer' para garantizar la atomicidad.
        """
        # Ejemplo: writer.add_insert(TARGET_COLLECTION, {"_id": "new_doc"})
        pass

    def down(self, db: Database) -> None:
        """
        Define operaciones para revertir cambios de INFRAESTRUCTURA.
        La reversión de DATOS (insert, update, delete) es automática.
        """
        # Ejemplo: db[TARGET_COLLECTION].drop_index("my_index_name")
        pass
'''

def create_migration_script(description: str):
    """Genera un nuevo script de migración con un nombre versionado."""
    # La ruta ahora es relativa a la ubicación del script (migrations/main.py)
    scripts_dir = os.path.join(os.path.dirname(__file__), "scripts")
    if not os.path.exists(scripts_dir):
        os.makedirs(scripts_dir)

    # Limpiar y normalizar la descripción para el nombre de archivo
    clean_desc = re.sub(r'[^a-z0-9_]+', '', description.lower().replace(' ', '_'))
    
    # Determinar el siguiente número de versión
    today_str = datetime.now().strftime('%Y%m%d')
    prefix = f"v{today_str}_"
    
    max_seq = 0
    for filename in os.listdir(scripts_dir):
        if filename.startswith(prefix):
            try:
                seq_str = filename.split('_')[1]
                max_seq = max(max_seq, int(seq_str))
            except (IndexError, ValueError):
                continue
    
    next_seq = max_seq + 1
    version_str = f"{prefix}{next_seq:02d}"
    
    # Crear el nombre y la ruta del archivo final
    file_name = f"{version_str}_{clean_desc}.py"
    file_path = os.path.join(scripts_dir, file_name)
    
    # Escribir la plantilla en el nuevo archivo
    with open(file_path, 'w') as f:
        f.write(MIGRATION_TEMPLATE)
        
    print(f"Script de migración creado con éxito en: {file_path}")


def main():
    """
    Punto de entrada principal para la interfaz de línea de comandos (CLI)
    del sistema de migraciones.
    """
    parser = argparse.ArgumentParser(
        description="Herramienta de Orquestación de Migraciones de Base de Datos."
    )
    
    parser.add_argument(
        '--create',
        type=str,
        metavar='DESCRIPTION',
        help="Crea un nuevo script de migración con el nombre descriptivo proporcionado."
    )
    parser.add_argument(
        '--migrate',
        action='store_true',
        help="Ejecuta las migraciones pendientes en orden cronológico."
    )
    parser.add_argument(
        '--rollback',
        action='store_true',
        help="Revierte las últimas migraciones. Usar con --steps."
    )
    parser.add_argument(
        '--steps',
        type=int,
        default=1,
        help="Número de migraciones a revertir. Requiere --rollback. (default: 1)"
    )

    args = parser.parse_args()

    if args.create:
        create_migration_script(args.create)
        sys.exit(0)

    # Las operaciones de migración y rollback requieren conexión a la BD
    try:
        db = get_db_connection()
        # El motor ahora se importa desde la nueva ubicación
        engine = MigrationEngine(db)
    except Exception as e:
        print(f"No se pudo inicializar el motor de migración: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.migrate:
            engine.migrate()
        elif args.rollback:
            engine.rollback(steps=args.steps)
        else:
            parser.print_help()
            print("\nPor favor, especifique una acción: --create, --migrate o --rollback.", file=sys.stderr)
            sys.exit(1)
    finally:
        # Asegurar que la conexión a la base de datos siempre se cierre
        close_db_connection()


if __name__ == "__main__":
    # Asegurarse de que el contexto de ejecución sea el correcto
    # al ejecutar el script directamente.
    main()