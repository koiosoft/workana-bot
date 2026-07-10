import os
import re
import json
import asyncio
from typing import Any, cast, Optional
from google import genai
import google.genai.errors
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from ..port import IntelligencePort
from app.exceptions import AIConnectionError
from typing import TYPE_CHECKING
from httpx import RemoteProtocolError

if TYPE_CHECKING:
    from app.bots.telegram.circuit_breaker import CircuitBreaker

FILTER_MODEL = "models/gemma-4-31b-it"      # 15 RPM - Gratis
STANDARD_MODEL = "models/gemini-2.5-flash" # 2000 RPM - Pago (muy barato)
PREMIUM_MODEL = "models/gemini-2.5-pro"    # 2 RPM - Pago (1.5 centavos)

class GeminiAdapter(IntelligencePort):
    def __init__(
        self,
        standard_model: str | None = None,
        premium_model: str | None = None,
        filter_model: str | None = None,
    ):
        self.default_strategy = "none"
        self.flash_strategy = 'flash'
        self.pro_strategy = 'pro'
        self.delay_model = 1

        # Allow overriding model IDs from the database-driven factory.
        # Fall back to module-level constants when no override is provided.
        self._standard_model_override = standard_model
        self._premium_model_override = premium_model
        self._filter_model_override = filter_model

        template_path = os.path.join(os.path.dirname(__file__), '../prompts')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path))

        logger.info('Instanciando el Adapter de GEMINI')
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            logger.error("La variable de entorno GEMINI_API_KEY no está configurada.")
            raise ValueError("GEMINI_API_KEY no configurada.")

        try:
            # Habilitamos retries automáticos del SDK para errores transitorios (503, 429, etc.).
            # Por defecto: 5 intentos, backoff exponencial (1s → 60s max), con jitter.
            # Esto evita que picos temporales de demanda en Google tumben el circuito.
            http_opts = genai.types.HttpOptions(
                retry_options=genai.types.HttpRetryOptions()
            )
            self.client = genai.Client(api_key=api_key, http_options=http_opts)
            self.model_id = FILTER_MODEL
            
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

        except RemoteProtocolError as e:
            logger.error(f"Conexión interrumpida durante evaluación: {e}")
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError("Servidor de IA interrumpido inesperadamente") from e
        except google.genai.errors.APIError as e:
            logger.error(f"Error en API de IA durante la evaluación: {e}")
            if circuit_breaker:
                circuit_breaker.record_failure()
            error_details = getattr(e, 'response_json', {}).get('error', {})
            raise AIConnectionError(f"La API de IA falló durante la evaluación de proyectos: {error_details.get('message', 'Unknown error')}") from e
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

            await asyncio.sleep(self.delay_model)  # Replace time.sleep with asyncio.sleep

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

        except RemoteProtocolError as e:
            logger.error(f"Conexión interrumpida durante generación de propuesta: {e}")
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError("Servidor de IA interrumpido inesperadamente") from e
        except google.genai.errors.APIError as e:
            logger.error(f"Error en API de IA durante la generación de propuesta: {e}")
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError(f"La API de IA falló durante la generación de propuesta: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado generando propuesta: {e}")
            # No es una falla de API, podría ser JSON mal formado, etc.
            # Devolvemos un error para que el handler sepa que este proyecto falló.
            return {"error": f"Error inesperado: {e}"}

    async def refine_proposal(
        self,
        project: dict[str, Any],
        user_feedback_observations: str,
        model_id: str,
        contract_type: str = "project_fixed",
        use_initial_template: bool = False,
        circuit_breaker: Optional["CircuitBreaker"] = None,
    ) -> dict[str, Any]:
        """Refine an existing proposal using user feedback and a specific LLM model.

        When *use_initial_template* is True (contract type changed), the initial
        proposal template is used instead of the refinement template, effectively
        regenerating the proposal from scratch.

        When *contract_type* is ``"staff_augmentation"`` and the template is not
        an initial one, the ``refine-staffing.j2`` template is used.
        """
        hourly_rate = 25
        my_skills = [
            "Typescript", "React", "Angular", "VueJS", "ReactNative", "IONIC",
            "NestJS", "ExpressJS", "PHP", "Laravel", "Python", "FastAPI", "Django",
            "SQL", "MySQL", "PostgreSQL", "MongoDB", "GIT", "Swift", "C#", "Docker",
            "UML Diagram", "DB Design (E-R)", "REST & GraphQL APIs"
        ]

        project_payload: dict[str, Any] = {
            "title": project.get("title", "Proyecto sin título"),
            "description": project.get(
                "full_description", project.get("description", "N/A")
            ),
            "skills_required": project.get("skills", []),
            "budget_range": project.get("budget_detail", "N/A"),
        }

        # Extract current proposal data for the LLM context
        current_proposal = project.get("proposal") or project.get("proposal_data")
        current_proposal_json = (
            json.dumps(current_proposal, indent=2) if current_proposal else "{}"
        )

        # -- Template selection ----------------------------------------------
        if use_initial_template:
            template_name = (
                "proposal_staffing.j2" if contract_type == "staff_augmentation"
                else "proposal.j2"
            )
            logger.info(
                f"🔄 Contract type changed → using initial template '{template_name}'"
            )
            prompt = self._render_prompt(
                template_name,
                my_profile_skills=my_skills,
                hourly_rate=hourly_rate,
                project_payload_json=json.dumps(project_payload, indent=2),
            )
        elif contract_type == "staff_augmentation":
            logger.info("🔁 Staff augmentation refinement → using refine-staffing.j2")
            prompt = self._render_prompt(
                "refine-staffing.j2",
                my_profile_skills=my_skills,
                hourly_rate=hourly_rate,
                suggested_hours_per_week=20,
                project_payload_json=json.dumps(project_payload, indent=2),
                current_proposal_json=current_proposal_json,
                user_feedback_observations=user_feedback_observations,
            )
        else:
            logger.info("🔁 Project-fixed refinement → using refine.j2")
            prompt = self._render_prompt(
                "refine.j2",
                project_payload_json=json.dumps(project_payload, indent=2),
                current_proposal_json=current_proposal_json,
                user_feedback_observations=user_feedback_observations,
            )

        try:
            # Override model with the user-specified one (if provided)
            original_model = self.model_id
            if model_id:
                self.model_id = model_id

            logger.info(
                f"🤖 Refinando propuesta con modelo: '{self.model_id}'"
            )

            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )

            # Restore original model
            self.model_id = original_model

            if circuit_breaker:
                circuit_breaker.record_success()

            if response.text is None:
                logger.warning("La IA no devolvió texto en el refinamiento de propuesta.")
                return {"error": "No se pudo refinar la propuesta, la IA no devolvió contenido."}

            text_response = response.text.strip()
            logger.debug(
                f"[DEBUG gemini refine] Raw LLM response (len={len(text_response)}): "
                f"{text_response[:500]}...{text_response[-200:] if len(text_response) > 700 else ''}"
            )
            match = re.search(r"```json\s*(\{.*?\})\s*```", text_response, re.DOTALL)
            json_part = match.group(1) if match else text_response[text_response.find("{") : text_response.rfind("}") + 1]
            logger.debug(
                f"[DEBUG gemini refine] Extracted json_part (len={len(json_part)}): "
                f"{json_part[:300]}..."
            )

            refined_data: dict[str, Any] = json.loads(json_part)
            logger.debug(
                f"[DEBUG gemini refine] Parsed refined_data keys: {list(refined_data.keys())}"
            )
            return refined_data

        except RemoteProtocolError as e:
            logger.error(f"Conexión interrumpida durante refinamiento de propuesta: {e}")
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError("Servidor de IA interrumpido inesperadamente") from e
        except google.genai.errors.APIError as e:
            logger.error(f"Error en API de IA durante el refinamiento de propuesta: {e}")
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError(f"La API de IA falló durante el refinamiento de propuesta: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado refinando propuesta: {e}")
            return {"error": f"Error inesperado: {e}"}

    async def format_project_description(
        self, description: str, circuit_breaker: Optional["CircuitBreaker"] = None
    ) -> str:
        """Formatea la descripción de un proyecto usando IA para mejorar legibilidad."""
        
        prompt = self._render_prompt(
            "project_formatter.j2",
            raw_description=description
        )
        
        logger.info("🤖 Llamando a Gemini para formatear descripción...")
        try:
            self.set_gemini_model(self.flash_strategy)
            response = self.client.models.generate_content(
                model=self.model_id,
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
            raise AIConnectionError(f"La API de IA falló durante el formateo de descripción: {e}") from e
        except Exception as e:
            logger.error(f"Error inesperado en formateo de descripción: {e}")
            raise e

    def set_gemini_model(self, strategy = "none") -> str:
        self.model_id = self._filter_model_override or FILTER_MODEL
        if strategy == self.pro_strategy:
            self.model_id = self._premium_model_override or PREMIUM_MODEL
        elif strategy == self.flash_strategy:
            self.model_id = self._standard_model_override or STANDARD_MODEL
        return self.model_id 

    def set_delay_model(self, strategy = "none") -> float:
        self.delay_model = 5.0
        if strategy == self.pro_strategy:
            self.delay_model  = 35.0
        elif strategy == self.flash_strategy :
            self.delay_model  = 1.0
            
        override = os.getenv("GEMINI_DELAY_OVERRIDE")
        if override is not None:
            self.delay_model = float(override)
            
        return self.delay_model 
    
    

