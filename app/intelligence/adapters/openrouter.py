import os
import re
import json
from typing import Any, cast, Optional
import httpx
from jinja2 import Environment, FileSystemLoader
from loguru import logger
from ..port import IntelligencePort
from app.exceptions import AIConnectionError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.bots.telegram.circuit_breaker import CircuitBreaker

# Modelos disponibles via OpenRouter (compatibles con chat completions)
STANDARD_MODEL = "qwen/qwen3-14b"  
PREMIUM_MODEL = "deepseek/deepseek-v4-pro"     

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterAdapter(IntelligencePort):
    """
    Adaptador de inteligencia artificial que utiliza OpenRouter como proveedor.
    Implementa el contrato IntelligencePort usando la API de chat completions
    compatible con OpenAI, permitiendo enrutar solicitudes a distintos modelos.
    """

    def __init__(
        self,
        standard_model: str | None = None,
        premium_model: str | None = None,
        filter_model: str | None = None,
    ) -> None:
        self.default_strategy = "none"
        self.flash_strategy = "flash"
        self.pro_strategy = "pro"
        self.filter_strategy = "filter"
        self.delay_model = 1.0

        # Allow overriding model IDs from the database-driven factory.
        # Fall back to module-level constants when no override is provided.
        self._standard_model_override = standard_model
        self._premium_model_override = premium_model
        self._filter_model_override = filter_model

        template_path = os.path.join(os.path.dirname(__file__), "../prompts")
        self.jinja_env = Environment(loader=FileSystemLoader(template_path))

        logger.info("Instanciando el Adapter de OpenRouter")
        api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            logger.error("La variable de entorno OPENROUTER_API_KEY no está configurada.")
            raise ValueError("OPENROUTER_API_KEY no configurada.")

        self.api_key = api_key
        self.model_id = STANDARD_MODEL

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _render_prompt(self, template_name: str, **kwargs: Any) -> str:
        """Centraliza la carga y renderización de plantillas Jinja2."""
        template = self.jinja_env.get_template(template_name)
        return template.render(**kwargs)

    def _select_model(self, strategy: str = "none") -> str:
        """
        Selecciona el modelo de OpenRouter según la estrategia.
        Devuelve el nombre del modelo en formato OpenRouter (e.g. google/gemini-2.5-flash).
        """
        if strategy == self.pro_strategy:
            self.model_id = self._premium_model_override or PREMIUM_MODEL
        elif strategy == self.flash_strategy:
            self.model_id = self._standard_model_override or STANDARD_MODEL
        elif strategy == self.filter_strategy:
            self.model_id = self._filter_model_override or STANDARD_MODEL
        else:
            self.model_id = self._standard_model_override or STANDARD_MODEL
        return self.model_id

    def _set_delay(self, strategy: str = "none") -> float:
        """Ajusta la demora entre llamadas según la estrategia y rate‑limits."""
        if strategy == self.pro_strategy:
            self.delay_model = 35.0
        elif strategy == self.flash_strategy:
            self.delay_model = 1.0
        else:
            self.delay_model = 5.0

        override = os.getenv("GEMINI_DELAY_OVERRIDE")
        if override is not None:
            self.delay_model = float(override)

        return self.delay_model

    async def _chat_completion(
        self,
        prompt: str,
        circuit_breaker: Optional["CircuitBreaker"] = None,
    ) -> str:
        """
        Realiza una llamada POST al endpoint de chat completions de OpenRouter
        y devuelve el texto de la respuesta. Lanza AIConnectionError si falla.
        """
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )

        if response.status_code != 200:
            logger.error(
                f"OpenRouter API error {response.status_code}: {response.text}"
            )
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError(
                f"OpenRouter API error {response.status_code}"
            )

        if circuit_breaker:
            circuit_breaker.record_success()

        data: dict[str, Any] = response.json()
        choices: list[dict[str, Any]] = data.get("choices", [])

        if not choices:
            logger.warning("OpenRouter no devolvió choices en la respuesta.")
            return ""

        return choices[0].get("message", {}).get("content", "")

    # ------------------------------------------------------------------
    # Métodos de la interfaz IntelligencePort
    # ------------------------------------------------------------------

    async def evaluate_projects(
        self,
        projects: list[dict[str, Any]],
        circuit_breaker: Optional["CircuitBreaker"] = None,
    ) -> list[dict[str, Any]]:
        """Evalúa un lote de proyectos en una sola llamada."""
        if not projects:
            return []

        projects_payload: list[dict[str, Any]] = []
        for p in projects:
            projects_payload.append(
                {
                    "link_hash": p.get("link_hash"),
                    "title": p.get("title"),
                    "budget": p.get("budget"),
                    "description": p.get(
                        "description", p.get("short_description", "N/A")
                    ),
                    "skills": p.get("skills", []),
                }
            )

        prompt = self._render_prompt(
            "evaluation.j2",
            pro_strategy=self.pro_strategy,
            flash_strategy=self.flash_strategy,
            default_strategy=self.default_strategy,
            projects_payload=json.dumps(projects_payload, indent=2),
        )

        try:
            self._select_model()
            logger.info(
                f"🤖 Modelo de IA seleccionado para evaluación: '{self.model_id}'"
            )

            text_response = await self._chat_completion(prompt, circuit_breaker)

            if not text_response:
                logger.warning("La IA de evaluación no devolvió texto.")
                return []

            text_response = text_response.strip()
            match = re.search(
                r"```json\s*(\[.*?\])\s*```", text_response, re.DOTALL
            )
            if match:
                json_part = match.group(1)
            else:
                json_part = text_response[
                    text_response.find("[") : text_response.rfind("]") + 1
                ]

            results: list[dict[str, Any]] = json.loads(json_part)
            logger.info(f"IA evaluó un lote de {len(results)} proyectos.")
            return cast(list[dict[str, Any]], results) if results else []

        except (httpx.RemoteProtocolError, httpx.HTTPError) as e:
            logger.error(f"Error de red en evaluación via OpenRouter: {e}")
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError(
                "Servidor de IA (OpenRouter) interrumpido inesperadamente"
            ) from e
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parseando respuesta de evaluación: {e}")
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError(
                "Respuesta de OpenRouter no pudo ser interpretada"
            ) from e

    async def generate_proposal(
        self,
        project: dict[str, Any],
        circuit_breaker: Optional["CircuitBreaker"] = None,
        project_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Genera una propuesta económica detallada con hitos.

        When *project_id* is provided, the generated proposal is automatically
        inserted as a new version into the ``proposal_versions`` collection
        (with ``version_number = MAX + 1``) instead of being stored as an
        embedded document on the project.
        """
        hourly_rate = int(os.getenv("HOURLY_RATE", "25"))
        contract_type: str = project.get("contract_type", "project_fixed")

        logger.info(f"Generando propuesta para tipo de contrato: {contract_type}")

        my_skills: list[str] = [
            "Typescript", "React", "Angular", "VueJS", "ReactNative", "IONIC",
            "NestJS", "ExpressJS", "PHP", "Laravel", "Python", "FastAPI", "Django",
            "SQL", "MySQL", "PostgreSQL", "MongoDB", "GIT", "Swift", "C#", "Docker",
            "UML Diagram", "DB Design (E-R)", "REST & GraphQL APIs",
        ]

        project_payload: dict[str, Any] = {
            "title": project.get("title", "Proyecto sin título"),
            "description": project.get(
                "full_description", project.get("description", "N/A")
            ),
            "skills_required": project.get("skills", []),
            "budget_range": project.get("budget_detail", "N/A"),
        }

        template_name = (
            "proposal_staffing.j2"
            if contract_type == "staff_augmentation"
            else "proposal.j2"
        )

        prompt = self._render_prompt(
            template_name,
            my_profile_skills=my_skills,
            hourly_rate=hourly_rate,
            project_payload_json=json.dumps(project_payload, indent=2),
        )

        try:
            strategy: str = project.get("strategy", self.default_strategy)
            self._select_model(strategy)
            self._set_delay(strategy)

            await __import__("asyncio").sleep(self.delay_model)

            text_response = await self._chat_completion(prompt, circuit_breaker)

            if not text_response:
                logger.warning(
                    "La IA no devolvió texto en la generación de propuesta."
                )
                return {
                    "error": "No se pudo generar la propuesta, la IA no devolvió contenido."
                }

            text_response = text_response.strip()
            match = re.search(
                r"```json\s*(\{.*?\})\s*```", text_response, re.DOTALL
            )
            json_part = (
                match.group(1)
                if match
                else text_response[
                    text_response.find("{") : text_response.rfind("}") + 1
                ]
            )

            proposal_data: dict[str, Any] = json.loads(json_part)

            if "questions_for_client" not in proposal_data:
                proposal_data["questions_for_client"] = []

            return proposal_data

        except (httpx.RemoteProtocolError, httpx.HTTPError) as e:
            logger.error(
                f"Error de red en generación de propuesta via OpenRouter: {e}"
            )
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError(
                "Servidor de IA (OpenRouter) interrumpido inesperadamente"
            ) from e
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parseando propuesta: {e}")
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError(
                "Respuesta de OpenRouter no pudo ser interpretada"
            ) from e

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
        proposal template is used instead of the refinement template.

        When *contract_type* is ``"staff_augmentation"``, the
        ``refine-staffing.j2`` template is selected.
        """
        hourly_rate = int(os.getenv("HOURLY_RATE", "25"))
        my_skills = [
            "Typescript", "React", "Angular", "VueJS", "ReactNative", "IONIC",
            "NestJS", "ExpressJS", "PHP", "Laravel", "Python", "FastAPI", "Django",
            "SQL", "MySQL", "PostgreSQL", "MongoDB", "GIT", "Swift", "C#", "Docker",
            "UML Diagram", "DB Design (E-R)", "REST & GraphQL APIs",
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
            # Override model_id with the user-specified one (if provided)
            original_model = self.model_id
            if model_id:
                self.model_id = model_id

            logger.info(
                f"🤖 Refinando propuesta con modelo: '{self.model_id}'"
            )

            text_response = await self._chat_completion(prompt, circuit_breaker)

            # Restore original model
            self.model_id = original_model

            if not text_response:
                logger.warning(
                    "La IA no devolvió texto en el refinamiento de propuesta."
                )
                return {
                    "error": "No se pudo refinar la propuesta, la IA no devolvió contenido."
                }

            text_response = text_response.strip()
            logger.debug(
                f"[DEBUG openrouter refine] Raw LLM response (len={len(text_response)}): "
                f"{text_response[:500]}...{text_response[-200:] if len(text_response) > 700 else ''}"
            )
            match = re.search(
                r"```json\s*(\{.*?\})\s*```", text_response, re.DOTALL
            )
            json_part = (
                match.group(1)
                if match
                else text_response[
                    text_response.find("{") : text_response.rfind("}") + 1
                ]
            )
            logger.debug(
                f"[DEBUG openrouter refine] Extracted json_part (len={len(json_part)}): "
                f"{json_part[:300]}..."
            )

            refined_data: dict[str, Any] = json.loads(json_part)
            logger.debug(
                f"[DEBUG openrouter refine] Parsed refined_data keys: {list(refined_data.keys())}"
            )
            return refined_data

        except (httpx.RemoteProtocolError, httpx.HTTPError) as e:
            logger.error(
                f"Error de red en refinamiento de propuesta via OpenRouter: {e}"
            )
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError(
                "Servidor de IA (OpenRouter) interrumpido inesperadamente"
            ) from e
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parseando propuesta refinada: {e}")
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError(
                "Respuesta de OpenRouter no pudo ser interpretada"
            ) from e

    async def format_project_description(
        self,
        description: str,
        circuit_breaker: Optional["CircuitBreaker"] = None,
    ) -> str:
        """Formatea la descripción de un proyecto usando IA."""
        prompt = self._render_prompt(
            "project_formatter.j2", raw_description=description
        )

        logger.info("🤖 Llamando a OpenRouter para formatear descripción...")

        try:
            self._select_model(self.filter_strategy)

            text_response = await self._chat_completion(prompt, circuit_breaker)

            if text_response:
                logger.success("✅ Descripción formateada exitosamente.")
                return text_response.strip()

            logger.warning(
                "La IA de formateo no devolvió texto. Usando descripción original."
            )
            return description

        except (httpx.RemoteProtocolError, httpx.HTTPError) as e:
            logger.error(
                f"Error de red en formateo de descripción via OpenRouter: {e}"
            )
            if circuit_breaker:
                circuit_breaker.record_failure()
            raise AIConnectionError(
                "Servidor de IA (OpenRouter) interrumpido inesperadamente"
            ) from e
