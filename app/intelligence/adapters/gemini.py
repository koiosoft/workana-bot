import os
import re
import json
from typing import Any, cast
from google import genai
from loguru import logger
from ..port import IntelligencePort

class GeminiAdapter(IntelligencePort):
    def __init__(self):
        logger.info('Instanciando el Adapter de GEMINI')
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            logger.error("La variable de entorno GEMINI_API_KEY no está configurada.")
            raise ValueError("GEMINI_API_KEY no configurada.")

        try:
            self.client = genai.Client(api_key=api_key)
            self.model_id = "models/gemini-flash-latest"
            
            logger.info('Definiendo las instrucciones generales para el Adapter de GEMINI')

            # Mantenemos tu perfil pero ajustamos para recibir una lista
            self.system_instructions = """
                Actúa como un Senior Fullstack Developer y Technical Recruiter con gran visión de negocio en el mercado de freelancers.
                Tu tarea es evaluar proyectos de Workana para determinar su viabilidad técnica y comercial.

                **MIS HABILIDADES CORE:**
                - Backend: Python (FastAPI, Django), Node.js (Express)
                - Frontend: React, Vue.js, Angular, TypeScript
                - Bases de Datos: PostgreSQL, MongoDB
                - DevOps: Docker, CI/CD

                **REGLAS DE EXCLUSIÓN CRÍTICA (Filtro Rojo):**
                - Descarta inmediatamente (Score 0 y should_propose: false) cualquier proyecto que requiera: PHP o Odoo. No me interesa trabajar con estas tecnologías bajo ninguna circunstancia.

                **CRITERIOS DE EVALUACIÓN (Lógica de Decisión):**

                1. Ajuste Técnico (Prioridad Máxima):
                - Evalúa si el stack coincide con mis habilidades. 
                - Proyectos de IA, Automatización, APIs y Web Scraping son altamente valorados.
                - Prioriza proyectos que hablen de: "Escalabilidad", "Optimización de base de datos", "Integraciones complejas", "Refactorización" o "Sistemas desde cero".
                - Un proyecto que requiere un buen diseño relacional o patrones de diseño vale más que un script aislado.

                2. Flexibilidad de Presupuesto (Contexto LatAm):
                - No descartes proyectos por tener un presupuesto bajo (ej. < 100 USD) si la descripción parece ser de un proyecto serio.
                - Entiende que muchos clientes ponen "100 USD" como placeholder para negociar después. Solo penaliza el presupuesto si el cliente parece buscar "mucho trabajo por poco dinero" de forma cerrada.
                - Ignora también la barrera de los 100 USD si el proyecto suena a "Producto Mínimo Viable (MVP)" o "Core Business". 

                3. Manejo de Información Incompleta:
                - Si el título o la descripción son breves, NO los descartes. Si el título sugiere un desafío técnico interesante (ej: "Script de IA para leads"), asígnale un voto de confianza (5). 
                - La falta de detalle puede ser una oportunidad para definir el alcance en la propuesta.

                **FORMATO DE SALIDA (Estrictamente JSON):**
                Devuelve un array de objetos con esta estructura:
                [
                {
                    "link_hash": "string",
                    "score": integer (0 a 10),
                    "should_propose": boolean,
                    "reason": "Explicación concisa justificando el score basado en el stack o el potencial de negociación."
                }
                ]
            """

            try:
                logger.info("Listando modelos disponibles para esta API KEY...")
                models_available = ""
                for model in self.client.models.list():
                    models_available = f"ID: {model.name}/n"
                logger.debug(f"Models Available:/n {models_available}  ")
            except Exception as e:
                logger.error(f"No se pudo listar los modelos: {e}")        

        except Exception as e:
            logger.critical(f"❌ Error inicializando Google GenAI:: {e}")
            raise RuntimeError(f"Error inicializando Google GenAI: {e}")

    async def evaluate_projects(self, projects: list[dict]) -> list[dict]:
        """Evalúa un lote de proyectos en una sola llamada."""
        if not projects:
            return []

        # Serializamos los datos relevantes para la IA
        projects_payload = []
        for p in projects:
            projects_payload.append({
                "link_hash": p.get("link_hash"),
                "title": p.get("title"),
                "budget": p.get("budget"),
                "description": p.get("description", p.get("short_description", "N/A")),
                "skills": p.get("skills", [])
            })

        prompt = f"{self.system_instructions}\n\n**Proyectos a evaluar:**\n{json.dumps(projects_payload, indent=2)}"

        # logger.info(f"Actual prompt para la IA {prompt} .")

        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            if response.text:
                text_response = response.text.strip()
                #logger.info(f"IA respondio con {response} .")
                # Tu lógica original de limpieza de JSON mejorada para arrays
                match = re.search(r"```json\s*(\[.*?\])\s*```", text_response, re.DOTALL)
                if match:
                    json_part = match.group(1)
                else:
                    json_part = text_response[text_response.find("[") : text_response.rfind("]") + 1]

                results = json.loads(json_part)
                logger.info(f"IA evaluó un lote de {len(results)} proyectos.")
                if results:
                    return cast( list[dict],results ) 
                else:
                    logger.warning("La IA devolvió una lista vacía.")
                    return  []

        except Exception as e:
            logger.error(f"Error masivo en evaluación de IA: {e}")
            if "API key not valid" in str(e) or "400" in str(e):
                    raise e
            # Fallback: devolver todo como 'no proponer' para no romper el flujo
            return [{"link_hash": p.get("link_hash"), "score": 0, "should_propose": False, "reason": "Error en IA"} for p in projects]
        

    async def generate_proposal(self, project: dict) -> dict[str, Any]:
        """
        Genera una propuesta económica detallada con hitos basada en el valor por hora.
        """
        hourly_rate = 20.5
        
        logger.info('is generating a proposal...')

        my_skills = [
            "Typescript", "React", "Angular", "VueJS", "ReactNative", "IONIC",
            "NestJS", "ExpressJS", "PHP", "Laravel", "Python", "FastAPI", "Django",
            "SQL", "MySQL", "PostgreSQL", "MongoDB", "GIT", "Swift", "C#", "Docker",
            "UML Diagram", "DB Design (E-R)", "REST & GraphQL APIs"
        ]


        # Preparamos el contexto para la IA
        proposal_context = {
            "title": project.get("title", "Proyecto sin título"),
            "description": project.get("full_description", project.get("description", "N/A")),
            "skills_required": project.get("skills", []),
            "budget_range": project.get("budget_detail", "N/A"),
            "my_profile_skills": my_skills,
            "hourly_rate": hourly_rate
        }

        proposal_instructions = f"""
            Actúa como un Arquitecto de Software Senior con más de 24 años de experiencia contrastada. 
            Tu objetivo es generar una propuesta técnico-económica en stricto formato JSON para un proyecto de Workana.

            **MI PERFIL TÉCNICO (STACK REAL):**
            {", ".join(my_skills)}

            **INSTRUCCIONES DE ESTIMACIÓN Y NEGOCIO:**
            1. **Análisis de Match:** Cruza los requerimientos del cliente con mi stack real. Resalta mi capacidad para diseñar arquitecturas escalables y seguras.
            2. **Cálculo de Tiempos (Lógica de Overhead):** 
                - Estima las horas netas de desarrollo (aquí se permiten decimales internos para precisión). Sigue las siguientes reglas:
                    * Aplica obligatoriamente un 20% de overhead sobre la estimación (Horas Netas * 1.2).
                    * Regla de Formato Final: El valor hours_with_overhead resultante DEBE ser un número entero.
                    * Redondeo: Aplica la función techo (ceiling) al resultado final: cualquier fracción sube al entero superior (Ej: 3.01h → 4h).
                    * Mínimo Vital: Ninguna tarea puede durar menos de 1 hora.
            3. **Cálculo de Costos:** Subtotal de hito = (Suma de horas del hito con overhead) * ${hourly_rate}.
            4. **Estructura de Hitos:** - Genera entre 4 y 8 hitos según la complejidad.
            - Es obligatorio incluir un hito final dedicado exclusivamente a **UAT (User Acceptance Testing), Refactorización y Despliegue Final**.
            - Las pruebas unitarias deben estar diluidas dentro de las tareas de desarrollo de cada hito (menciónalas en las descripciones).
            5. **Tono:** Profesional, extremadamente técnico, persuasivo y orientado a resultados de negocio.

            **VERIFICACIONES FINALES:**
                - Verificación Matemática: La suma de los subtotales de cada hito debe coincidir exactamente con el total_budget final del JSON.
                - Output check: Verifica que todos los campos de horas en el JSON sean integers.

            **FORMATO DE SALIDA (JSON ESTRICTO):**
            {{
                "proposal_header": "Saludo de Arquitecto Senior destacando los 24+ años de experiencia y la idoneidad técnica para este proyecto específico.",
                "milestones": [
                    {{
                        "step": 1,
                        "name": "Nombre del hito (ej. Arquitectura de Base de Datos y Auth)",
                        "tasks": {{
                            "Nombre de Tarea 1": {{
                                "description": "Detalle técnico profundo de la implementación incluyendo mención a Unit Testing.",
                                "hours_with_overhead": float
                            }},
                            "Nombre de Tarea 2": {{
                                "description": "Detalle técnico de la tarea.",
                                "hours_with_overhead": float
                            }}
                        }},
                        "hours_with_overhead": float,
                        "subtotal": float
                    }}
                ],
                "summary": {{
                    "total_hours": float,
                    "total_budget": float,
                    "delivery_time_weeks": float,
                    "hourly_rate_applied": {hourly_rate}
                }},
                "technical_pitch": "Argumento de cierre sobre por qué mi experiencia con {", ".join(my_skills[:5])}... garantiza el éxito donde otros fallan."
            }}
        """

        prompt = f"{proposal_instructions}\n\n**DATOS DEL PROYECTO:**\n{json.dumps(proposal_context, indent=2)}"

        logger.info('=========== el PROMPT ======================')
        logger.info(prompt)

        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )

            logger.info('self.client.models.generate_content IN EXECUTION')

            if response.text is None:
                return {"error": "No se pudo generar la propuesta"}
            
            text_response = response.text.strip()
            # Limpieza de markdown para extraer el JSON
            match = re.search(r"```json\s*({{.*?}})\s*```", text_response, re.DOTALL)
            json_part = match.group(1) if match else text_response[text_response.find("{") : text_response.rfind("}") + 1]
            
            return json.loads(json_part)

        except Exception as e:
            logger.error(f"Error generando propuesta económica: {e}")
            return {"error": "No se pudo generar la propuesta"}

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
