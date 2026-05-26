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

### Todos los tests
```bash
pytest tests/ -v
```

### Solo tests unitarios (rápidos, sin servicios externos)
```bash
pytest tests/unit/ -v
```

### Solo tests de integración (requieren MongoDB)
```bash
pytest tests/integration/ -v
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
