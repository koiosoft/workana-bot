import os
import re
import json
import time
from typing import Any, cast, Optional
from google import genai
import google.genai.errors
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from ..port import IntelligencePort
from app.exceptions import AIConnectionError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.bots.telegram.circuit_breaker import CircuitBreaker

FILTER_MODEL = "models/gemma-4-31b-it"      # 15 RPM - Gratis
STANDARD_MODEL = "models/gemini-2.5-flash" # 2000 RPM - Pago (muy barato)
PREMIUM_MODEL = "models/gemini-2.5-pro"    # 2 RPM - Pago (1.5 centavos)

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

    async def evaluate_projects(
        self, projects: list[dict], circuit_breaker: Optional["CircuitBreaker"] = None
    ) -> list[dict[str, Any]]:
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
        
        try:
            self.set_gemini_model()
            logger.info(f"🤖 Modelo de IA seleccionado para evaluación: '{self.model_id}'")

            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )

            if circuit_breaker:
                circuit_breaker.record_success()

            if response.text:
                text_response = response.text.strip()
                match = re.search(r"```json\s*(\[.*?\])\s*```", text_response, re.DOTALL)
                if match:
                    json_part = match.group(1)
                else:
                    json_part = text_response[text_response.find("[") : text_response.rfind("]") + 1]

                results = json.loads(json_part)
                logger.info(f"IA evaluó un lote de {len(results)} proyectos.")
                return cast(list[dict[str, Any]], results) if results else []
            
            logger.warning("La IA de evaluación no devolvió texto.")
            return []

        except google.genai.errors.APIError as e:
            logger.error(f"Error en API de IA durante la evaluación: {e}")
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError("La API de IA falló durante la evaluación de proyectos.") from e
        except Exception as e:
            logger.error(f"Error inesperado en evaluación de IA: {e}")
            # No registramos esto como una falla de API necesariamente, podría ser un error de parsing, etc.
            raise e
        

    async def generate_proposal(
        self, project: dict, circuit_breaker: Optional["CircuitBreaker"] = None
    ) -> dict[str, Any]:
        """
        Genera una propuesta económica detallada con hitos basada en el valor por hora.
        Usa diferentes templates según el tipo de contrato detectado.
        """
        hourly_rate = 25
        contract_type = project.get("contract_type", "project_fixed")
        
        logger.info(f'Generando propuesta para tipo de contrato: {contract_type}')

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

        template_name = "proposal_staffing.j2" if contract_type == "staff_augmentation" else "proposal.j2"
        
        prompt = self._render_prompt(
            template_name,
            my_profile_skills=my_skills,
            hourly_rate=hourly_rate,
            project_payload_json=json.dumps(project_payload, indent=2)
        )
        
        try:
            strategy = project.get("strategy", self.default_strategy)
            self.set_gemini_model(strategy)
            self.set_delay_model(strategy)

            time.sleep(self.delay_model)

            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )

            if circuit_breaker:
                circuit_breaker.record_success()

            if response.text is None:
                logger.warning("La IA no devolvió texto en la generación de propuesta.")
                return {"error": "No se pudo generar la propuesta, la IA no devolvió contenido."}
            
            text_response = response.text.strip()
            match = re.search(r"```json\s*(\{.*?\})\s*```", text_response, re.DOTALL)
            json_part = match.group(1) if match else text_response[text_response.find("{") : text_response.rfind("}") + 1]
            
            proposal_data = json.loads(json_part)

            if 'questions_for_client' not in proposal_data:
                proposal_data['questions_for_client'] = []
            
            return proposal_data

        except google.genai.errors.APIError as e:
            logger.error(f"Error en API de IA durante la generación de propuesta: {e}")
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError("La API de IA falló durante la generación de propuesta.") from e
        except Exception as e:
            logger.error(f"Error inesperado generando propuesta: {e}")
            # No es una falla de API, podría ser JSON mal formado, etc.
            # Devolvemos un error para que el handler sepa que este proyecto falló.
            return {"error": f"Error inesperado: {e}"}

    async def format_project_description(
        self, description: str, circuit_breaker: Optional["CircuitBreaker"] = None
    ) -> str:
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

            if circuit_breaker:
                circuit_breaker.record_success()
            
            if response.text:
                logger.success("✅ Descripción formateada exitosamente.")
                return response.text.strip()
            
            logger.warning("La IA de formateo no devolvió texto. Usando descripción original.")
            return description

        except google.genai.errors.APIError as e:
            logger.error(f"Error en API de IA durante el formateo de descripción: {e}")
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError("La API de IA falló durante el formateo de descripción.") from e
        except Exception as e:
            logger.error(f"Error inesperado en formateo de descripción: {e}")
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
    
    