# 🚀 Workana AI Command Center

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-enabled-blue.svg)](https://www.docker.com/)
[![MongoDB 8.0](https://img.shields.io/badge/mongodb-8.0_LTS-green.svg)](https://www.mongodb.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Workana AI Command Center** es un sistema inteligente de monitoreo y automatización diseñado para freelancers de alto nivel. El sistema utiliza **Playwright** para el scraping, **Google Gemini AI** para el análisis de proyectos y **Telegram** como una interfaz de control móvil ("Command Center").

## 📸 Interfaz de Control (Telegram)
El bot permite supervisar todo el flujo de trabajo desde el celular, permitiendo al desarrollador intervenir solo cuando la IA ha detectado una oportunidad de alto valor.

## 🛠️ Stack Tecnológico
- **Core:** Python 3.11 (Asincrónico)
- **Bot Engine:** `python-telegram-bot` v22.7
- **Base de Datos:** MongoDB 8.0 LTS (Motor Async)
- **Scraping:** Playwright (Chromium headless)
- **Inteligencia Artificial:** Google Gemini Pro API
- **Infraestructura:** Docker & Docker Compose
- **Logs:** Loguru (Rotativos y persistentes)

## 🏗️ Arquitectura del Sistema
El bot gestiona los proyectos a través de una máquina de estados:
1.  **NUEVO**: Detectado por el scraper.
2.  **ANALIZADO**: Score generado por IA (0-100).
3.  **OFERTADO**: Propuesta enviada.
4.  **NEGOCIACIÓN**: El cliente ha respondido (Alerta prioritaria).
5.  **CONTRATADO/DESCARTADO**: Estados finales.

## 🚀 Instalación y Despliegue rápido

### 1. Clonar el repositorio
```bash
git clone [https://github.com/tu-usuario/workana-bot.git](https://github.com/tu-usuario/workana-bot.git)
cd workana-bot