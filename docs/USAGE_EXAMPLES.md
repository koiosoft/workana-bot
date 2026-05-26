# 📖 Ejemplos de Uso - Contract Type Detection

## Descripción General

Este documento contiene ejemplos prácticos de cómo funciona la detección de tipo de contrato y la generación de propuestas diferenciadas.

---

## 🎯 Escenario 1: Proyecto de Staff Augmentation

### Descripción del Proyecto en Workana

```
Título: Desarrollador Python Senior para Equipo Remoto

Descripción:
Buscamos un desarrollador Python con experiencia en Django para incorporarse 
a nuestro equipo de desarrollo. El trabajo es remoto y pagaremos por hora.

Necesitamos:
- 4+ años de experiencia en Python
- Conocimiento de Django y DRF
- Disponibilidad de 20-30 horas semanales
- Trabajo a largo plazo (6+ meses)

Por favor enviar CV y portafolio.

Presupuesto: $25-35/hora
```

### Salida del Comando `/lista`

```
⭐ Score: 8/10 | 🔧 Staff Aug.
📌 Desarrollador Python Senior para Equipo Remoto
💰 $25-35/hora
📝 Cliente busca perfil Python/Django para contratación por horas. 
    Proyecto de largo plazo con disponibilidad semanal definida.
💡 Alto ajuste técnico. Stack coincide perfectamente. Cliente 
    parece serio por solicitar CV y mencionar plazo largo.
🔗 [Ver Proyecto](https://workana.com/...)
```

### Salida del Comando `/procesar`

```
⚙️ (1/3) Procesando 🔧: Desarrollador Python Senior para Equipo Remoto
🧠 (1/3) Generando propuesta IA para: Desarrollador Python Senior...
✅ (1/3) Propuesta Generada (🔧 Staff): Desarrollador Python Senior...
💰 $25/hora | 📅 ~$2000/mes
```

### Estructura de Propuesta Generada

```json
{
  "cover_letter": "Estimado Cliente,\n\nHe leído con interés su búsqueda de un Desarrollador Python Senior para incorporarse a su equipo remoto. Con más de 24 años de experiencia en arquitectura de software y desarrollo, me especializo en la construcción de sistemas escalables usando Python/Django.\n\nMi experiencia específica incluye:\n- Diseño e implementación de APIs RESTful con Django REST Framework\n- Optimización de queries y diseño de bases de datos PostgreSQL\n- Desarrollo de sistemas empresariales críticos con alta disponibilidad\n- Trabajo en equipos remotos distribuidos usando metodologías ágiles\n\nEstoy disponible para comenzar de inmediato y puedo comprometerme a 20-25 horas semanales. Me especializo en escribir código limpio, bien documentado y con cobertura de tests.\n\n¿Podríamos coordinar una llamada técnica breve para discutir los detalles específicos del proyecto y cómo puedo aportar valor a su equipo desde el primer día?\n\nQuedo atento a su respuesta.\n\nSaludos cordiales,\n[Tu Nombre]",
  
  "budget_summary": {
    "hourly_rate": 25,
    "suggested_hours_per_week": 20,
    "estimated_monthly_budget": 2000
  },
  
  "questions_for_client": [
    "¿Cuál es la duración estimada inicial del proyecto o rol?",
    "¿Cómo está compuesto el equipo técnico actual y qué metodología de trabajo utilizan (Scrum, Kanban, etc.)?",
    "¿Cuáles son las tecnologías específicas del stack que estaré utilizando (versiones de Django, bases de datos, servicios cloud)?",
    "¿Existe documentación técnica del proyecto o habrá un período de onboarding?"
  ]
}
```

---

## 🎯 Escenario 2: Proyecto Llave en Mano

### Descripción del Proyecto en Workana

```
Título: Desarrollo de Sistema de Gestión de Inventario

Descripción:
Necesitamos desarrollar desde cero un sistema web de gestión de inventario 
para nuestra empresa de distribución.

Funcionalidades requeridas:
- Módulo de productos con categorías y subcategorías
- Control de stock en tiempo real
- Generación de reportes (entradas/salidas/existencias)
- Dashboard con gráficas de análisis
- Sistema de usuarios con roles (Admin, Operador, Visualizador)
- Integración con API de nuestro proveedor de facturación

Entregables:
- Código fuente completo
- Base de datos diseñada y documentada
- Manual de usuario
- Deployment en nuestro servidor

Tecnologías preferidas: Python/Django + React

Presupuesto: $3000-5000
Plazo: 6-8 semanas
```

