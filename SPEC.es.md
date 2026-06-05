# ESPECIFICACIÓN DE DISEÑO DE SOFTWARE (SDD) - WORKANA BOT

## 1. OBJETIVO DEL SISTEMA

### 1.1 Declaración de Propósito
El objetivo primordial de **Workana Bot** es automatizar de forma integral y resiliente el ciclo de vida de prospección en la plataforma Workana. Esto comprende el descubrimiento ininterrumpido de nuevos proyectos de desarrollo, su evaluación cognitiva mediante Inteligencia Artificial y la generación automatizada de propuestas altamente personalizadas para los administradores del sistema, optimizando tiempos de respuesta y maximizando las oportunidades de adjudicación.

### 1.2 Objetivos Técnicos de Alto Nivel
*   **Automatización No Invasiva:** Implementar un pipeline de ingesta automatizada (Scraper) capaz de lidiar con renderizado dinámico e interactividad compleja en plataformas SPA (Single Page Applications).
*   **Evaluación Cognitiva Desacoplada:** Clasificar y estimar la viabilidad técnica y comercial de cada proyecto recolectado utilizando modelos avanzados de procesamiento de lenguaje natural (LLM) a través de un motor cognitivo aislado.
*   **Persistencia Segura e Idempotente:** Registrar estructuradamente todos los proyectos, auditorías de evaluación, semáforos de control y propuestas, garantizando la consistencia transaccional y la trazabilidad del estado.
*   **Notificación y Control en Tiempo Real:** Proveer una consola operativa bidireccional basada en un bot de Telegram, sirviendo como canal único para alertar, interactuar y ejecutar transacciones de negocio.
*   **Aislamiento de Infraestructura:** Minimizar la dependencia ambiental garantizando una empaquetación lista para producción mediante contenedores Docker, aislados a nivel de red y volumen de datos.

---

## 2. REGLAS DE ARQUITECTURA Y DISEÑO

El sistema está estructurado bajo los principios de **Diseño Guiado por el Dominio (DDD)** y la **Arquitectura Hexagonal (Puertos y Adaptadores)**. Ningún detalle de infraestructura (frameworks, librerías de persistencia, APIs externas) debe permear la lógica de negocio nuclear.

```
       [External Clients/Triggers]
                    |
                    v
         +---------------------+
         |   Driving Adaptor   |  (e.g., Telegram Bot Interface)
         +---------------------+
                    |
                    v
         +---------------------+
         |     Inbound Port    |  (Abstract Base Interfaces)
         +---------------------+
                    |
                    v
    =================================
    ||       APPLICATION CORE      ||  (Pure Business & Domain Logic)
    =================================
                    |
                    v
         +---------------------+
         |    Outbound Port    |  (Abstract Infrastructure Interfaces)
         +---------------------+
                    |
                    v
         +---------------------+
         |   Driven Adaptor    |  (e.g., Motor Repository, Playwright Scraper)
         +---------------------+
                    |
                    v
       [External Databases / APIs]
```

### 2.1 Principios de Inversión de Dependencias (DIP) y Aislamiento
1.  **Abstracción en las Fronteras:** Los módulos de mayor nivel (`scraper`, `intelligence`, `database`) deben interactuar únicamente mediante contratos abstractos (Ports). Los adaptadores concretos (e.g., Playwright, Gemini SDK, Motor) se inyectan en tiempo de ejecución.
2.  **No Fugas de Infraestructura (Zero Leakage):** Los tipos de datos o excepciones específicos de adaptadores externos jamás deben cruzar las fronteras de su módulo sin traducción previa. El scraper debe convertir los elementos DOM o selectores de Playwright a tipos primitivos de Python o modelos Pydantic puramente semánticos antes de enviarlos al núcleo de la aplicación.
3.  **Aislamiento Horizontal de Módulos:** Está estrictamente prohibido que un adaptador interactúe directamente con otro adaptador (e.g., el scraper no debe realizar escrituras directas en la base de datos). Toda comunicación se coordina mediante la capa de aplicación core.

### 2.2 Topología del Proyecto y Estructura de Directorios
La jerarquía de archivos se define estrictamente para soportar la segregación hexagonal de responsabilidades:

