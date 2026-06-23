# Login API Integration Tests for FastAPI

Este documento describe las pruebas de integración para los endpoints de autenticación en el backend de FastAPI.

## Estructura del Proyecto (Estado Real)

```
Workana-Bot/
├── app/
│   ├── main.py                    # Entry point (no usar)
│   ├── api/
│   │   ├── main.py               # ✅ Existe (actualizar)
│   │   └── routes/
│   │       ├── projects.py       # ✅ Existe
│   │       └── auth.py          # 🆕 NUEVO (crear)
│   ├── database/
│   │   ├── mongo.py              # ✅ Existe
│   │   ├── projects_repository.py # ✅ Existe
│   │   └── users_repository.py   # 🆕 NUEVO (crear)
│   └── services/
│       └── auth_service.py       # 🆕 NUEVO (crear)
├── tests/
│   └── integration/
│       └── test_auth.py          # 🆕 NUEVO (crear)
└── .env                          # Actualizar con AUTH_SECRET
```

## Contratos de Endpoints

### `POST /api/auth/login`

- **URL:** `POST /api/auth/login`
- **Headers:** `Content-Type: application/json`
- **Archivo:** `app/api/routes/auth.py`

**Request:**
```json
{
  "email": "admin@example.com",
  "password": "SecurePassword123!"
}
```

**Respuesta Exitosa (`200 OK`):**
```json
{
  "success": true,
  "user": {
    "name": "Test Admin",
    "email": "admin@example.com",
    "role": "admin"
  }
}
```

**Headers:**
```
Set-Cookie: auth_session=<jwt_token>; HttpOnly; Secure; SameSite=Lax
```

**Respuesta de Error (`401 Unauthorized`):**
```json
{
  "error": "Unauthorized",
  "message": "Credenciales inválidas"
}
```

---

### `POST /api/auth/logout`

- **URL:** `POST /api/auth/logout`
- **Headers:** `Content-Type: application/json`
- **Archivo:** `app/api/routes/auth.py`

**Respuesta Exitosa (`200 OK`):**
```json
{
  "success": true,
  "message": "Logout successful"
}
```

**Headers:**
```
Set-Cookie: auth_session=; HttpOnly; Secure; SameSite=Lax; Max-Age=0
```

## Pruebas de Integración

### 1. `test_login_success` - Login Exitoso

**Descripción:** Debería retornar `200` y establecer cookie `auth_session`.

```python
@pytest.mark.asyncio
async def test_login_success():
    """Test login con credenciales válidas."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@example.com",
                "password": "SecurePassword123!"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "user" in data
        assert data["user"]["email"] == "admin@example.com"
        
        # Verificar cookie
        assert "auth_session" in response.cookies
```

**Aserciones:**
- [ ] Código de estado `200`
- [ ] `success: true`
- [ ] `user` con `name`, `email`, `role`
- [ ] Header `set-cookie` con `auth_session`
- [ ] Cookie con flags `HttpOnly`, `Secure`, `SameSite=Lax`

---

### 2. `test_login_invalid_password` - Contraseña Incorrecta

**Descripción:** Debería retornar `401` con contraseña incorrecta.

```python
@pytest.mark.asyncio
async def test_login_invalid_password():
    """Test login con contraseña incorrecta."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@example.com",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
```

**Aserciones:**
- [ ] Código de estado `401`
- [ ] `error: "Unauthorized"` en cuerpo
- [ ] Mensaje no revela si email existe

---

### 3. `test_login_nonexistent_email` - Email No Existe

**Descripción:** Debería retornar `401` con email inexistente.

```python
@pytest.mark.asyncio
async def test_login_nonexistent_email():
    """Test login con email inexistente."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "SecurePassword123!"
            }
        )
        
        assert response.status_code == 401
```

**Aserciones:**
- [ ] Código de estado `401`
- [ ] Mensaje de error genérico

---

### 4. `test_login_missing_email` - Datos Faltantes

**Descripción:** Debería retornar `422` (validación de Pydantic) con email faltante.

```python
@pytest.mark.asyncio
async def test_login_missing_email():
    """Test login sin email (validación)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "password": "SecurePassword123!"
            }
        )
        
        assert response.status_code == 422
```

**Aserciones:**
- [ ] Código de estado `422` (Unprocessable Entity - validación)

---

### 5. `test_login_invalid_email_format` - Formato Email Inválido

**Descripción:** Debería retornar `422` con email malformado.

