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

El repositorio está organizado según los principios de **Arquitectura Hexagonal** y **Domain-Driven Design (DDD)**, con una separación clara entre el núcleo de la aplicación y las capas de infraestructura:

```
/
├── app/                            # Núcleo de la aplicación (servicio principal del bot)
│   ├── api/                      # Capa de entrada (FastAPI) con rutas y endpoints definidos
│   │   ├── routes/
│   │   │   ├── auth.py           # Endpoints de autenticación (login, register)
│   │   │   ├── projects.py       # Endpoints de gestión de proyectos
│   │   │   └── __init__.py
│   │   └── main.py               # Configuración principal de FastAPI y middleware
│   ├── database/                 # Capa de salida (Outbound Ports) para persistencia
│   │   ├── mongo.py              # Conector asincrónico con MongoDB usando Motor
│   │   ├── repositories/
│   │   │   ├── users_repository.py
│   │   │   ├── projects_repository.py
│   │   │   └── __init__.py
│   │   └── __init__.py
│   ├── intelligence/             # Motor cognitivo (LLM) con Gemini
│   │   └── prompts/
│   │       └── *.j2              # Plantillas de prompts para procesamiento AI
│   ├── scraper/                  # Motor de extracción (Inbound Port)
│   │   └── adaptors/
│   │       └── workana.py        # Implementación con Playwright para Workana
│   └── __init__.py
├── migrations/                   # Sistema de migraciones con PyMongo (sincrónico)
├── browser_data/                 # Datos de sesión del navegador (state.json)
├── data/                         # Volumen persistente para MongoDB
├── logs/                         # Archivos de registro (Loguru)
├── docker-compose.yml            # Orquestador de servicios (app, MongoDB)
└── README.md                     # Esta documentación
```

El repositorio está organizado en los siguientes directorios clave:

```
/
├── app/
│   ├── api/                  # Capa de entrada (FastAPI) con rutas y endpoints definidos
│   │   ├── routes/
│   │   │   ├── auth.py       # Endpoints de autenticación (login, register)
│   │   │   ├── projects.py   # Endpoints de gestión de proyectos
│   │   │   └── __init__.py
│   │   └── main.py           # Configuración principal de FastAPI
│   ├── database/
│   │   ├── mongo.py          # Conexión y configuración de MongoDB
│   │   ├── repositories/
│   │   │   ├── users_repository.py
│   │   │   ├── projects_repository.py
│   │   │   └── __init__.py
│   │   └── __init__.py
│   └── __init__.py
├── browser_data/
├── data/
├── logs/
├── migrations/
├── docker-compose.yml
└── README.md
```

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

### Requisitos Previos
- **Docker y Docker Compose** para entorno aislado
- **Python 3.11+** para migraciones y scripts
- **MongoDB** (local o Dockerizado)

### Configuración Inicial
1. **Clonar el repositorio**:
   ```bash
   git clone <URL_DEL_REPOSITORIO>
   cd workana-bot
   ```
2. **Configurar entorno**:
   - Crear `.env.local` con credenciales
   - Instalar dependencias:
     ```bash
     pip install -r requirements.txt
     ```
3. **Ejecutar servicios**:
   ```bash
   docker-compose up --build
   ```
4. **Verificar arquitectura**:
   - Visitar http://localhost:8000/docs para probar endpoints
   - Revisar logs en `logs/` para seguimiento de operaciones

### Requisitos Previos
- **FastAPI**: Instalado automáticamente desde `requirements.txt`
- **MongoDB**: Servidor local o Dockerizado
- **Python 3.11+**: Para ejecutar scripts de migración

### Inicialización de la API
1. **Ejecutar servicios con Docker**:
   ```bash
   docker-compose up --build
   ```
2. **Verificar endpoints**:
   - Visita `http://localhost:8000/docs` para Swagger UI
   - Prueba endpoints `/api/auth/login` y `/api/projects/`

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

### Pruebas de la API
- **Endpoints validados:**
  ```bash
  curl -X GET http://localhost:8000/api/projects/
  curl -X POST http://localhost:8000/api/auth/login -d '{"email": "test@example.com", "password": "secret"}'
  ```
- **Pruebas automatizadas:**
  - `tests/unit/`: Validación de lógica de negocio, repositorios mockeados, y manejo de errores
  - `tests/integration/`: Flujos end-to-end con MongoDB real
- **Validación con Swagger:**
  http://localhost:8000/docs

### Ejemplo de Endpoints Documentados:
| Ruta                  | Método | Propósito                  | Port Tipo       |
|-----------------------|--------|----------------------------|-----------------|
| `/api/auth/login`     | POST   | Autenticación de usuario   | Inbound Port    |
| `/api/projects/`      | GET    | Listar proyectos           | Inbound Port    |
| `/api/projects/{id}`  | GET    | Detalles de un proyecto    | Inbound Port    |
| `projects_repository.py` | -     | Acceso a MongoDB proyectos | Outbound Port   |
| `users_repository.py` | -      | Gestión de usuarios        | Outbound Port   |

### Pruebas de la API
- `curl` o `httpie` para validar endpoints:
  ```bash
  curl -X GET http://localhost:8000/api/projects/
  ```
- Pruebas automatizadas con `pytest` en `tests/unit/` y `tests/integration/`.
- Validación de esquemas Pydantic en respuestas de API.

### Ejemplo de Endpoints Documentados:
| Ruta                  | Método | Propósito                  |
|-----------------------|--------|----------------------------|
| `/api/auth/login`     | POST   | Autenticación de usuario   |
| `/api/projects/`      | GET    | Listar proyectos           |
| `/api/projects/{id}`  | GET    | Detalles de un proyecto    |

Para ejecutar las pruebas del proyecto (aún por implementar), se utilizará `pytest`.
```bash
pytest
```