```
.
├── app/                           # Monolito Principal de la Aplicación
│   ├── bots/                      # Adaptadores Primarios / Conductores (Ruteo, comandos y estados de Telegram)
│   ├── config/                    # Motor de Configuración: Validación inmutable de variables de entorno
│   ├── database/                  # Infraestructura de Datos: Adaptadores secundarios, repositorios y control de semáforos
│   ├── intelligence/              # Motor Cognitivo: Adaptadores e integraciones LLM
│   │   └── prompts/               # Plantillas Jinja2 versionadas para ingeniería de prompts
│   └── scraper/                   # Motor de Ingesta: Adaptadores de raspado web (Playwright, bs4)
│       └── adaptors/              # Implementaciones concretas (workana, dummy test suites)
├── migrations/                    # Gestión de Esquemas de Base de Datos y Datos Semilla (Síncronos, PyMongo)
│   └── scripts/                   # Scripts de migración idempotentes autogestionados
├── scripts/                       # Mantenimiento, utilidades y scripts operacionales auxiliares
├── tests/                         # Suites de pruebas automatizadas (unitarias y de integración)
├── .env.example                   # Definición del esquema declarativo de variables de entorno
├── docker-compose.yml             # Orquestación de infraestructura local de servicios (App, MongoDB)
└── requirements.txt               # Registro y fijación de dependencias del ecosistema
```

### 2.3 Gestión de Concurrencia y Recursos Críticos
*   **Garantía de Liberación de Recursos:** Todo recurso que gestione concurrencia o acceso exclusivo (como el semáforo de procesamiento) debe ser encapsulado en un gestor de contexto asíncrono (`async with`). Esta medida es mandatoria para garantizar que, incluso ante fallos inesperados o excepciones no controladas durante la operación, el recurso se libere correctamente, evitando bloqueos permanentes (`deadlocks`) en el sistema.

---

## 3. DISEÑO DE DATOS Y PERSISTENCIA

### 3.1 Motores y Controladores Diferenciados
El sistema implementa persistencia políglota a nivel de controladores para optimizar los ciclos de ejecución:
*   **Entorno de Aplicación (Asíncrono):** Utiliza `motor` (basado en `asyncio`) para todas las consultas y escrituras del bot, asegurando que el bucle de eventos no se bloquee durante operaciones de E/S.
*   **Entorno de Migraciones (Síncrono):** Utiliza `pymongo` para garantizar un control atómico y secuencial, asegurando que las alteraciones de esquema no sufran condiciones de carrera.

### 3.2 Evolución del Esquema: Sistema de Migraciones
Toda modificación en las colecciones e índices de MongoDB debe ejecutarse a través del framework personalizado de migraciones ubicado en `migrations/`. **Las modificaciones manuales directas están estrictamente prohibidas en cualquier entorno.**

*   **Idempotencia y Versionado:** Cada migración es un script de Python versionado por fecha (`vYYYYMMDD_NN_...`). Su reejecución repetida debe dar como resultado exactamente el mismo estado final en la base de datos sin generar inconsistencias.
*   **Operaciones Atómicas (`ResilientBulkWriter`):** Se prohíbe el uso de comandos crudos de modificación. Se debe utilizar la API de `ResilientBulkWriter` (`writer`) dentro de los scripts, la cual garantiza la atomicidad de las operaciones de datos mediante una estrategia de Write-Ahead Logging (WAL).
*   **CLI para Gestión:** La creación, ejecución y reversión de migraciones se gestiona mediante una interfaz de línea de comandos (`python3 migrations/main.py`), permitiendo un control explícito sobre el ciclo de vida de la base de datos:
    *   `--create "descripcion"`: Genera una nueva plantilla de migración.
    *   `--migrate`: Aplica todas las migraciones pendientes.
    *   `--rollback`: Revierte la última migración aplicada.
*   **Rollback Inteligente:** El método `up()` de una migración define los cambios de datos e infraestructura. La reversión de los **datos** es automática gracias al `ResilientBulkWriter`. El método `down()` se reserva exclusivamente para revertir cambios de **infraestructura** (ej. eliminar un índice).

---

## 4. ESTRATEGIA DE PRUEBAS

El proyecto adopta una estrategia de pruebas multinivel gestionada con `pytest` para garantizar la calidad y estabilidad del código. Las dependencias de desarrollo se gestionan en `requirements-dev.txt`.

