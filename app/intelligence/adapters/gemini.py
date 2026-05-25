import os
import re
import json
import time
from typing import Any, cast
from google import genai
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from ..port import IntelligencePort

FILTER_MODEL = "models/gemma-4-31b-it"      # 15 RPM - Gratis
STANDARD_MODEL = "models/gemini-flash-latest" # 2000 RPM - Pago (muy barato)
PREMIUM_MODEL = "models/gemini-1.5-pro"    # 2 RPM - Pago (1.5 centavos)

class GeminiAdapter(IntelligencePort):
    def __init__(self):
        self.default_strategy = "none"
        self.flash_strategy = 'flash'
        self.pro_strategy = 'pro'
        self.delay_model = 1
        template_path = os.path.join(os.path.dirname(__file__), '../prompts')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path))

        logger.info('Instanciando el Adapter de GEMINI')
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            logger.error("La variable de entorno GEMINI_API_KEY no está configurada.")
            raise ValueError("GEMINI_API_KEY no configurada.")

        try:
            self.client = genai.Client(api_key=api_key)
            self.model_id = "models/gemini-flash-latest"
            
            self.evaluation_instructions = ""
            self.proposal_instructions = ""

        except Exception as e:
            logger.critical(f"❌ Error inicializando Google GenAI:: {e}")
            raise RuntimeError(f"Error inicializando Google GenAI: {e}")
        
    def _render_prompt(self, template_name: str, **kwargs) -> str:
            """Centraliza la carga y renderización de plantillas."""
            template = self.jinja_env.get_template(template_name)
            return template.render(**kwargs)

    async def evaluate_projects(self, projects: list[dict]) -> list[dict[str, Any]]:
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

        template = self.jinja_env.get_template("evaluation.j2")
        prompt = template.render(
            pro_strategy=self.pro_strategy,
            flash_strategy=self.flash_strategy,
            default_strategy=self.default_strategy,
            projects_payload=json.dumps(projects_payload, indent=2)
        )

        # logger.info(f"Actual prompt para la IA {prompt} .")
        #. Trabajamso con GEMMA por las quotas establecidas
        try:
            self.set_gemini_model()
            logger.info(f"🤖 Modelo de IA seleccionado : '{self.model_id}'")

            logger.info('=========== PROMPT EVALUACION (INICIO)  ======================')
            logger.info(prompt)
            logger.info('=========== PROMPT EVALUACION  (FIN) ======================')

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
                    return cast(  list[dict[str, Any]],results ) 
                else:
                    logger.warning("La IA devolvió una lista vacía.")
                    return  []
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
        hourly_rate = 25
        
        logger.info('is generating a proposal...')

        my_skills = [
            "Typescript", "React", "Angular", "VueJS", "ReactNative", "IONIC",
            "NestJS", "ExpressJS", "PHP", "Laravel", "Python", "FastAPI", "Django",
            "SQL", "MySQL", "PostgreSQL", "MongoDB", "GIT", "Swift", "C#", "Docker",
            "UML Diagram", "DB Design (E-R)", "REST & GraphQL APIs"
        ]


        # Preparamos el contexto para la IA
        project_payload = {
            "title": project.get("title", "Proyecto sin título"),
            "description": project.get("full_description", project.get("description", "N/A")),
            "skills_required": project.get("skills", []),
            "budget_range": project.get("budget_detail", "N/A")
        }

        prompt = self._render_prompt(
            "proposal.j2",
            my_profile_skills=my_skills,
            hourly_rate=hourly_rate,
            project_payload_json=json.dumps(project_payload, indent=2)
        )

        logger.info('Definiendo el PROMPT para el Adapter de GEMINI') 
        
        logger.info('=========== PROMPT PROPOSAL (INICIO)  ======================')
        logger.info(prompt)
        logger.info('=========== PROMPT PROPOSAL (FIN) ======================')
        try:
            strategy = project.get("strategy", self.default_strategy)
            self.set_gemini_model(strategy)
            self.set_delay_model(strategy)

            time.sleep(self.delay_model)

            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )

            logger.info('self.client.models.generate_content IN EXECUTION')

            if response.text is None:
                return {"error": "No se pudo generar la propuesta"}
            
            text_response = response.text.strip()
            # Limpieza de markdown para extraer el JSON
            match = re.search(r"```json\s*(\{.*?\})\s*```", text_response, re.DOTALL)
            json_part = match.group(1) if match else text_response[text_response.find("{") : text_response.rfind("}") + 1]
            
            proposal_data = json.loads(json_part)

            # Normalización: Asegurar que 'questions_for_client' siempre exista
            if 'questions_for_client' not in proposal_data:
                proposal_data['questions_for_client'] = []
            
            return proposal_data

        except Exception as e:
            logger.error(f"Error generando propuesta económica: {e}")
            return {"error": "No se pudo generar la propuesta"}

    async def format_project_description(self, description: str) -> str:
        """Formatea la descripción de un proyecto usando IA para mejorar legibilidad."""
        
        prompt = self._render_prompt(
            "project_formatter.j2",
            raw_description=description
        )
        
        logger.info("🤖 Llamando a Gemini Flash para formatear descripción...")
        try:
            # Usamos el modelo más rápido y económico para esta tarea.
            response = self.client.models.generate_content(
                model=STANDARD_MODEL,
                contents=prompt
            )
            
            if response.text:
                logger.success("✅ Descripción formateada exitosamente.")
                return response.text.strip()
            
            logger.warning("La IA de formateo no devolvió texto. Usando descripción original.")
            return description

        except Exception as e:
            logger.error(f"Error en la IA de formateo: {e}. Se propagará la excepción.")
            # Propagamos la excepción para que el manejador principal la capture
            # y active los reintentos, como se solicitó.
            raise e

    def set_gemini_model(self, strategy = "none") -> str:
        self.model_id = FILTER_MODEL
        if strategy == self.pro_strategy:
            self.model_id  = PREMIUM_MODEL
        elif strategy == self.flash_strategy :
            self.model_id  = STANDARD_MODEL
        return self.model_id 

    def set_delay_model(self, strategy = "none") -> int:
        self.delay_model = 5
        if strategy == self.pro_strategy:
            self.delay_model  = 35
        elif strategy == self.flash_strategy :
            self.delay_model  = 1
        return self.delay_model 
    
    