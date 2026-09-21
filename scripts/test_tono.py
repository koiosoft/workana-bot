"""Prueba del TONO de la Etapa 3 tras suavizar la plantilla.

Renderiza write-proposal.j2 con un caso ambiguo y llama al PREMIUM, para
inspeccionar el tono del proposal_header y technical_pitch.

Uso:
    docker exec workana_bot python /usr/src/test_tono.py
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, "/usr/src")
from app.intelligence.adapters.openrouter import OpenRouterAdapter  # noqa: E402

load_dotenv()

PROJECT = {
    "title": "Automatizacion de Respuestas en WhatsApp",
    "description": "Se busca un bot de WhatsApp para responder consultas frecuentes y generar informes.",
    "skills_required": ["Python", "API", "Chatbot"],
    "budget_range": "Abierto",
}

# Estimate tipo discovery con un hito pequeño (caso ambiguo)
ESTIMATE = {
    "estimate_type": "discovery",
    "milestones": [
        {
            "step": 1,
            "name": "Configuracion inicial WhatsApp API",
            "tasks": {
                "setup": {"description": "Setup credenciales + webhook", "hours_with_overhead": 8}
            },
            "hours_with_overhead": 8,
            "subtotal": 144.0,
        }
    ],
    "summary": {
        "total_hours": 8,
        "total_budget": 144.0,
        "delivery_time_weeks": 1,
        "hourly_rate_applied": 18,
    },
    "analysis": {
        "maturity_score": 3,
        "maturity_reason": "Requerimiento vago",
        "entities": {"technologies": ["WhatsApp API"], "deliverables": ["Bot"], "constraints": []},
        "gaps": ["Sin stack definido", "Sin flujos"],
        "branch": "discovery",
    },
    "model_used": "test",
    "scope_matrix": {"in_scope": ["Setup inicial"], "out_of_scope": ["Flujos", "Informes"]},
    "discovery_hours": 24,
    "post_discovery_hourly_rate": 18.0,
    "open_questions": ["Que proveedor de API?", "Que flujos?"],
}


async def main() -> None:
    adapter = OpenRouterAdapter()
    adapter.model_id = "deepseek/deepseek-v4-pro-0813"

    prompt = adapter._render_prompt(
        "s3-commercial/write-proposal.j2",
        my_profile_skills=["Python", "FastAPI", "React"],
        hourly_rate=18,
        project_payload_json=json.dumps(PROJECT, indent=2),
        technical_estimate_json=json.dumps(ESTIMATE, indent=2),
    )

    resp = await adapter._chat_completion(prompt, per_attempt_timeout=240.0)
    data = json.loads(adapter._extract_json_object(resp))
    print("=" * 80)
    print("PROPOSAL_HEADER:")
    print(data.get("proposal_header", ""))
    print()
    print("TECHNICAL_PITCH:")
    print(data.get("technical_pitch", ""))
    print()
    print("QUESTIONS:", json.dumps(data.get("questions_for_client", []), ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