### 4.1 Pruebas Unitarias (`tests/unit/`)
*   **Filosofía:** Prueban componentes de lógica de negocio en completo aislamiento, utilizando mocks para simular dependencias externas (bases de datos, APIs de IA, etc.). Son la base de la pirámide de pruebas y se ejecutan rápidamente.
*   **Alcance:**
    *   Lógica de clasificación y procesamiento de proyectos.
    *   Validación de la selección de plantillas de propuestas.
    *   Formateo y construcción de mensajes para Telegram.
    *   Comportamiento de los repositorios (con la base de datos mockeada).
    *   **Manejo de Errores Críticos:** Se valida explícitamente la resiliencia del sistema, incluyendo reintentos automáticos ante fallos de red, la correcta activación del `Circuit Breaker` y la liberación del semáforo de concurrencia en caso de error.

### 4.2 Pruebas de Integración (`tests/integration/`)
*   **Filosofía:** Verifican la correcta colaboración entre varios componentes del sistema. Requieren una instancia real de servicios externos, principalmente una base de datos MongoDB.
*   **Alcance:**
    *   Correcta creación de índices en la base de datos al iniciar la aplicación.
    *   Flujos de datos de extremo a extremo (ej. desde la recepción de un proyecto hasta su almacenamiento con un `contract_type` específico).
    *   Validación de la integridad estructural de los datos guardados en la base de datos.
*   **Ejecución Condicional:** Estos tests se saltan automáticamente si no se provee una cadena de conexión a la base de datos (`MONGODB_URI`), permitiendo ejecutar el resto de la suite en entornos sin servicios.

### 4.3 Ejecución de la Suite
La suite de pruebas se puede ejecutar con granularidad desde la raíz del proyecto:
*   **Todos los tests:** `pytest tests/ -v`
*   **Solo unitarios:** `pytest tests/unit/ -v`
*   **Generar reporte de cobertura:** `pytest tests/ --cov=app --cov-report=html`

---

## 5. SCRIPTS DE UTILIDAD (`scripts/`)

El directorio `scripts/` contiene herramientas operacionales y de diagnóstico para facilitar el desarrollo, la configuración y el mantenimiento del sistema.

*   `check_projects.py`: Script de diagnóstico que se conecta a MongoDB y reporta el estado actual de los proyectos en el pipeline de procesamiento. Permite verificar cuántos proyectos están analizados, cuántos tienen un puntaje de IA suficiente y cuántos están listos para la siguiente etapa.
*   `extract_session.py`: Operational utility executed manually by the developer in non-headless mode to handle initial authentication and dump the session cookies into `state.json`. *Note: Excluded from production runtime.*
*   `test_bot_session.py`: Smoke-test script executed manually to verify that the generated `state.json` successfully authenticates a headless browser instance before deploying the main application.
*   `get-gemini-images.py`: Utilidad para interactuar con la API de Google Gemini. Lista todos los modelos de IA disponibles para la clave de API configurada, permitiendo al desarrollador verificar la conexión y conocer los nombres de los modelos que puede utilizar.

---

## 6. INGESTACIÓN Y COMPONENTES OPERATIVOS

### 6.1 Ingesta Resiliente (Scraper)
*   **Estrategia de Renderizado:** El adaptador de producción (`workana.py`) utiliza Playwright de forma headless para sortear protecciones y renderizar dinámicamente el contenido Javascript.
*   **Parser de Alto Rendimiento:** La estructuración del DOM en memoria se delega a BeautifulSoup4 por su eficiencia de CPU.
*   **Selectores Defensivos y Parseo Robusto:** La extracción de datos debe utilizar selectores CSS defensivos que no fallen si un atributo cambia. Los datos extraídos deben ser validados y parseados en modelos Pydantic que utilicen tipos opcionales (`Optional[...]`) y valores por defecto para prevenir que cambios menores en el DOM de la web de origen generen errores fatales.
*   **Gestión y resiliencia de sesiones:** Las cookies y los identificadores de sesión se cargan desde un archivo `state.json` preexistente para evitar costosas reautenticaciones que activan alertas de seguridad. Si se detecta que este estado de sesión ha caducado o no es válido durante la ejecución, la automatización debe interrumpir la ejecución de forma controlada, generando un registro/notificación crítico que indica al usuario que regenere manualmente el estado mediante `scripts/extract_session.py` y lo valide mediante `scripts/test_bot_session.py`.

