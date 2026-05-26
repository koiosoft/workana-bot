# Feature: Contract Type Detection & Differentiated Proposals

## 📋 Descripción General

Esta funcionalidad permite al sistema detectar automáticamente el tipo de contrato de cada proyecto de Workana y generar propuestas diferenciadas según la modalidad:

- **🔧 Staff Augmentation**: Proyectos que buscan un perfil de programador para contratación por horas/días (outsourcing de personal)
- **📦 Project Fixed**: Proyectos llave en mano con entregables definidos

## 🎯 Objetivo

Optimizar la tasa de conversión de propuestas al adaptar el enfoque comercial según las expectativas reales del cliente.

## 🏗️ Arquitectura de la Implementación

### 1. **Detección del Tipo de Contrato (Fase de Evaluación)**

**Archivo**: `app/intelligence/prompts/evaluation.j2`

La IA analiza la semántica de la descripción del proyecto durante el comando `/lista` y asigna uno de los siguientes valores:

```
"contract_type": "project_fixed" | "staff_augmentation"
```

**Criterios de detección**:
- `staff_augmentation`: Si el cliente busca "pago por horas", "incorporarse al equipo", "enviar CV", "soporte a largo plazo", etc.
- `project_fixed`: Si el cliente busca "producto", "entregables definidos", "proyecto llave en mano", etc.

### 2. **Almacenamiento en Base de Datos**

**Archivo**: `app/database/projects_repository.py`

Se agregó el campo `contract_type` a la actualización de análisis:

```python
async def update_project_analysis(
    self, 
    link_hash: str, 
    score: int, 
    reason: str, 
    strategy: str = "none", 
    status: str = "analyzed", 
    ai_summary: str = "No summary available",
    contract_type: str = "project_fixed"  # ✅ NUEVO CAMPO
) -> bool:
```

### 3. **Extracción y Propagación del Campo**

**Archivo**: `app/bots/telegram/handlers.py`

En la función `fetch_projects()`:

```python
contract_type = eval_data.get("contract_type", "project_fixed")

await projects_repository.update_project_analysis(
    link_hash=project["link_hash"], 
    score=score, 
    reason=eval_data.get("reason", 'Sin razón especificada.'),
    strategy=strategy,
    status="analyzed",
    ai_summary=summary,
    contract_type=contract_type  # ✅ Se guarda en DB
)
```

### 4. **Recuperación del Campo para Generación de Propuestas**

En `get_projects_for_deep_analysis()` se proyecta el campo `contract_type`:

```python
cursor = self.collection.find({...}, {
    "_id": 0,
    "title": 1,
    "contract_type": 1,  # ✅ Se recupera
    ...
})
```

### 5. **Selección de Template Dinámico**

**Archivo**: `app/intelligence/adapters/gemini.py`

En el método `generate_proposal()`:

```python
contract_type = project.get("contract_type", "project_fixed")

# Seleccionamos el template según el tipo de contrato
template_name = "proposal_staffing.j2" if contract_type == "staff_augmentation" else "proposal.j2"

prompt = self._render_prompt(
    template_name,
    my_profile_skills=my_skills,
    hourly_rate=hourly_rate,
    project_payload_json=json.dumps(project_payload, indent=2)
)
```

### 6. **Templates de Propuesta**

#### 📦 `proposal.j2` - Proyectos Llave en Mano
Genera propuestas con:
- Hitos estructurados
- Desglose de tareas técnicas
- Presupuesto total y horas estimadas
- Enfoque en arquitectura y entregables

#### 🔧 `proposal_staffing.j2` - Staff Augmentation
Genera propuestas con:
- Carta de presentación del perfil profesional
- Tarifa por hora
- Sugerencia de paquete de horas semanales/mensuales
- Enfoque en habilidades y disponibilidad

## 📊 Flujo de Datos

