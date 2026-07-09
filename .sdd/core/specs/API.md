# API TECHNICAL SPECIFICATION

## 1. ROUTE GROUP: AUTHENTICATION (`/api/routes/auth.py`)

### 1.1 Login Endpoint
**Method**: `POST` `/login`  
**Path**: `/auth/login`  
**Security**: OAuth2 Password Flow (Bearer Token)  

**Request Body**:
```python
class LoginForm(BaseModel):
    username: str
    password: str
```

**Response**:
- 200 OK: `{"access_token": str, "token_type": str}`
- 400 Bad Request: `{"detail": "Incorrect username or password"}`
- 401 Unauthorized: `{"detail": "Missing credentials"}`

**Validation**:
1. Username/password validation via MongoDB `admins` collection
2. Token generation using HS256 with secret key

### 1.2 Token Refresh
**Method**: `POST` `/refresh-token`  
**Path**: `/auth/refresh-token`  
**Security**: Bearer Auth (existing token)

**Request Body**:
```python
class TokenRefresh(BaseModel):
    refresh_token: str
```

**Response**:
- 200 OK: `{"access_token": str, "new_refresh_token": str}`
- 401 Unauthorized: Token validation failure

## 2. ROUTE GROUP: PROJECTS (`/api/routes/projects.py`)

### 2.1 Project Creation
**Method**: `POST`  
**Path**: `/projects`  

**Request Body**:
```python
class ProjectCreate(BaseModel):
    title: str
    description: str
    budget_min: float
    budget_max: float
    deadline: datetime
    skills_required: List[str]
```

**Validation**:
- `budget_min <= budget_max`
- `deadline` must be > current time
- `skills_required` max 10 items

**Response**:
- 201 Created: ProjectRead model
- 422 Validation Error

### 2.2 Project Search
**Method**: `GET`  
**Path**: `/projects`  
**Query Parameters**:
- `skill_filter`: Array[str]
- `status`: Optional[ProjectStatus] (enum: "open", "closed", "in_progress")
- `skip`: int, `limit`: int

**Response**:
- 200 OK: `List[ProjectRead]`

## 3. ROUTE GROUP: PROPOSALS (`/api/routes/proposals.py`)

### 3.1 Proposal Submission
**Method**: `POST`  
**Path**: `/proposals`  
**Security**: Bearer Auth

**Request Body**:
```python
class ProposalCreate(BaseModel):
    project_id: PyObjectId
    cover_letter: str
    budget: float
    timeline_days: int
    attachments: Optional[List[str]]  # S3 URLs
```

**Validation**:
- `timeline_days` must be > 0
- Budget must be within project budget range
- Requires admin authentication

**Response**:
- 201 Created: ProposalRead model
- 403 Forbidden: Unauthorized user
- 409 Conflict: Already submitted for project

## 4. GLOBAL VALIDATION RULES
1. **Error Responses**: Standard `{"detail": str, "code": int}` format
2. **Rate Limiting**: 60 requests/minute per IP address
3. **CORS**: Allowed domains configured in `[settings.CORS_ORIGINS]`

## 5. MIDDLEWARE
1. AuthenticationMiddleware (JWT validation)
2. RequestIDMiddleware (UUID tracking in headers)
3. Database session per request

## 6. ROUTE GROUP: MODELS & PROVIDERS (`/api/routes/models.py`)

### 6.1 Provider Management

**Base Path**: `/api/models/providers` (CRUD endpoints)

#### 6.1.1 Create Provider
**Method**: `POST` `/api/models/providers`
**Security**: Admin auth

**Request Body**:
```python
ProviderModel(
    key: str, 
    name: str, 
    url: str,
    is_deleted: Optional[bool] = False
)
```

**Responses**:
- 201 Created: `"inserted_id": str`
- 409 Conflict: Duplicate provider key
- 400 Bad Request: Invalid provider_key

#### 6.1.2 Update Provider
**Method**: `PUT` `/api/models/providers/{provider_key}`

**Request Body**:
```python
ProviderUpdate(
    name: Optional[str],
    url: Optional[str]
)
```

**Responses**:
- 200 OK: Updated provider object
- 404 Not Found

#### 6.1.3 Delete Provider
**Method**: `DELETE` `/api/models/providers/{provider_key}`

**Behavior**:
- Soft-deletes provider and associated models
- Sets `is_deleted: True` flag
- Returns cascade count

**Responses**:
- 200 OK: `{"cascaded_models": int}`
- 404 Not Found

### 6.2 Model Management

**Base Path**: `/api/models/` (CRUD endpoints)

#### 6.2.1 Create Model
**Method**: `POST` `/api/models`
**Security**: Admin auth

**Request Body**:
```python
ModelModel(
    model_id: str, 
    provider_key: str, 
    is_default: bool = False,
    is_premium: bool = False,
    is_deleted: Optional[bool] = False
)
```

**Validation**:
1. Provider must exist
2. Unique (model_id, provider_key) constraint

**Responses**:
- 201 Created: `"inserted_id": str`
- 409 Conflict: Duplicate model
- 400 Bad Request: Invalid provider_key

#### 6.2.2 Update Model Flags
**Method**: `PUT` `/api/models/{model_id}`

**Request Body**:
```python
ModelUpdate(
    is_default: Optional[bool],
    is_premium: Optional[bool]
)
```

**Special Logic**:
- When setting `is_default=True` for a tier:
  1. Unsets default flag on *all other models* in that tier
  2. Ensures mutual exclusion

**Responses**:
- 200 OK: Updated model object
- 404 Not Found

#### 6.2.3 Soft-Delete Model
**Method**: `DELETE` `/api/models/{model_id}`

**Behavior**:
- Retains historical data
- Sets `is_deleted: True`

**Responses**:
- 200 OK: Success message
- 404 Not Found

### 6.3 List Models
**Method**: `GET` `/api/models`

**Query Parameters**:
- `filter`: ["standard" | "premium"]

**Response**:
- Returns list of models with enriched provider metadata:
  ```json
  {
    "model_id": ..., 
    "provider_key": ..., 
    "provider_name": str, 
    "provider_url": str
  }
  ```