### Salida del Comando `/lista`

```
⭐ Score: 9/10 | 📦 Proyecto
📌 Desarrollo de Sistema de Gestión de Inventario
💰 $3000-5000
📝 Proyecto completo desde cero: Sistema de inventario con dashboard, 
    reportes, roles y API de integración. Stack: Python/Django + React.
💡 Excelente ajuste técnico. Proyecto bien definido con entregables 
    claros. Requiere arquitectura robusta y diseño de BD relacional.
🔗 [Ver Proyecto](https://workana.com/...)
```

### Salida del Comando `/procesar`

```
⚙️ (1/3) Procesando 📦: Desarrollo de Sistema de Gestión de Inventario
🧠 (1/3) Generando propuesta IA para: Desarrollo de Sistema...
✅ (1/3) Propuesta Generada (📦 Proyecto): Desarrollo de Sistema...
💰 Presupuesto: $4500 | ⏱️ Horas: 180h
```

### Estructura de Propuesta Generada

```json
{
  "proposal_header": "Estimado Cliente,\n\nComo Arquitecto de Software con más de 24 años de experiencia en el diseño y despliegue de sistemas críticos empresariales, he analizado su requerimiento de Sistema de Gestión de Inventario y comprendo perfectamente la importancia de contar con una herramienta robusta, escalable y de fácil mantenimiento.\n\nSu proyecto requiere no solo desarrollo de funcionalidades, sino un diseño arquitectónico sólido que garantice la integridad de datos, rendimiento en operaciones concurrentes y una experiencia de usuario fluida. Mi enfoque consultivo me permite anticipar puntos críticos como la sincronización de stock en tiempo real y la integración segura con APIs externas.",

  "milestones": [
    {
      "step": 1,
      "name": "Discovery, Arquitectura Base y Contratos de API",
      "tasks": {
        "Modelado E-R de Base de Datos PostgreSQL": {
          "description": "Diseño normalizado incluyendo productos, categorías, movimientos de stock, usuarios y roles. Control de concurrencia y triggers para auditoría.",
          "hours_with_overhead": 12
        },
        "Definición de Contratos de API REST (OpenAPI/Swagger)": {
          "description": "Especificación completa de endpoints, validaciones, códigos de respuesta y manejo de errores.",
          "hours_with_overhead": 8
        },
        "Setup de Arquitectura Backend (Django + DRF)": {
          "description": "Configuración de proyecto, autenticación JWT, middleware de logging, dockerización inicial.",
          "hours_with_overhead": 10
        },
        "Setup de Frontend (React + TypeScript)": {
          "description": "Configuración de proyecto con Vite, estructura modular, librerías de UI (Material-UI), manejo de estado (Redux/Context).",
          "hours_with_overhead": 10
        }
      },
      "hours_with_overhead": 40,
      "subtotal": 1000.0
    },
    {
      "step": 2,
      "name": "Módulo Core: Productos y Categorías",
      "tasks": {
        "Backend: CRUDs de Productos y Categorías": {
          "description": "Endpoints con filtros, búsqueda, paginación. Validaciones de negocio (SKU único, categorías obligatorias). Tests unitarios.",
          "hours_with_overhead": 15
        },
        "Frontend: Interfaces de Gestión": {
          "description": "Formularios con validación, tablas con ordenamiento/filtrado, modales de confirmación. Componentes reutilizables.",
          "hours_with_overhead": 18
        },
        "Integración y Pruebas E2E": {
          "description": "Testing de flujos completos, validación de casos edge, ajustes de UX basados en feedback.",
          "hours_with_overhead": 7
        }
      },
      "hours_with_overhead": 40,
      "subtotal": 1000.0
    },
    {
      "step": 3,
      "name": "Módulo de Control de Stock en Tiempo Real",
      "tasks": {
        "Backend: Sistema de Movimientos de Inventario": {
          "description": "Registro de entradas/salidas, validación de stock disponible, transacciones atómicas, auditoría de cambios.",
          "hours_with_overhead": 18
        },
        "Backend: Lógica de Cálculo de Existencias": {
          "description": "Queries optimizadas con agregaciones, manejo de stock negativo, alertas de stock mínimo.",
          "hours_with_overhead": 12
        },
        "Frontend: Interfaz de Movimientos y Stock": {
          "description": "Pantallas de captura rápida, visualización de stock por producto/categoría, indicadores visuales.",
          "hours_with_overhead": 15
        }
      },
      "hours_with_overhead": 45,
      "subtotal": 1125.0
    },
    {
      "step": 4,
      "name": "Dashboard Analítico y Sistema de Reportes",
      "tasks": {
        "Backend: Endpoints de Reportes": {
          "description": "Generación de reportes en PDF/Excel, queries de análisis con filtros por fecha/categoría, caching de datos.",
          "hours_with_overhead": 15
        },
        "Frontend: Dashboard con Gráficas": {
          "description": "Implementación con Chart.js/Recharts, métricas clave (rotación, productos top, movimientos), filtros dinámicos.",
          "hours_with_overhead": 18
        },
        "Optimización de Performance": {
          "description": "Indexación de BD, lazy loading, debouncing de búsquedas, optimización de queries N+1.",
          "hours_with_overhead": 7
        }
      },
      "hours_with_overhead": 40,
      "subtotal": 1000.0
    },
    {
      "step": 5,
      "name": "Integración con API Externa y UAT Final",
      "tasks": {
        "Integración con API de Facturación": {
          "description": "Autenticación, mapeo de datos, manejo de errores de API, reintentos automáticos, logging detallado.",
          "hours_with_overhead": 12
        },
        "User Acceptance Testing (UAT)": {
          "description": "Pruebas con cliente, ajustes finales, corrección de bugs, refinamiento de UX.",
          "hours_with_overhead": 8
        },
        "Documentación y Deployment": {
          "description": "Manual de usuario, documentación técnica, Dockerfile, CI/CD con GitHub Actions, deployment en servidor.",
          "hours_with_overhead": 15
        }
      },
      "hours_with_overhead": 35,
      "subtotal": 875.0
    }
  ],

  "summary": {
    "total_hours": 200,
    "total_budget": 5000.0,
    "delivery_time_weeks": 7,
    "hourly_rate_applied": 25
  },

  "technical_pitch": "Este proyecto requiere una arquitectura sólida desde el inicio para garantizar la escalabilidad y mantenibilidad a largo plazo. Mi propuesta incluye un Hito 1 enfocado en cimientos técnicos robustos: diseño de base de datos normalizado, contratos de API bien definidos y configuración de arquitectura con mejores prácticas.\n\nLa elección de Django + PostgreSQL asegura transacciones atómicas críticas para el control de stock (evitando inconsistencias por concurrencia), mientras que React + TypeScript en el frontend garantiza una interfaz mantenible y type-safe.\n\nLa integración con su API de facturación se manejará con patrones de resiliencia (circuit breaker, reintentos) para garantizar estabilidad ante fallos externos. El deployment incluirá dockerización completa y CI/CD automatizado.\n\nEste presupuesto contempla un overhead técnico del 20% para manejo de excepciones, testing y documentación, protegiendo su inversión de desviaciones de alcance comunes en proyectos sin análisis previo.",

  "questions_for_client": [
    "¿Existe documentación de la API de facturación (endpoints, autenticación, límites de rate)?",
    "¿Cuál es el volumen estimado de productos y transacciones mensuales para dimensionar la BD?",
    "¿El servidor de deployment cuenta con Docker instalado o prefieren deployment tradicional?",
    "¿Requieren capacitación para el equipo de TI sobre el mantenimiento del sistema?"
  ]
}
```

