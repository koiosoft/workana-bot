# Login API Migration Plan for FastAPI

Este documento detalla la implementación del endpoint de autenticación `POST /api/auth/login` en FastAPI.

## Estructura Actual del Proyecto

```
Workana-Bot/
├── app/
│   ├── main.py                    # Punto de entrada de FastAPI
│   ├── database/
│   │   ├── mongo.py             # ✅ Existe
│   │   └── projects_repository.py # ✅ Existe
│   └── api/
│       ├── main.py               # Punto de entrada de la API
│       └── routes/
│           └── projects.py        # ✅ Existe (endpoints de proyectos)
│
├── database/
│   └── connection.py            # ✅ Existe
│
├── tests/
│   └── integration/
│       └── test_auth.py         # ❌ NO EXISTE
```

## Archivos que DEBEN ser Creados

| Archivo | Descripción |
|---------|-------------|
| `app/api/routes/auth.py` | Endpoints de autenticación (NUEVO) |
| `app/services/auth_service.py` | Lógica de negocio (NUEVO) |
| `app/database/users_repository.py` | Acceso a datos de usuarios (NUEVO) |

## 1. Modelo de Datos en Python (Pydantic)

```python
from pydantic import BaseModel, EmailStr
from typing import Optional

class LoginRequest(BaseModel):
    """Request model for user login."""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """Response model for user data in login success."""
    name: str
    email: EmailStr
    role: str = "user"

class LoginSuccessResponse(BaseModel):
    """Response model for successful login."""
    success: bool = True
    user: UserResponse

class LogoutResponse(BaseModel):
    """Response model for successful logout."""
    success: bool = True
    message: str = "Logout successful"

class ErrorResponse(BaseModel):
    """Response model for authentication errors."""
    error: str = "Unauthorized"
    message: str
```

## 2. Conexión a la Base de Datos

Usar el patrón existente de `app.database.mongo`:

```python
from app.database.mongo import get_database

db = get_database()
users_collection = db.users
```

## 3. Repositorio de Usuarios (NUEVO)

**Archivo:** `app/database/users_repository.py`

```python
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
import bcrypt

class UsersRepository:
    def __init__(self, db: AsyncIOMotorDatabase = None):
        self.db = db or get_database()
        self.collection = self.db.users
    
    async def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Obtener usuario por email (case-insensitive)."""
        return await self.collection.find_one(
            {"email": email.lower()}
        )
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hashear contraseña con bcrypt."""
        return bcrypt.hashpw(
            password.encode(), 
            bcrypt.gensalt()
        ).decode()
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verificar contraseña contra hash."""
        return bcrypt.checkpw(
            plain_password.encode(), 
            hashed_password.encode()
        )
```

## 4. Servicio de Autenticación (NUEVO)

**Archivo:** `app/services/auth_service.py`

```python
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from jose import JWTError, jwt
from app.database.users_repository import UsersRepository

class AuthResult:
    def __init__(self, success: bool, user: Optional[Dict] = None, 
                 token: Optional[str] = None, message: Optional[str] = None):
        self.success = success
        self.user = user
        self.token = token
        self.message = message

class AuthService:
    def __init__(self, users_repo: UsersRepository = None):
        self.users_repo = users_repo or UsersRepository()
    
    async def authenticate(self, email: str, password: str) -> AuthResult:
        """Autenticar usuario con email y contraseña."""
        user = await self.users_repo.get_by_email(email)
        
        if not user:
            return AuthResult(success=False, message="Credenciales inválidas")
        
        if not self.users_repo.verify_password(password, user["passwordHash"]):
            return AuthResult(success=False, message="Credenciales inválidas")
        
        token = self.create_access_token(user)
        return AuthResult(success=True, user=user, token=token)
    
    @staticmethod
    def create_access_token(user: Dict) -> str:
        """Crear JWT token."""
        payload = {
            "sub": str(user["_id"]),
            "email": user["email"],
            "name": user["name"],
            "role": user.get("role", "user"),
            "exp": datetime.utcnow() + timedelta(days=1)
        }
        return jwt.encode(payload, AUTH_SECRET, algorithm="HS256")
```

