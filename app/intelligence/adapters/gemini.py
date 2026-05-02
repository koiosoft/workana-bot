import os
import re
import json
import google.generativeai as genai
from loguru import logger
from ..port import IntelligencePort


class GeminiAdapter(IntelligencePort):
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("La variable de entorno GEMINI_API_KEY no está configurada.")
            raise ValueError("GEMINI_API_KEY no configurada.")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")
        self.prompt_template = """
        Actúa como un Senior Python/Node.js Developer con experiencia en React, Vue, Angular, y bases de datos SQL/NoSQL.
        Tu objetivo es decidir si vale la pena enviar una propuesta a un proyecto en una plataforma de freelancers.

        **Mis Habilidades:**
        - Backend: Python (FastAPI, Django), Node.js (Express)
        - Frontend: React, Vue.js, Angular, TypeScript
        - Bases de Datos: PostgreSQL, MongoDB
        - DevOps: Docker, CI/CD

        **Criterios de Evaluación:**
        1.  **Ajuste Técnico:** ¿El proyecto se alinea con mis habilidades? (Prioridad Alta)
        2.  **Presupuesto:** ¿El presupuesto parece razonable para el trabajo descrito? (Prioridad Media). Presupuestos fijos por debajo de 100 USD son poco atractivos a menos que el trabajo sea mínimo.
        3.  **Claridad:** ¿La descripción del proyecto es clara y detallada? (Prioridad Media)
        4.  **Red Flags:** Evita proyectos con descripciones vagas, presupuestos irrisorios, o tecnologías que no domino (ej. PHP, C#, WordPress, Shopify, Wix, Joomla).

        **Proyecto a Evaluar:**
        - **Título:** {title}
        - **Presupuesto:** {budget}
        - **Descripción (si disponible):** {description}

        **Tu Tarea:**
        Responde únicamente con un objeto JSON válido con la siguiente estructura:
        {{
          "should_propose": boolean,
          "reason": "Una explicación concisa de tu decisión."
        }}
        """

    async def evaluate_project(self, project: dict) -> dict:
        prompt = self.prompt_template.format(
            title=project.get("title", "N/A"),
            budget=project.get("budget", "N/A"),
            description=project.get("description", "N/A"),
        )
        try:
            response = await self.model.generate_content_async(prompt)
            text_response = response.text.strip()

            # El modelo a veces devuelve el JSON dentro de un bloque de código markdown.
            # Esta expresión regular busca y extrae el JSON de manera robusta.
            match = re.search(r"```json\s*(\{.*?\})\s*```", text_response, re.DOTALL)
            if match:
                json_part = match.group(1)
            else:
                # Si no está en un bloque, se busca el objeto JSON directamente.
                json_part = text_response[
                    text_response.find("{") : text_response.rfind("}") + 1
                ]

            logger.info(f"Evaluación de IA para '{project.get('title')}': {json_part}")
            result = json.loads(json_part)
            return result

        except Exception as e:
            logger.error(f"Error durante la evaluación de IA para el proyecto '{project.get('title')}': {e}")
            return {"should_propose": False, "reason": f"Error durante la evaluación: {e}"}
