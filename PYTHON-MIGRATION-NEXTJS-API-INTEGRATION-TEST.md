# Migración de Pruebas de Integración de Next.js a Python

Este documento describe las pruebas de integración existentes en el codebase de Next.js. El objetivo es replicar estas pruebas en el nuevo backend de Python para asegurar la paridad funcional y minimizar la fricción durante la migración.

## Autenticación (`tests/integration/auth.test.ts`)

Estas pruebas cubren los endpoints de login y logout.

### Setup y Teardown

- **Antes de todas las pruebas (`beforeAll`)**:
  - Se conecta a la base de datos MongoDB.
  - Crea un usuario de prueba en la colección `users` con un email (`admin@example.com`) y una contraseña hasheada (`SecurePassword123!`).

- **Después de todas las pruebas (`afterAll`)**:
  - Elimina el usuario de prueba de la base de datos.
  - Cierra la conexión a MongoDB.

### Pruebas

#### 1. `POST /api/auth/login`

- **Caso de éxito**:
  - **Descripción**: Debería retornar un estado `200` y establecer una cookie `auth_session` de tipo `httpOnly` con credenciales válidas.
  - **Payload**: `{ "email": "admin@example.com", "password": "SecurePassword123!" }`
  - **Aserciones**:
    - El código de estado de la respuesta es `200`.
    - La cabecera `set-cookie` está definida.
    - La cookie `auth_session` está presente en la cabecera y es `HttpOnly`.

- **Caso de fallo**:
  - **Descripción**: Debería retornar un estado `401 Unauthorized` con credenciales inválidas.
  - **Payload**: `{ "email": "invalid@example.com", "password": "wrong" }`
  - **Aserciones**:
    - El código de estado de la respuesta es `401`.

#### 2. `POST /api/auth/logout`

- **Caso de éxito**:
  - **Descripción**: Debería retornar un estado `200` y limpiar la cookie `auth_session`.
  - **Aserciones**:
    - El código de estado de la respuesta es `200`.
    - La cabecera `set-cookie` indica que la cookie `auth_session` ha expirado (e.g., `Max-Age=0` o fecha de expiración en el pasado).

## Proyectos (`tests/integration/projects.test.ts`)

Estas pruebas cubren los endpoints para obtener y actualizar proyectos.

### Setup y Teardown

- **Antes de todas las pruebas (`beforeAll`)**:
  - Se conecta a la base de datos MongoDB.
  - Crea un proyecto de prueba en la colección `projects` con `title` y `proposal_status`.
  - Almacena el ID del proyecto creado para usarlo en las pruebas.

- **Después de todas las pruebas (`afterAll`)**:
  - Elimina el proyecto de prueba de la base de datos.
  - Cierra la conexión a MongoDB.

### Pruebas

#### 1. `GET /api/projects`

- **Caso de éxito (estructura)**:
  - **Descripción**: Debería retornar un estado `200` y una lista de proyectos con una estructura válida.
  - **Query Params**: `page=1`, `limit=10`
  - **Aserciones**:
    - El código de estado de la respuesta es `200`.
    - El cuerpo de la respuesta contiene las propiedades `projects` (un array) y `total` (un número).

- **Caso de éxito (filtros)**:
  - **Descripción**: Debería permitir filtrar proyectos por estado, `staffAugmentationOnly` y término de búsqueda.
  - **Query Params**: `status=proposal_generated`, `staffAugmentationOnly=true`, `searchTerm=test`
  - **Aserciones**:
    - El código de estado de la respuesta es `200`.
    - El cuerpo de la respuesta contiene la propiedad `projects`.

#### 2. `PATCH /api/projects/[id]`

- **Caso de éxito**:
  - **Descripción**: Debería retornar un estado `200` y actualizar los campos del proyecto con una solicitud válida.
  - **Payload**: `{ "proposal_status": "proposal_generated", "title": "Updated Project Title" }`
  - **Aserciones**:
    - El código de estado de la respuesta es `200`.
    - El cuerpo de la respuesta contiene un mensaje de éxito: `Project updated successfully`.

- **Caso de fallo (ID inválido)**:
  - **Descripción**: Debería retornar un estado `400` si el formato del ID del proyecto es inválido.
  - **URL**: `/api/projects/invalid_id_format`
  - **Aserciones**:
    - El código de estado de la respuesta es `400`.
