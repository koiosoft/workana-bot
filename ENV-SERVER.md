# ENV-SERVER — Guía de despliegue en el servidor Ubuntu

> Documento operativo: qué copiar y ejecutar en el servidor para levantar
> **backend** (Workana-Bot) + **frontend** (Workana-Dashboard) desde `stable`,
> con Cloudflare sirviendo `workana.koiosoft.com`.

---

## 0. Estructura objetivo en el servidor

```
~/servicios/
├── backend/     → Workana-Bot (bot Telegram + API :8000)   — INTERNO
└── frontend/    → Workana-Dashboard (Next.js :3000)        — expuesto por Cloudflare
                    ▲
                    └── workana.koiosoft.com
```

**Repos GitHub:**
- backend  → `koiosoft.github.com:koiosoft/workana-bot.git`
- frontend → `koiosoft.github.com:koiosoft/workana-bot-dashboard.git`

**Topología:**
- Red Docker compartida: **`workana_net`** (nombre FIJO). La CREA el backend.
- El backend expone `api:8000` en esa red; el frontend lo consume como `http://api:8000`.
- Solo el **frontend** se expone a internet, vía túnel Cloudflare.
- Producción usa **MongoDB Atlas** (no mongo local).

---

## 1. Red compartida

**NO se crea a mano.** La crea automáticamente el **backend** al levantarse
(su `docker-compose.prod.yml` la define con `name: workana_net`). El frontend
la consume como `external` → por eso el **backend debe arrancar primero**.

```bash
# (no ejecutar: la crea el backend)
# Si necesitas recrearla manualmente:
#   docker network create workana_net
```

---

## 2. Backend — `.env` (en `~/servicios/backend/.env`)

Copia `.env.prod.example` → `.env` y rellena con los valores reales:

```dotenv
# --- Scraper ---
SCRAPER_SOURCE=workana

# --- Telegram ---
TELEGRAM_BOT_TOKEN=<TOKEN_REAL>
MY_TELEGRAM_ID=<ID_REAL>

# --- IA (una de las dos) ---
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=<REAL>
# GEMINI_API_KEY=<REAL>

# --- Base de datos: ATLAS ---
MONGO_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/
MONGO_DB_NAME=workana_bot
# (solo si usas mongo local del compose; en prod con Atlas no aplica)
MONGO_USER=admin
MONGO_PASS=<REAL>

# --- Auth / Entorno ---
ENVIRONMENT=production
AUTH_SECRET=<CADENA_ALEATORIA_32+>
AUTH_JWT_ALGORITHM=HS256
AUTH_TOKEN_EXPIRE_HOURS=24

# --- Workana (sesion) ---
WORKANA_USE_SESSION=false
STATE_FILE_PATH=/usr/src/app/state.json

# --- Tarifas ---
HOURLY_RATE_PROJECT_FIXED=18
HOURLY_RATE_STAFF_AUGMENTATION=18
POST_DISCOVERY_HOURLY_RATE=18

# --- Limites de negocio ---
MIN_SCORE_FOR_AUTO_SEND=90
CONNECTS_AVAILABLE=50
MAX_PROJECT_DAYS=2
```

> **Nota:** el backend usa `MONGO_URI` (así lo lee `app/config/database.py`).

---

## 3. Frontend — `.env` (en `~/servicios/frontend/.env`)

Copia `.env.prod.example` → `.env` y rellena:

```dotenv
# --- Next.js ---
NODE_ENV=production
PORT=3000
HOSTNAME=0.0.0.0

# --- API del backend (red Docker interna) ---
NEXT_PUBLIC_WORKANA_PUBLIC_API_URL=http://api:8000

# --- Cloudflare Tunnel (workana.koiosoft.com) ---
TUNNEL_TOKEN=<TOKEN_DEL_TUNEL>
```

> **Nota:** el frontend **NO usa Mongo** (todo va por la API).
> `MONGODB_URI` / `MONGODB_DB` / `AUTH_SECRET` en `.env.prod.example` son **LEGACY**
> (solo los usan scripts sueltos `seed-user`/`change-password`). No son necesarias
> para arrancar. Pueden dejarse vacías u omitirse.

### Token del túnel Cloudflare

