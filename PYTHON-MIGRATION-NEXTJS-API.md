# Python Migration Analysis for Next.js API

Este documento detalla la arquitectura y el contrato de la API existente en Next.js para facilitar su migración a Python 3.11.

## 1. Esquema de la Colección `projects` en MongoDB

La colección `projects` almacena la información principal de los proyectos. A continuación se describe su esquema deducido de los tipos de la aplicación.

-   `_id`: `ObjectId` - Identificador único de MongoDB.
-   `link_hash`: `string` - Hash único generado a partir del enlace del proyecto.
-   `title`: `string` - Título del proyecto.
-   `description`: `string` - Descripción corta del proyecto.
-   `full_description`: `string` - Descripción completa y detallada del proyecto.
-   `generated_proposal`: `string` (Markdown) - Propuesta generada, opcional.
-   `status`: `string` - Estado interno del proyecto (e.g., 'BACKLOG', 'PUBLISHED').
-   `updated_at`: `string` (ISO Date) - Fecha de última actualización.
-   `scraped_at`: `string` (ISO Date) - Fecha en que fue obtenido (scraped).
-   `estimated_published_at`: `string` (ISO Date) - Fecha de publicación estimada.
-   `proposal_at`: `string` (ISO Date) - Fecha de creación de la propuesta, opcional.
-   `url`: `string` - URL original del proyecto.
-   `country`: `string` - País del cliente.
-   `payment`: `string` - Información sobre el pago (verificado, etc.).
-   `skills`: `array` of `string` - Listado de habilidades requeridas.
-   `proposal`: `object` - Objeto que contiene la propuesta detallada. Puede ser de dos tipos: `MilestoneProposal` o `StaffAugmentationProposal`.
-   `link`: `string` - Otro enlace relacionado al proyecto.
-   `budget`: `string` - Presupuesto del proyecto.
-   `strategy`: `string` - Estrategia de propuesta ('PRO', 'FLASH', 'NONE').
-   `ai_reason`: `string` - Justificación de la IA para la estrategia y puntuación.
-   `ai_score`: `number` - Puntuación asignada por la IA (de 0 a 10).
-   `proposal_status`: `string` - Estado de la propuesta (e.g., 'ready_for_proposal', 'proposal_generated').
-   `previous_status`: `string` | `null` - Estado anterior, usado cuando se rechaza una propuesta.
-   `contract_type`: `string` - Tipo de contrato ('staff_augmentation' o 'fixed').
-   `deleted_at`: `string` (ISO Date) | `null` - Para borrado lógico (soft delete).

## 2. Modelos de Datos Equivalentes en Python (Pydantic)

Se sugiere utilizar Pydantic para definir los modelos de datos en Python, lo que proporciona validación y serialización automática, ideal para frameworks como FastAPI.

```python
from typing import Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime

# Tipos literales para estados y estrategias
ProjectStatus = Literal['BACKLOG', 'DRAFT', 'READY_TO_PUBLISH', 'PUBLISHED', 'REJECTED']
ProjectStrategy = Literal['PRO', 'FLASH', 'NONE']
ContractType = Literal['staff_augmentation', 'fixed']
ProposalStatus = Literal[
    'all', 
    'proposal_generated', 
    'submited_to_workana', 
    'ready_for_proposal', 
    'discarded', 
    'rejected',
    'not_found' # Estado interno para filtrado
]

class Task(BaseModel):
    description: str
    hours_with_overhead: float

class Milestone(BaseModel):
    step: int
    name: str
    tasks: Dict[str, Task]
    hours_with_overhead: float
    subtotal: float

class MilestoneProposalSummary(BaseModel):
    total_hours: float
    total_budget: float
    delivery_time_weeks: int
    hourly_rate_applied: float

class MilestoneProposal(BaseModel):
    proposal_header: str
    milestones: List[Milestone]
    summary: MilestoneProposalSummary
    technical_pitch: str
    questions_for_client: Optional[List[str]] = None

class BudgetSummary(BaseModel):
    hourly_rate: float
    suggested_hours_per_week: int
    estimated_monthly_budget: float

class StaffAugmentationProposal(BaseModel):
    cover_letter: str
    budget_summary: BudgetSummary
    questions_for_client: Optional[List[str]] = None

# Unión de los dos tipos de propuesta
AnyProposal = Union[MilestoneProposal, StaffAugmentationProposal]

class Project(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    link_hash: str
    title: str
    description: str
    full_description: str
    generated_proposal: Optional[str] = None # Markdown
    status: ProjectStatus
    updated_at: datetime
    scraped_at: datetime
    estimated_published_at: datetime
    proposal_at: Optional[datetime] = None
    url: HttpUrl
    country: str
    payment: str
    skills: List[str]
    proposal: AnyProposal
    link: HttpUrl
    budget: str
    strategy: ProjectStrategy
    ai_reason: str
    ai_score: float
    proposal_status: str
    previous_status: Optional[str] = None
    contract_type: ContractType
    deleted_at: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            # Si se usa ObjectId de pymongo/motor
            # ObjectId: str
        }
```

## 3. Conexión a la Base de Datos

La conexión a MongoDB se gestiona de forma centralizada.

-   **Driver:** Se utiliza el driver oficial `mongodb` para Node.js.
-   **URI de Conexión:** La URI se obtiene de la variable de entorno `MONGODB_URI`. Si no está definida, la aplicación lanza un error al iniciar.
-   **Gestión de Conexión:**
    -   En entorno de **desarrollo (`development`)**, la promesa de conexión (`clientPromise`) se almacena en una variable global (`global._mongoClientPromise`). Esto evita crear una nueva conexión en cada recarga de módulo (hot-reloading), optimizando recursos.
    -   En entorno de **producción**, se crea un nuevo cliente y se establece la conexión de forma estándar.
