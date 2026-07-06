# Models & Providers API Documentation

## Table of Contents
1. [Providers Endpoints](#providers-endpoints)
2. [Models Endpoints](#models-endpoints)
3. [Error Codes](#error-codes)

## Providers Endpoints

### 🆕 Create Provider
**POST** `/api/models/providers`

**Request Body (JSON):**
```json
{
  "key": "openrouter",
  "name": "OpenRouter",
  "url": "https://openrouter.ai/api/v1"
}
```

**Response 201 (Created):**
```json
{
  "_id": "6a4bfcf05aa4dce247af189b",
  "key": "openrouter",
  "name": "OpenRouter",
  "url": "https://openrouter.ai/api/v1"
}
```

**409 Conflict:** Another provider with the same `key` exists.
**422 Validation Error:** Missing required fields (`key`, `name`, `url`) or invalid format.

---

### 🔄 Update Provider
**PUT** `/api/models/providers/{provider_key}`

**Request Body (JSON):**
```json
{
  "name": "OpenRouter v2",
  "url": "https://new.url"
}
```

**Response 200 (Success):**
```json
{
  "_id": "6a4bfcf05aa4dce247af189b",
  "key": "openrouter",
  "name": "OpenRouter v2",
  "url": "https://new.url"
}
```

**404 Not Found:** Provider with specified `provider_key` doesn't exist.
**400 Bad Request:** Empty body in PUT request.

---

### 🗑️ Soft-Delete Provider
**DELETE** `/api/models/providers/{provider_key}`

**Response 200 (Success):**
```json
{
  "message": "Provider 'openrouter' soft-deleted successfully.",
  "cascaded_models": 2
}
```

**404 Not Found:** Provider with specified `provider_key` doesn't exist.

---

### 📋 List All Providers
**GET** `/api/models/providers`


**Response 200 (Success):**
```json
[
  {
    "_id": "6a4bfcf05aa4dce247af189b",
    "key": "openrouter",
    "name": "OpenRouter",
    "url": "https://openrouter.ai/api/v1"
  }
]
```


## Models Endpoints

### 🆕 Create Model
**POST** `/api/models`

**Request Body (JSON):**
```json
{
  "model_id": "gpt-4o",
  "provider_key": "openrouter",
  "is_default": true,
  "is_premium": false
}
```

**Response 201 (Created):**
```json
{
  "_id": "6a4bfcf05aa4dce247af189c",
  "model_id": "gpt-4o",
  "provider_key": "openrouter",
  "is_default": true,
  "is_premium": false
}
```

**400 Bad Request:** Provider with `provider_key` doesn't exist.
**409 Conflict:** Another model with same `(model_id + provider_key)` exists.
**422 Validation Error:** Missing required fields or invalid format.

---

### 🔄 Update Model Flags
**PUT** `/api/models/{model_id}`

**Request Body (JSON):**
```json
{
  "is_default": false,
  "is_premium": true
}
```

**Response 200 (Success):**
```json
{
  "_id": "6a4bfcf05aa4dce247af189c",
  "model_id": "gpt-4o",
  "provider_key": "openrouter",
  "is_default": false,
  "is_premium": true
}
```

**Mutual Exclusion Rule:** If `is_default` is set to `true`, it will unset `is_default` on all other models in the same tier (standard/premium).

**422 Validation Error:** Fields must be boolean.

---

### 🗑️ Soft-Delete Model
**DELETE** `/api/models/{model_id}`

**Response 200 (Success):**
```json
{
  "message": "Model 'gpt-4o' soft-deleted successfully."
}
```

**404 Not Found:** Model with specified `model_id` doesn't exist.

---

### 📋 List Models
**GET** `/api/models`

**Filter Query (Optional):**
- `?filter=standard` → Non-premium models
- `?filter=premium` → Premium models

**Response 200 (Success):**
```json
[
  {
    "_id": "6a4bfcf05aa4dce247af189c",
    "model_id": "gpt-4o",
    "provider_key": "openrouter",
    "is_default": true,
    "is_premium": false
  }
]
```


## Error Codes
| Code | Meaning | Notes |
|------|---------|-------|
| `400` | Bad Request | Invalid provider key, empty request body |
| `404` | Not Found | Provider or model does not exist |
| `409` | Conflict | Unique constraint violation |
| `422` | Validation Error | Pydantic schema requirements failed |
| `500` | Internal Server Error | DB connection errors, unexpected failures