## 5. Router de Autenticación (NUEVO)

**Archivo:** `app/api/routes/auth.py`

```python
from fastapi import APIRouter, HTTPException, Response, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.services.auth_service import AuthService, AuthResult

router = APIRouter(prefix="/api/auth", tags=["authentication"])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginSuccessResponse(BaseModel):
    success: bool = True
    user: dict

class LogoutResponse(BaseModel):
    success: bool = True
    message: str = "Logout successful"

@router.post("/login", response_model=LoginSuccessResponse)
async def login(request: LoginRequest, response: Response):
    """Autenticar usuario y establecer cookie HttpOnly."""
    auth_service = AuthService()
    result = await auth_service.authenticate(request.email, request.password)
    
    if not result.success:
        raise HTTPException(status_code=401, detail={
            "error": "Unauthorized",
            "message": result.message
        })
    
    # Establecer cookie HttpOnly
    response.set_cookie(
        key="auth_session",
        value=result.token,
        httponly=True,
        secure=True,
        samesite="lax"
    )
    
    return LoginSuccessResponse(
        success=True,
        user={
            "name": result.user["name"],
            "email": result.user["email"],
            "role": result.user.get("role", "user")
        }
    )

@router.post("/logout", response_model=LogoutResponse)
async def logout(response: Response):
    """Cerrar sesión y limpiar cookie."""
    response.delete_cookie(
        key="auth_session",
        httponly=True,
        secure=True,
        samesite="lax"
    )
    return LogoutResponse(success=True, message="Logout successful")
```

## 6. Actualizar `app/api/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database.mongo import connect_to_mongo, close_mongo_connection
from app.api.routes.projects import router as projects_router
from app.api.routes.auth import router as auth_router  # NUEVO

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()

app = FastAPI(title="Workana Bot API", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas
app.include_router(projects_router)
app.include_router(auth_router)  # NUEVO
```

## 7. Variables de Entorno Requeridas

```bash
# En .env
MONGODB_URI=mongodb://mongodb:27017
MONGODB_DB=workana
AUTH_SECRET=tu-secret-jwt-aqui  # NUEVO
```

## 8. Dependencias Necesarias

```python
# requirements.txt (verificar)
python-jose[cryptography]  # Para JWT
bcrypt                    # Para hashing de contraseñas (ya instalado)
motor                     # Cliente async MongoDB (ya instalado)
```

## 9. Estructura Final del Proyecto

```
Workana-Bot/
├── app/
│   ├── main.py                    # Entry point (no usar)
│   ├── api/
│   │   ├── main.py               # ✅ Actualizar para incluir auth
│   │   └── routes/
│   │       ├── projects.py       # ✅ Existe
│   │       └── auth.py           # 🆕 NUEVO
│   ├── database/
│   │   ├── mongo.py              # ✅ Existe
│   │   ├── projects_repository.py # ✅ Existe
│   │   └── users_repository.py   # 🆕 NUEVO
│   └── services/
│       ├── auth_service.py       # 🆕 NUEVO
│       └── projects_service.py   # (?) Existe
│
├── database/
│   └── connection.py             # ✅ Existe
│
├── tests/
│   └── integration/
│       └── test_auth.py          # 🆕 NUEVO
```

## 10. Implementación Paso a Paso

### Paso 1: Crear `app/database/users_repository.py`
Repositorio para acceso a usuarios en MongoDB.

### Paso 2: Crear `app/services/auth_service.py`
Lógica de negocio: authenticate(), create_access_token().

### Paso 3: Crear `app/api/routes/auth.py`
Endpoints: POST /api/auth/login, POST /api/auth/logout.

### Paso 4: Actualizar `app/api/main.py`
Importar y registrar el router de auth.

### Paso 5: Agregar variable AUTH_SECRET en `.env`

### Paso 6: Crear `tests/integration/test_auth.py`
Pruebas de integración.