-   **Exportación:** El módulo exporta `clientPromise`, una promesa que resuelve al cliente de MongoDB conectado, listo para ser usado en otros servicios.

**Equivalente en Python (con Motor para asincronismo):**

```python
import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI environment variable is not set.")

client = AsyncIOMotorClient(MONGODB_URI)

# Para usarlo:
# db = client[os.getenv("MONGODB_DB")]
# collection = db.projects
```

## 4. Lógica del Servicio (`projects.service.ts`)

Este servicio encapsula toda la interacción con la colección `projects`.

### `getProjects(queryOptions)`

-   **Propósito:** Obtiene una lista paginada y filtrada de proyectos.
-   **Parámetros (`queryOptions`):**
    -   `status`: `string` - Filtra por estado de la propuesta ('all', 'proposal_generated', 'discarded', 'rejected', etc.).
    -   `searchTerm`: `string` - Busca el término en los campos `title` y `description` (insensible a mayúsculas).
    -   `staffAugmentationOnly`: `boolean` - Si es `true`, filtra solo proyectos con `contract_type: 'staff_augmentation'`.
    -   `skip`: `number` - Número de documentos a omitir (paginación).
    -   `limit`: `number` - Número máximo de documentos a devolver (paginación).
-   **Lógica de Filtrado:**
    1.  **Exclusiones base:**
        -   Se excluyen siempre los proyectos con `proposal_status: 'not_found'`.
        -   Se excluyen los proyectos con borrado lógico (`deleted_at` existe).
    2.  **Filtro por `status`:**
        -   Si `status` es `'discarded'`, filtra `ai_score < 5`.
        -   Si `status` es `'rejected'`, filtra `proposal_status: 'rejected'` (ignora `ai_score`).
        -   Para cualquier otro `status` (incluido `'all'`), requiere `ai_score >= 5`.
        -   Si `status` es `'all'`, limita los `proposal_status` a `['proposal_generated', 'submited_to_workana', 'ready_for_proposal']`.
        -   Si es otro `status` específico, se usa ese valor para `proposal_status`.
    3.  **Filtro por `searchTerm`**: Usa `$regex` con opción `i` sobre `title` y `description`.
-   **Ordenamiento:**
    -   Se utiliza un pipeline de agregación para ordenar de forma descendente por:
        1.  `estimated_published_at`
        2.  `ai_score`
        3.  `updated_at` (campo calculado para manejar fechas como string o Date).
-   **Respuesta:** Devuelve un objeto `{ projects: IProject[], total: number }`, donde `total` es el conteo total de documentos que coinciden con el filtro (sin paginación).

### `getProject(id)`

-   **Propósito:** Obtiene un único proyecto por su `_id`.
-   **Parámetros:**
    -   `id`: `string` - El `_id` del proyecto en formato string.
-   **Lógica:**
    1.  Valida si el `id` es un `ObjectId` válido. Si no, devuelve `null`.
    2.  Busca en la colección `projects` un documento con el `_id` correspondiente.
    3.  Si no se encuentra, devuelve `null`.
    4.  Devuelve el documento del proyecto.

## 5. Contrato de los Endpoints de la API

### `GET /api/projects`

-   **Archivo:** `src/app/api/projects/route.ts`
-   **Método:** `GET`
-   **Parámetros de Query:**
    -   `status`: `string` (Opcional, default: 'all'). Ver valores posibles en `ProposalStatus` arriba.
    -   `searchTerm`: `string` (Opcional).
    -   `staffAugmentationOnly`: `string` ('true' o 'false', opcional).
    -   `page`: `string` (Opcional, default: '1').
    -   `limit`: `string` (Opcional, default: '10').
-   **Lógica:**
    1.  Parsea y normaliza los parámetros de la query.
    2.  Llama a `getProjects()` del servicio con las opciones construidas.
    3.  Devuelve el resultado.
-   **Respuesta Exitosa (`200 OK`):**
    ```json
    {
      "projects": [
        {
          "_id": "...",
          "title": "...",
          // ... resto de campos del proyecto
        }
      ],
      "total": 123
    }
    ```
-   **Respuesta de Error (`500 Internal Server Error`):**
    ```json
    {
      "message": "Failed to fetch projects"
    }
    ```

### `PATCH /api/projects/{id}`

-   **Archivo:** `src/app/api/projects/[id]/route.ts`
-   **Método:** `PATCH`
-   **Parámetro de Ruta:**
    -   `id`: `string` - El `_id` del proyecto a actualizar.
-   **Cuerpo de la Petición (`Request Body`):**
    -   Un objeto JSON con los campos y valores a actualizar en el documento del proyecto.
    -   Ejemplo: `{ "status": "DRAFT", "proposal": { ... } }`
-   **Lógica:**
    1.  Valida si el `id` es un `ObjectId` válido.
    2.  Usa `updateOne` con el operador `$set` para aplicar las actualizaciones.
    3.  Comprueba si un documento fue realmente encontrado y modificado.
-   **Respuesta Exitosa (`200 OK`):**
    ```json
    {
      "message": "Project updated successfully"
    }
    ```
-   **Respuestas de Error:**
    -   `400 Bad Request`: Si el `id` no es un `ObjectId` válido.
        ```json
        { "message": "Invalid ID" }
        ```
    -   `404 Not Found`: Si no se encuentra ningún proyecto con ese `id`.
        ```json
        { "message": "Project not found" }
        ```
    -   `500 Internal Server Error`: Para cualquier otro error de base de datos.
        ```json
        { "message": "Internal Server Error" }
        ```