```python
@pytest.mark.asyncio
async def test_login_invalid_email_format():
    """Test login con email malformado."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "not-an-email",
                "password": "SecurePassword123!"
            }
        )
        
        assert response.status_code == 422
```

**Aserciones:**
- [ ] Código de estado `422`

---

### 6. `test_logout_success` - Logout Exitoso

**Descripción:** Debería retornar `200` y limpiar la cookie.

```python
@pytest.mark.asyncio
async def test_logout_success():
    """Test logout limpia la cookie."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/logout")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verificar cookie de logout
        assert "auth_session" in response.cookies
        cookie = response.cookies["auth_session"]
        assert cookie.max_age == 0
```

**Aserciones:**
- [ ] Código de estado `200`
- [ ] `success: true`
- [ ] `message: "Logout successful"`
- [ ] Header `set-cookie` con `Max-Age=0`

## Implementación Completa de Tests

```python
import pytest
import os
from httpx import AsyncClient, ASGITransport
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt

# Importar la app FastAPI
from app.api.main import app

# Configuración
TEST_MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://mongodb:27017")
TEST_MONGODB_DB = os.getenv("MONGODB_DB", "workana")
TEST_AUTH_SECRET = os.getenv("AUTH_SECRET", "test-secret-for-testing")


@pytest.fixture(scope="module")
async def setup_teardown():
    """Setup y teardown para las pruebas."""
    client = AsyncIOMotorClient(TEST_MONGODB_URI)
    db = client[TEST_MONGODB_DB]
    
    # Crear usuario de prueba
    password_hash = bcrypt.hashpw(
        "SecurePassword123!".encode(), 
        bcrypt.gensalt()
    ).decode()
    
    # Limpiar cualquier usuario previo
    await db.users.delete_many({"email": "admin@example.com"})
    
    # Insertar usuario de prueba
    await db.users.insert_one({
        "email": "admin@example.com",
        "passwordHash": password_hash,
        "name": "Test Admin",
        "role": "admin"
    })
    
    yield
    
    # Limpiar después de las pruebas
    await db.users.delete_many({"email": "admin@example.com"})
    await client.close()


@pytest.mark.asyncio
async def test_login_success(setup_teardown):
    """Test login con credenciales válidas."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@example.com",
                "password": "SecurePassword123!"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "user" in data
        assert data["user"]["email"] == "admin@example.com"
        assert data["user"]["name"] == "Test Admin"
        assert data["user"]["role"] == "admin"
        
        # Verificar cookie
        assert "auth_session" in response.cookies


@pytest.mark.asyncio
async def test_login_invalid_password(setup_teardown):
    """Test login con contraseña incorrecta."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "admin@example.com",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "error" in data


@pytest.mark.asyncio
async def test_login_nonexistent_email(setup_teardown):
    """Test login con email inexistente."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "SecurePassword123!"
            }
        )
        
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_missing_email(setup_teardown):
    """Test login sin email (validación Pydantic)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "password": "SecurePassword123!"
            }
        )
        
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_invalid_email_format(setup_teardown):
    """Test login con email malformado."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "not-an-email",
                "password": "SecurePassword123!"
            }
        )
        
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_logout_success(setup_teardown):
    """Test logout limpia la cookie."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/logout")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Logout successful"
        
        # Verificar cookie de logout
        assert "auth_session" in response.cookies
        cookie = response.cookies["auth_session"]
        assert cookie.max_age == 0
```

## Ejecución de Pruebas

```bash
# Desde el directorio Workana-Bot
cd /Volumes/ExtDrive/Home/rzavala/Documents/Projects/Koiosoft/Workana-Bot

# Ejecutar pruebas
pytest tests/integration/test_auth.py -v

# Con coverage
pytest tests/integration/test_auth.py --cov=app.api.routes.auth --cov-report=html

# Ejecutar en contenedor Docker
docker exec workana_api pytest tests/integration/test_auth.py -v
```

## Resumen de Implementación

| Tarea | Archivo | Estado |
|-------|---------|--------|
| Crear repositorio de usuarios | `app/database/users_repository.py` | 🆕 NUEVO |
| Crear servicio de auth | `app/services/auth_service.py` | 🆕 NUEVO |
| Crear router de auth | `app/api/routes/auth.py` | 🆕 NUEVO |
| Actualizar main.py | `app/api/main.py` | 🆕 ACTUALIZAR |
| Crear tests | `tests/integration/test_auth.py` | 🆕 NUEVO |
| Agregar AUTH_SECRET | `.env` | 🆕 ACTUALIZAR |