---

## 📊 Comparación de Propuestas

### Staff Augmentation vs Proyecto Fijo

| Aspecto | Staff Augmentation | Proyecto Fijo |
|---------|-------------------|---------------|
| **Template Usado** | `proposal_staffing.j2` | `proposal.j2` |
| **Enfoque** | Presentación de perfil | Solución técnica con hitos |
| **Presupuesto** | Tarifa por hora + estimado mensual | Presupuesto total + desglose |
| **Estructura** | Cover letter + budget_summary | Header + milestones + pitch |
| **Duración** | Indefinida o largo plazo | Definida en semanas |
| **Entregables** | Horas de trabajo | Productos/funcionalidades |
| **Riesgo** | Bajo (pago por tiempo) | Medio (alcance fijo) |

---

## 🔍 Detección de Palabras Clave

### Keywords que Detectan Staff Augmentation

```
✅ "por horas"
✅ "incorporarse al equipo"
✅ "enviar CV"
✅ "contratación mensual"
✅ "soporte a largo plazo"
✅ "trabajo remoto continuo"
✅ "disponibilidad semanal"
✅ "buscamos perfil"
✅ "necesitamos programador"
```

### Keywords que Detectan Proyecto Fijo

```
✅ "llave en mano"
✅ "desarrollo completo"
✅ "proyecto desde cero"
✅ "entregables definidos"
✅ "sistema de gestión"
✅ "plataforma web"
✅ "MVP"
✅ "desarrollo de aplicación"
✅ "presupuesto fijo"
```