```
1. /lista (Scraping)
   ↓
2. IA Evalúa → Detecta contract_type
   ↓
3. Se guarda en MongoDB con contract_type
   ↓
4. /procesar (Generación de Propuesta)
   ↓
5. Se recupera contract_type de MongoDB
   ↓
6. Se selecciona template apropiado
   ↓
7. IA genera propuesta según modalidad
   ↓
8. Se guarda propuesta en MongoDB
```

## 🎨 Mejoras en la UI de Telegram

### Comando `/lista`
Ahora muestra el tipo de contrato con emojis:

```
⭐ Score: 8/10 | 🔧 Staff Aug.
📌 Desarrollador Python Senior para equipo remoto
💰 $20-30/hora
...

⭐ Score: 9/10 | 📦 Proyecto
📌 Sistema de gestión de inventario desde cero
💰 $2000-3000
...
```

### Comando `/procesar`
Muestra información diferenciada:

**Staff Augmentation:**
```
✅ (1/5) Propuesta Generada (🔧 Staff): Desarrollador React
💰 $25/hora | 📅 ~$2000/mes
```

**Proyecto Llave en Mano:**
```
✅ (1/5) Propuesta Generada (📦 Proyecto): Sistema E-commerce
💰 Presupuesto: $4500 | ⏱️ Horas: 180h
```

## 🗄️ Migración de Base de Datos

**Archivo**: `migrations/scripts/v20260523_01_add_contract_type_index.py`

Se creó una migración que:
1. Agrega un índice en el campo `contract_type` para mejorar el rendimiento de queries
2. Establece `"project_fixed"` como valor por defecto para documentos existentes

Para ejecutar la migración:

```bash
python migrations/main.py
```

## 🧪 Testing

### Casos de Prueba Recomendados

1. **Proyecto con descripción ambigua**: Verificar que la IA asigna un tipo por defecto
2. **Proyecto que menciona "busco programador por horas"**: Debe detectar `staff_augmentation`
3. **Proyecto que menciona "desarrollo de plataforma completa"**: Debe detectar `project_fixed`
4. **Generación de propuesta para staff_augmentation**: Validar estructura de salida
5. **Generación de propuesta para project_fixed**: Validar hitos y presupuesto

## 📝 Campos de Propuesta Generados

### Para `staff_augmentation`:
```json
{
  "cover_letter": "Texto de presentación profesional",
  "budget_summary": {
    "hourly_rate": 25,
    "suggested_hours_per_week": 20,
    "estimated_monthly_budget": 2000
  },
  "questions_for_client": [...]
}
```

### Para `project_fixed`:
```json
{
  "proposal_header": "Saludo y validación",
  "milestones": [...],
  "summary": {
    "total_hours": 180,
    "total_budget": 4500,
    "delivery_time_weeks": 8,
    "hourly_rate_applied": 25
  },
  "technical_pitch": "Argumentación técnica",
  "questions_for_client": [...]
}
```

## 🔄 Retrocompatibilidad

- Proyectos existentes sin `contract_type` se marcan automáticamente como `"project_fixed"` por la migración
- El valor por defecto en código también es `"project_fixed"`
- No se requiere re-scrapear proyectos antiguos

## 🚀 Próximos Pasos Sugeridos

1. **Métricas**: Agregar tracking de tasa de conversión por tipo de contrato
2. **A/B Testing**: Experimentar con diferentes estilos de propuesta
3. **ML Fine-tuning**: Entrenar la IA con feedback de propuestas aceptadas/rechazadas
4. **Dashboard**: Visualización de distribución de tipos de contrato en proyectos

## 📚 Referencias

- Template de evaluación: `app/intelligence/prompts/evaluation.j2`
- Template de propuesta fixed: `app/intelligence/prompts/proposal.j2`
- Template de propuesta staffing: `app/intelligence/prompts/proposal_staffing.j2`
- Repositorio de proyectos: `app/database/projects_repository.py`
- Handler de Telegram: `app/bots/telegram/handlers.py`
- Adaptador de IA: `app/intelligence/adapters/gemini.py`
