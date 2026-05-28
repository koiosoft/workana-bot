# 🧪 Tests

## Estructura

```
tests/
├── unit/                    # Tests unitarios (con mocks)
│   └── test_contract_type_detection.py
├── integration/             # Tests de integración (con servicios reales)
│   └── test_contract_type_integration.py
└── README.md
```

## Instalación

```bash
pip install -r requirements-dev.txt
```

## Ejecución

### Configurar el entorno
```bash
# Activar el entorno virtual
source venv/bin/activate

# Configurar PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Todos los tests
```bash
pytest tests/ -v
```

### Solo tests unitarios (rápidos, sin servicios externos)
```bash
pytest tests/unit/ -v
```

### Test específico
```bash
pytest tests/unit/test_error_handling.py -v

# O solo una prueba específica
pytest tests/unit/test_error_handling.py::TestProcessProjectsErrorHandling::test_retries_on_gemini_server_error_and_succeeds -v
```

### Solo tests de integración (requieren MongoDB)
```bash
pytest tests/integration/ -v
```

### Con logs detallados
```bash
pytest tests/unit/test_error_handling.py -v --log-cli-level=INFO
```

### Con cobertura
```bash
pytest tests/ --cov=app --cov-report=html
```

## Tests Unitarios (`tests/unit/`)

**Características:**
- ✅ Rápidos (usan mocks)
- ✅ No requieren servicios externos
- ✅ Prueban componentes aislados

**Qué se prueba:**
- Detección de keywords de contrato
- Selección de template según `contract_type`
- Lógica de guardado en repositorio (mockeado)
- Estructura de propuestas
- Formato de mensajes de Telegram
- **Manejo de errores y reintentos** (`test_error_handling.py`):
  - Reintentos automáticos en errores retriables (API 503, timeouts, etc.)
  - Circuit breaker tras múltiples fallas consecutivas
  - Liberación correcta del semáforo
  - Notificaciones apropiadas a Telegram

## Tests de Integración (`tests/integration/`)

**Características:**
- ⚠️ Requieren MongoDB configurado
- ⚠️ Validan integración real de componentes
- ⚠️ Más lentos que tests unitarios

**Qué se prueba:**
- Existencia de archivos del feature
- Código correcto en componentes
- Templates con estructura adecuada
- Índice de MongoDB creado
- Datos reales con `contract_type`

**Nota:** Si `MONGODB_URI` no está configurado, estos tests se saltarán automáticamente.
