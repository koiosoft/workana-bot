# Sistema de Migraciones de Base de Datos

Este directorio contiene el sistema de gestión de migraciones para la base de datos MongoDB del proyecto. Su propósito es permitir la evolución del esquema y los datos de la base de datos de una manera controlada, versionada y resiliente.

## 🎯 Propósito

A medida que una aplicación evoluciona, su estructura de base de datos necesita cambiar. Este sistema asegura que dichos cambios se apliquen de forma consistente en todos los entornos (desarrollo, producción, etc.) y que puedan ser revertidos de forma segura en caso de fallo.

## 🧩 Conceptos Clave

-   **Motor de Migración (`core/engine.py`)**: Es el orquestador principal. Se encarga de descubrir, ejecutar y revertir los scripts de migración.
-   **Escritor Resiliente (`core/writer.py`)**: Es el corazón de la resiliencia del sistema. Garantiza la atomicidad de las operaciones de datos mediante una estrategia de Write-Ahead Logging (WAL) en una colección de respaldo.
-   **Scripts de Migración (`scripts/`)**: Son archivos de Python individuales donde se definen los cambios específicos para una versión.

## ✍️ Creación de una Nueva Migración

Para crear una nueva migración, puedes usar el CLI del sistema de migraciones.

1.  **Generar el Script Automáticamente (Recomendado)**:
    Desde la raíz del proyecto, ejecuta el siguiente comando:
    ```bash
    python3 migrations/main.py --create "Una descripcion breve de la migracion"
    ```
    Esto creará un nuevo archivo en el directorio `scripts/` con el formato de nombre correcto (`vYYYYMMDD_NN_descripcion.py`) y la plantilla de código necesaria.

2.  **Estructura del Script**:
    El contenido del archivo debe tener una clase `Migration` que herede de `MigrationBase`. A continuación, se muestra una plantilla con ejemplos de las operaciones disponibles:

    ```python
    from migrations.core.base import MigrationBase
    from migrations.core.writer import ResilientBulkWriter
    from pymongo.database import Database

    TARGET_COLLECTION = "users"

    class Migration(MigrationBase):
        """
        Descripción de lo que hace esta migración.
        """
        def up(self, writer: ResilientBulkWriter) -> None:
            """
            Define las operaciones de subida (cambios a aplicar).
            Utiliza SIEMPRE el 'writer' para garantizar la atomicidad.
            """
            # Ejemplo de inserción
            writer.add_insert(TARGET_COLLECTION, {"_id": "new_doc", "name": "John Doe"})

            # Ejemplo de actualización de un único documento (con upsert)
            writer.add_update_one(
                TARGET_COLLECTION,
                query_filter={"_id": "user123"},
                update_mutation={"$set": {"name": "Jane Doe"}},
                upsert=True  # Crea el documento si no existe
            )

            # Ejemplo de actualización de múltiples documentos
            writer.add_update(
                TARGET_COLLECTION,
                query_filter={"status": "active"},
                update_mutation={"$set": {"last_seen": "2026-05-21"}}
            )

            # Ejemplo de eliminación
            writer.add_delete(
                TARGET_COLLECTION,
                query_filter={"status": "inactive"}
            )

        def down(self, db: Database) -> None:
            """
            Define operaciones para revertir cambios de INFRAESTRUCTURA.
            La reversión de DATOS (insert, update, delete) es automática.
            """
            # Ejemplo: si en 'up' creaste un índice, aquí lo borras.
            # try:
            #     db[TARGET_COLLECTION].drop_index("my_index_name")
            # except:
            #     pass
            pass
    ```

### Reglas de Oro

-   **NUNCA** realices operaciones de escritura directas (`db.collection.insert_one`, etc.) dentro del método `up()`. **SIEMPRE** utiliza los métodos del objeto `writer` (`add_insert`, `add_update_one`, `add_update`, `add_delete`).
-   El método `down()` es **exclusivamente** para revertir cambios de infraestructura (ej. crear/eliminar índices). La reversión de datos es automática.

## ▶️ Ejecución y Rollback (Manual)

La ejecución de las migraciones se realiza manually a través de la línea de comandos. Esto te da control total sobre cuándo y cómo se aplican los cambios en la base de datos.

**Nota importante**: Antes de ejecutar estos comandos, asegúrate de haber configurado tu entorno de desarrollo local como se indica en el `README.md` principal del proyecto. Esto implica tener el entorno virtual activado (`source .venv/bin/activate`) y las dependencias instaladas (`pip install -r requirements.txt`).

Asegúrate de que tu archivo `.env.local` esté configurado correctamente, ya que el script de migraciones lo necesita para conectarse a la base de datos.

-   **Aplicar Migraciones Pendientes**:
    Para ejecutar todas las migraciones que no se han aplicado aún:
    ```bash
    python3 migrations/main.py --migrate
    ```

-   **Revertir Migraciones (Rollback)**:
    Para revertir la última migración aplicada:
    ```bash
    python3 migrations/main.py --rollback
    ```
    Para revertir un número específico de migraciones (ej. las últimas 3):
    ```bash
    python3 migrations/main.py --rollback --steps 3
    ```

-   **Estado de las Migraciones**:
    Si una migración falla, su estado se marcará como `FAILED` o `CORRUPTED` en la colección `migration_history`, y el proceso se detendrá para que puedas investigar.