# Workana Bot

Bienvenido al proyecto Workana Bot. Este sistema está diseñado para automatizar la búsqueda, evaluación y propuesta de proyectos en la plataforma Workana, utilizando un stack tecnológico moderno que incluye web scraping, inteligencia artificial y comunicación a través de bots.

## 📋 Características Principales

- **Scraping Automatizado**: Extrae información de nuevos proyectos de Workana de forma continua.
- **Análisis con IA**: Utiliza modelos de lenguaje (como Gemini) para evaluar la viabilidad de un proyecto y generar borradores de propuestas.
- **Base de Datos Persistente**: Almacena proyectos, evaluaciones y propuestas en una base de datos MongoDB.
- **Sistema de Migraciones Resiliente**: Gestiona la evolución del esquema de la base de datos de forma segura y atómica.
- **Notificaciones por Bot**: Se comunica con los administradores a través de un bot de Telegram.
- **Contenerización**: Todo el sistema está preparado para ejecutarse de forma aislada y consistente utilizando Docker y Docker Compose.

## 📂 Estructura del Proyecto

El repositorio está organizado en los siguientes directorios clave:

```
/
├── app/                # Núcleo de la aplicación (servicio principal del bot).
├── browser_data/       # Datos de sesión del navegador para el scraper.
├── data/               # Volumen persistente para la base de datos MongoDB.
├── logs/               # Archivos de log generados por la aplicación.
├── migrations/         # Sistema de gestión de migraciones de la base de datos.
├── docker-compose.yml  # Orquestador de los servicios de la aplicación.
└── README.md           # Esta documentación.
```

## 🚀 Empezando

Sigue estas instrucciones para poner en marcha el proyecto en tu entorno local.

### Requisitos Previos

- **Docker y Docker Compose**: [Instrucciones de instalación](https://docs.docker.com/get-docker/).
- **Git**: Para clonar el repositorio.
- **Python 3.11+**: Para ejecutar scripts locales como el de migraciones.

### Instalación y Configuración

1.  **Clona el repositorio**:
    ```bash
    git clone <URL_DEL_REPOSITORIO>
    cd workana-bot
    ```

2.  **Configura las variables de entorno**:
    El proyecto utiliza archivos `.env` para la configuración. La forma recomendada es crear un archivo `.env.local` que no será versionado y contendrá tus secretos.

    Crea un archivo `.env.local` en la raíz del proyecto con el siguiente contenido. Reemplaza los valores de ejemplo con tus credenciales reales.

    ```dotenv
    # --- Fuente de Datos: 'workana' para producción, 'dummy' para pruebas ---
    SCRAPER_SOURCE=workana

    # --- Credenciales del Bot de Telegram ---
    TELEGRAM_BOT_TOKEN=TU_TOKEN_DE_TELEGRAM_AQUI
    MY_TELEGRAM_ID=TU_ID_DE_TELEGRAM_AQUI

    # --- Inteligencia Artificial (Gemini) ---
    GEMINI_API_KEY=TU_API_KEY_DE_GEMINI_AQUI

    # --- Configuración de la Base de Datos ---
    # Para Docker (recomendado), el host es el nombre del servicio en docker-compose.yml
    MONGO_URI=mongodb://admin:super_password_123@mongodb:27017/
    MONGO_DB_NAME=workana_bot

    # --- Variables para inicializar la BD en Docker ---
    MONGO_USER=admin
    MONGO_PASS=super_password_123
    ```
    **Nota:** El archivo `.env` puede existir para valores por defecto, pero `.env.local` siempre tendrá prioridad.

3.  **Configura el entorno virtual de Python (para desarrollo local)**:
    Para ejecutar scripts de mantenimiento, migraciones o pruebas localmente, necesitas un entorno virtual con las dependencias del proyecto.

    ```bash
    # 1. Crea el entorno virtual
    python3 -m venv .venv

    # 2. Actívalo (en macOS/Linux)
    source .venv/bin/activate
    # En Windows usa: .venv\Scripts\activate

    # 3. Instala todas las dependencias (app + desarrollo)
    pip install -r requirements.txt
    ```
    Este entorno te permitirá que herramientas como VSCode (Pylance) reconozcan las librerías instaladas.

### 4. Obtención de Credenciales (API Keys)

Para que la aplicación funcione, necesitas obtener credenciales para los servicios de Telegram y Google Gemini.

#### 🤖 Telegram Bot

1.  **Habla con BotFather**: En Telegram, busca el bot verificado `BotFather` y empieza una conversación.
2.  **Crea un nuevo bot**: Envía el comando `/newbot`. Sigue las instrucciones para darle un nombre y un nombre de usuario a tu bot.
3.  **Obtén el Token**: Al finalizar, BotFather te dará un token de acceso. Cópialo y pégalo en la variable `TELEGRAM_BOT_TOKEN` de tu archivo `.env.local`.
4.  **Obtén tu ID de usuario**: Busca el bot `@userinfobot` en Telegram, inicia una conversación y te enviará tu ID de usuario. Cópialo en la variable `MY_TELEGRAM_ID`.

#### ✨ Google Gemini

1.  **Ve a Google AI Studio**: Accede a [Google AI Studio](https://aistudio.google.com/).
2.  **Crea una API Key**: En el menú de la izquierda, haz clic en "Get API key" y luego en "Create API key".
3.  **Obtén la Key**: Se generará una nueva clave. Cópiala y pégala en la variable `GEMINI_API_KEY` de tu archivo `.env.local`.

### Uso

#### Ejecución con Docker (Recomendado)

El método preferido para ejecutar la aplicación es a través de Docker Compose, ya que gestiona todos los servicios (la aplicación principal y la base de datos) de forma automática.

1.  **Levanta los servicios**:
    Desde la raíz del proyecto, ejecuta:
    ```bash
    docker-compose up --build
    ```
    El flag `--build` reconstruye las imágenes si ha habido cambios en el código. La primera vez es obligatorio.

2.  **Detener los servicios**:
    Para detener la ejecución, presiona `Ctrl + C` en la terminal donde se está ejecutando.

#### Ejecución de Migraciones

El sistema de migraciones te permite gestionar la evolución de la base de datos. **A diferencia de versiones anteriores, la ejecución ahora es manual.**

Para más detalles, consulta la documentación en `migrations/README.md`.

1.  **Crear una nueva migración**:
    ```bash
    python3 migrations/main.py --create "Breve descripcion de la migracion"
    ```

2.  **Aplicar migraciones pendientes**:
    ```bash
    python3 migrations/main.py --migrate
    ```

## ✅ Testing

Para ejecutar las pruebas del proyecto (aún por implementar), se utilizará `pytest`.
```bash
pytest
```
