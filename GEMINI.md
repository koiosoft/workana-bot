# Resumen de Cambios (Sesión del 2026-05-21)

## Refactorización de Dependencias

Se ha refactorizado la gestión de dependencias de Python para diferenciar entre el entorno de producción (Docker) y el entorno de desarrollo local.

1.  **`app/requirements.txt`**: Este archivo se mantiene y contiene **únicamente** las dependencias necesarias para que la aplicación se ejecute en producción. El `Dockerfile` de la aplicación utiliza este archivo, garantizando que la imagen final sea ligera.

2.  **`requirements.txt` (Raíz)**: Se ha creado un nuevo archivo de requisitos en la raíz del proyecto. Este archivo está destinado a la configuración del **entorno de desarrollo local**. Su contenido es:
    ```
    -r app/requirements.txt
    playwright-stealth
    ```
    Esto permite instalar todas las dependencias del proyecto (las de la app + las de desarrollo) con un solo comando: `pip install -r requirements.txt`.

## Actualización de Documentación

Se han actualizado los archivos `README.md` para reflejar la nueva estructura de dependencias:

-   **`README.md` (Raíz)**: Se ha añadido una sección que explica cómo configurar el entorno virtual de Python (`.venv`) y cómo instalar las dependencias de desarrollo usando el nuevo `requirements.txt` de la raíz.
-   **`migrations/README.md`**: Se ha añadido una nota para recordar a los desarrolladores que deben tener el entorno local configurado antes de poder ejecutar los scripts de migración.