---

## 📈 Casos Edge

### Caso 1: Proyecto Ambiguo

**Descripción**:
```
Título: Necesito ayuda con Python

Descripción:
Tengo un proyecto que requiere conocimientos de Python.

Presupuesto: $100
```

**Resultado**:
- **contract_type**: `project_fixed` (por defecto)
- **score**: 3/10 (descripción muy ambigua)
- **strategy**: `default`

**Propuesta Generada**: Template básico con hito de Discovery extenso para clarificar alcance.

---

### Caso 2: Proyecto Mixto

**Descripción**:
```
Título: Desarrollo de API + Soporte Continuo

Descripción:
Necesito desarrollar una API REST (2-3 semanas) y luego 
brindar soporte y mantenimiento mensual por al menos 6 meses.

Presupuesto: $2000 inicial + $500/mes soporte
```

**Resultado**:
- **contract_type**: `project_fixed` (porque el componente principal es el desarrollo inicial)
- **score**: 8/10
- **strategy**: `pro`

**Propuesta Generada**: 
- Fase 1: Hitos de desarrollo (proyecto fijo)
- Nota al final: "Para la fase de soporte continuo, podemos establecer un contrato mensual de $X/hora"

---

## 💡 Tips de Uso

### Para Desarrolladores

1. **Revisar logs de detección**
   ```bash
   tail -f bot.log | grep "contract_type"
   ```

2. **Forzar re-evaluación de un proyecto**
   ```python
   # En MongoDB shell
   db.projects.updateOne(
     {link_hash: "ABC123"},
     {$set: {proposal_status: "pending"}}
   )
   ```

3. **Ver propuestas por tipo**
   ```javascript
   // Staff augmentation
   db.projects.find({
     contract_type: "staff_augmentation",
     proposal_status: "proposal_generated"
   }).pretty()
   
   // Proyectos fijos
   db.projects.find({
     contract_type: "project_fixed",
     proposal_status: "proposal_generated"
   }).pretty()
   ```

### Para QA

1. **Validar detección manual**
   - Buscar proyectos claramente de staff en Workana
   - Ejecutar `/lista`
   - Verificar que se marcan con 🔧

2. **Validar estructura de propuestas**
   - Ejecutar `/procesar`
   - Extraer JSON de MongoDB
   - Validar que tenga campos correctos según tipo

---

## 📚 Referencias Adicionales

- [Documentación Técnica Completa](CONTRACT_TYPE_FEATURE.md)
- [Guía de Tests](../tests/README.md)
- [Checklist de Deployment](../DEPLOYMENT_CHECKLIST.md)
- [Resumen de Implementación](../IMPLEMENTATION_SUMMARY.md)

---

## 🆘 Soporte

Para preguntas o problemas:
1. Revisar logs: `tail -f bot.log`
2. Ejecutar validación: `python scripts/validate_contract_type_feature.py`
3. Consultar documentación técnica
