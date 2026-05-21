# Módulo de Aplicación Principal (Workana Bot Service)

Este directorio contiene el núcleo de la lógica de negocio del Workana Bot. Funciona como un servicio autocontenido responsable de orquestar el scraping, la inteligencia artificial, la persistencia en base de datos y la comunicación con el usuario.

## 🏛️ Arquitectura del Módulo

El flujo de trabajo principal de la aplicación es el siguiente:

1.  El **Punto de Entrada (`main.py`)** inicia y coordina todos los componentes del bot.
2.  El **Scraper (`scraper/`)** se encarga de extraer datos de la plataforma Workana (o de generar datos de prueba, según la configuración).
3.  Los datos extraídos se guardan en la base de datos a través del **Repositorio (`database/`)**.
4.  El módulo de **Inteligencia (`intelligence/`)** procesa los proyectos almacenados, los evalúa utilizando un modelo de IA (Gemini) y genera propuestas.
5.  El **Bot (`bots/`)** utiliza la información procesada para comunicarse con los administradores a través de plataformas como Telegram, enviando notificaciones y recibiendo comandos.

### Descripción de Componentes

-   **`main.py`**: El orquestador principal del bot. Es responsable de iniciar el ciclo de vida de la aplicación y poner en marcha los bucles de scraping y análisis.
-   **`bots/`**: Capa de interfaz con el usuario final. Abstrae la lógica de comunicación con diferentes plataformas de mensajería (ej. Telegram), permitiendo enviar notificaciones y gestionar comandos.
-   **`config/`**: Contiene la configuración centralizada de la aplicación, como la conexión a la base de datos y la carga de variables de entorno.
-   **`database/`**: Capa de Acceso a Datos (DAO). Define los repositorios que abstraen las operaciones CRUD (Crear, Leer, Actualizar, Borrar) con las colecciones de MongoDB.
-   **`intelligence/`**: El cerebro del bot. Aquí reside la lógica para interactuar con servicios de IA externos.
-   **`scraper/`**: Módulo de extracción de datos. Contiene los adaptadores para navegar por sitios web (Workana) o generar datos falsos para pruebas.

## ⚙️ Configuración (Variables de Entorno)

Este servicio depende de las siguientes variables de entorno para su correcto funcionamiento. Deben estar definidas en un archivo `.env` o `.env.local` en la raíz del proyecto.

-   `SCRAPER_SOURCE`: Define el origen de los datos. Usa `workana` para producción o `dummy` para pruebas.
-   `MONGO_URI`: La cadena de conexión a la base de datos MongoDB.
-   `MONGO_DB_NAME`: El nombre de la base de datos a utilizar.
-   `GEMINI_API_KEY`: La clave de API para acceder a los servicios de Google Gemini.
-   `TELEGRAM_BOT_TOKEN`: El token de autenticación para el bot de Telegram.
-   `MY_TELEGRAM_ID`: El ID del chat de Telegram del administrador al que se enviarán las notificaciones.

## 🐳 Ejecución en Aislamiento

Aunque la forma recomendada de ejecutar el proyecto es con `docker-compose` desde la raíz, este módulo está contenerizado y puede ejecutarse de forma independiente para pruebas.

1.  **Construir la imagen de Docker**:
    Desde el directorio raíz del proyecto, puedes construir solo esta imagen:
    ```bash
    docker-compose build app
    ```

2.  **Ejecutar el contenedor**:
    Asegúrate de pasar las variables de entorno necesarias.
    ```bash
    docker run --rm \
      --env-file=../.env.local \
      --name workana-app-instance \
      workana-bot_app
    ```
    **Nota**: Para que el contenedor se conecte a otros servicios (como una base de datos en `localhost`), necesitarás configurar la red de Docker adecuadamente (e.g., `--network=host` o creando una red común).
