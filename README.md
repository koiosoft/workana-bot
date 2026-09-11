# Workana Bot — Automated Proposal Generator

---

## 📋 Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [Session & Anti-Bot](#-session--anti-bot)
- [Architecture](#-architecture)
- [Development](#-development)

---

## 🛠 Features

- **AI Provider Flexibility** — Gemini y OpenRouter via `AI_PROVIDER`.
- **Resilient Automation** — Arquitectura hexagonal, async/await.
- **Anti-bot evasion** — Exporta cookies desde Chrome real para omitir Cloudflare.
- **Test coverage** — Unitarias (`tests/unit/`) e integración (`tests/integration/`).

---

## ⚡ Quick Start

### 1. Requisitos

- Python 3.11+
- Docker & Docker Compose
- Una cuenta en [Workana](https://www.workana.com)

### 2. Configuración inicial

```bash
cp .env.example .env
# Edita .env con tus credenciales (ver sección de configuración)
# Crea .env.local para sobreescribir valores sensibles en local
```

### 3. Sesión de Workana (importante — ver abajo)

### 4. Levantar el bot

```bash
docker-compose up -d
```

---

## 🔐 Session & Anti-Bot

Workana usa **Cloudflare** para protegerse contra bots. Playwright en modo
headless es bloqueado automáticamente. Para evitar esto, el bot necesita
**cookies de una sesión real de Chrome** que ya haya pasado el challenge.

### Exportar sesión desde Chrome

Workana usa **Cloudflare**, que bloquea Playwright headless. La solución
es exportar las cookies desde Chrome real e inyectarlas al scraper.

1. Abre **Chrome normal** y ve a workana.com
2. Resuelve Cloudflare si aparece (checkbox)
3. Inicia sesión en Workana
4. Instala una extensión exportadora de cookies:
   - **"Get cookies.txt"** (recomendada) — Chrome Web Store
   - **"EditThisCookie"** (alternativa) — Chrome Web Store
5. Exporta las cookies (`.txt` o `.json`)
6. Ejecuta el script unificado:

   ```bash
   python scripts/export_session.py ~/Downloads/workana_cookies.txt
   ```

   El script detecta el formato automáticamente, convierte las cookies,
   copia al contenedor y reinicia el bot. Solo responde "s" cuando
   pregunte.

   > ⚠️ La sesión expira eventualmente. Cuando el bot deje de
   > encontrar proyectos, repite el proceso.
---

## ⚙️ Configuration

Variables principales en `.env`:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `MONGO_URI` | URI de MongoDB (Atlas o local) | — |
| `SCRAPER_SOURCE` | Origen: `workana` o `dummy` | `workana` |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram | — |
| `MY_TELEGRAM_ID` | Tu ID de Telegram | — |
| `AI_PROVIDER` | `gemini` o `openrouter` | `gemini` |
| `GEMINI_API_KEY` | API Key de Gemini | — |
| `WORKANA_PUBLICATION_FILTER` | Filtro de tiempo (`1h`, `1d`, `1w`) | `1d` |
| `WORKANA_MAX_PAGES` | Máx. páginas a scrapear | `30` |
| `WORKANA_DISABLE_BLINK_FEATURES` | Features Blink a deshabilitar | `AutomationControlled` |
| `WORKANA_USER_AGENT` | User-Agent personalizado | Chrome 123 |
| `STATE_FILE_PATH` | Ruta al archivo de sesión | `/usr/src/app/state.json` |

Ver `.env.example` para todas las variables.

---

## 🏗 Architecture

- **`app/scraper/`** — Adaptadores de scraping (Workana, dummy).
- **`app/bots/telegram/`** — Bot de Telegram (comandos, handlers).
- **`app/intelligence/`** — Evaluación de proyectos con IA.
- **`database/`** — Conexión y operaciones MongoDB.
- **`migrations/`** — Migraciones de base de datos.
- **`scripts/`** — Utilidades (extraer sesión, convertir cookies, etc.).

---

## 🔧 Development

```bash
# Entorno local (sin Docker)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -r requirements-dev.txt

# Tests
pytest

# Linter
ruff check .
```