```
TUNNEL_TOKEN=eyJhIjoiZDI0NjVjMmM2YzgzOGM3NmY4NzA4ZGM3ZGNhMGMwMDYiLCJzIjoiR0ViV0J3OFJWMGhwNm9icFBGZXI0c0xWTW02QWxsUXl4WGtBVWVkMVlIdz0iLCJ0IjoiMzgzNDA1NDEtYWRkMS00MTkyLTg1NDUtNDkzMGJlZDNkMTRjIn0=
```

Túnel: **`38340541-add1-4192-8545-4930bed3d14c`** → `workana.koiosoft.com` → `http://dashboard:3000`.

> ⚠️ **El túnel solo puede correr en UN lugar a la vez.** El de la máquina de
> desarrollo debe estar **apagado** antes de levantar el del servidor
> (`docker compose down tunnel` en la máquina local).
> ⚠️ Este token está expuesto en el `docker-compose.yml` histórico (git).
> Recomendado **rotarlo** en Cloudflare y usar el nuevo.

---

## 4. Comandos de despliegue

### 4.1 Backend (PRIMERO — crea `api:8000`)

```bash
mkdir -p ~/servicios && cd ~/servicios
git clone koiosoft.github.com:koiosoft/workana-bot.git backend
cd backend
git checkout stable
cp .env.prod.example .env
nano .env                                   # rellenar (seccion 2)
./scripts/devops/check_prod.sh              # debe dar ✅
./scripts/devops/deploy_prod.sh
```

### 4.2 Frontend (DESPUÉS)

```bash
cd ~/servicios
git clone koiosoft.github.com:koiosoft/workana-bot-dashboard.git frontend
cd frontend
git checkout stable
cp .env.prod.example .env
nano .env                                   # rellenar (seccion 3)
./scripts/devops/check_prod.sh              # debe dar ✅
./scripts/devops/deploy_prod.sh
```

### 4.3 Verificación

```bash
docker ps                                  # workana_bot, workana_api, workana-dashboard, workana-cloudflared
curl -s http://localhost:8000/api/projects -o /dev/null -w "%{http_code}\n"   # API interna
# desde el navegador:
#   https://workana.koiosoft.com           # Dashboard público (via Cloudflare)
```

---

## 5. Orden crítico (NO cambiar)

```
1. backend  → up   (CREA 'workana_net' y expone 'api:8000')
2. frontend → up   (consume api:8000 + levanta túnel Cloudflare)
```

---

## 6. Vía agente PI (alternativa a los comandos)

En cada carpeta, abrir PI y ejecutar el prompt:

```
/sdd-deploy
```

El rol `role.devops` leerá `.sdd/core/deploy/DEPLOY.md`, correrá el preflight,
pedirá **confirmación**, desplegará con rollback automático si el healthcheck
falla. Hace exactamente lo mismo que los scripts (el prompt es documentación viva).

---

## 7. Actualizaciones futuras (NO reclonar)

Ya clonado, para cada release nuevo basta:

```bash
cd ~/servicios/backend  && ./scripts/devops/deploy_prod.sh
cd ~/servicios/frontend && ./scripts/devops/deploy_prod.sh
```

`deploy_prod.sh` hace internamente: `git fetch` + `git merge --ff-only origin/stable`
+ `docker compose build/up`. Exige estar en la rama `stable` (aborta si no).

---

## 8. Checklist pre-vuelo

- [ ] Backend levantado primero (crea la red `workana_net`).
- [ ] Clave SSH del servidor con acceso a `koiosoft.github.com`.
- [ ] `.env` del backend con valores reales (Atlas, Telegram, IA).
- [ ] `.env` del frontend con `NEXT_PUBLIC_WORKANA_PUBLIC_API_URL` + `TUNNEL_TOKEN`.
- [ ] Túnel de la máquina de desarrollo **apagado**.
- [ ] `MONGO_URI`/`MONGODB_URI` apuntan a **Atlas** (no local).
- [ ] `cloudflared-config.yml` presente (viene en el repo del frontend) y
      `service: http://dashboard:3000` coincide con el servicio del compose.
- [ ] `check_prod.sh` en ambos repos → ✅ antes del `deploy_prod.sh`.

---

## 9. Rollback (si algo falla en prod)

```bash
cd ~/servicios/<backend|frontend>
./scripts/devops/rollback_prod.sh            # al commit anterior de stable
./scripts/devops/rollback_prod.sh vX.Y.Z     # a un tag/commit especifico
```