### 6.2 Arquitectura Cognitiva (Intelligence)
*   **Integración SDK:** Uso directo del SDK oficial de Google `google-genai` para el procesamiento con Gemini.
*   **Contención de Prompts:** Los prompts de IA se estructuran fuera del código python en archivos `.j2` (Jinja2) bajo `app/intelligence/prompts/` para permitir una iteración y versionamiento limpios de la ingeniería de prompts.
*   **Resolución Dinámica de Rutas:** La carga de plantillas `.j2` debe realizarse utilizando rutas dinámicas y robustas, basadas en la ubicación del archivo que las carga (e.g., `pathlib.Path(__file__).parent`). Se prohíbe el uso de rutas relativas o absolutas hardcodeadas para evitar fallos de ejecución en distintos contextos.

### 6.3 Canal Operativo (Telegram Bot)
*   **Asincronía Extrema:** Implementado mediante `python-telegram-bot` en su modo completamente asíncrono para escalar simultáneamente con las llamadas al Scraper y base de datos.
*   **Resiliencia de Conexión:** Implementación de disyuntores (Circuit Breakers) y reintentos exponenciales en los manejadores de comandos para evitar caídas en cascada si las APIs externas fallan temporalmente.

---

## 7. ESTÁNDARES DE CODIFICACIÓN Y CALIDAD

### 7.1 Calidad de Código y Estilo
*   **Tipado Estricto:** Toda firma de función, método o corutina debe definir completamente el tipo de datos de entrada y salida mediante anotaciones de tipo de Python (`typing`, `Pydantic`).
*   **Estilo Uniforme:** Alineación absoluta con **PEP 8**, formateado automatizado con `black` y ordenamiento de importaciones con `isort`.
*   **Comentarios de Valor:** No duplicar la lógica implícita. Los comentarios de código explican el **porqué** de decisiones de optimización o invariants complejas.

### 7.2 Logging Profesional
*   Toda salida informativa o de rastreo se centraliza mediante `Loguru`.
*   El uso de llamadas genéricas `print()` está estrictamente vetado.
*   Los logs deben categorizarse rigurosamente según criticidad: `INFO` para flujo regular del sistema, `WARNING` para eventos atípicos controlados, `ERROR`/`CRITICAL` para fallas que comprometen la integridad de datos o detienen la ejecución.

### 7.3 Ciclo de Documentación y Definición de Hecho (DoD)
*   **Ciclo de Documentación:** Cualquier alteración en la API, variables del entorno o arquitectura debe impactar atómicamente a `README.md` y a esta especificación `SPEC.md`.
*   **Definición de Hecho (DoD):** Ninguna funcionalidad se considerará completada hasta que sus pruebas unitarias en `tests/unit/` alcancen una cobertura aceptable y pasen exitosamente.

---

## 8. RESTRICCIONES Y SEGURIDAD

*   **Aislamiento de Secretos:** La variable de configuración de mayor prioridad se define localmente en un archivo `.env.local` excluido de git. El archivo `.env.example` actúa únicamente como contrato estructural sin credenciales reales expuestas.
*   **Control de Dependencias:** El archivo `requirements.txt` y `requirements-dev.txt` definen las dependencias fijas. No se deben importar módulos adicionales sin un análisis de seguridad previo y la aprobación correspondiente.
*   **Seguridad del Sistema:** Dado que la aplicación interactúa con el sistema de archivos local y automatizaciones de navegador, todo comando en producción debe operar de manera restringida o contenedorizada.

---

## 9. CHECKLIST DE IMPLEMENTACIÓN (SDD)

### Hito 1: Infraestructura y Base de Datos
- [x] Configurar entorno inmutable con `app/config/` and `.env.example`.
- [x] Implementar el CLI de migraciones y el `ResilientBulkWriter` síncrono.
- [x] Inicializar la conexión asíncrona con `motor` en `app/database/`.

### Hito 2: Motor de Ingesta (Scraper)
- [x] Implementar el adaptador `workana.py` con Playwright + BS4.
- [x] Mapear la salida del scraping a modelos Pydantic puros.
- [x] **Gestión del ciclo de vida de la sesión:** Implementar un manejo de errores defensivo de tal manera que, si la autenticación falla o la sesión expira, la canalización se detenga de forma elegante con una instrucción clara que le pida al usuario que ejecute manualmente `extract_session.py` y lo valide a través de `test_bot_session.py` antes de reiniciar.

### Hito 3: Motor Cognitivo y Canal Operativo
- [x] Integrar `google-genai` y la carga de prompts desde plantillas `.j2`.
- [x] Implementar el bot de Telegram asíncrono con sus Circuit Breakers.
