"""Prueba DIRECTA del comportamiento de _chat_completion con el fix de latencia.

No toca el pipeline ni Mongo: llama al LLM con un prompt representativo de la
Etapa 3 (grande) y mide tiempo / tokens / exito. Util para validar:

  - `max_tokens` acota la salida.
  - `reasoning.enabled=false` evita tokens de pensamiento.
  - el timeout por intento es suficiente.

Uso:
    docker exec workana_bot python /usr/src/test_llm_direct.py
    docker exec workana_bot python /usr/src/test_llm_direct.py --model <id>
"""

import asyncio
import os
import sys
import time

from dotenv import load_dotenv

sys.path.insert(0, "/usr/src")
from app.intelligence.adapters.openrouter import OpenRouterAdapter  # noqa: E402

load_dotenv()


# Prompt representativo de la Etapa 3: instrucciones comerciales + datos +
# JSON acumulado del estimate. Se exagera un poco para simular el peor caso.
PROMPT = (
    "Actua como un Arquitecto de Software Senior. Redacta SOLO los campos "
    "comerciales (proposal_header, technical_pitch, questions_for_client) en "
    "JSON estricto, sin prosa extra ni markdown.\n\n"
    + ("Datos del proyecto y estimacion tecnica (milestones con horas): "
       "Hito 1 Backend 13h; Hito 2 Playwright 18h; Hito 3 Alertas 13h; "
       "Hito 4 Deploy 14h. Total 58h a 18 USD/h = 1044 USD.\n" * 250)
    + "\nDevuelve el JSON."
)


async def main() -> None:
    model_override = None
    if "--model" in sys.argv:
        model_override = sys.argv[sys.argv.index("--model") + 1]

    adapter = OpenRouterAdapter()
    if model_override:
        adapter.model_id = model_override
    # Modelo PREMIUM (el que fallaba).
    adapter.model_id = model_override or adapter._premium_model_override or adapter.model_id

    print(f"=== Prueba directa _chat_completion ===")
    print(f"  modelo        : {adapter.model_id}")
    print(f"  prompt chars  : {len(PROMPT)} (~{len(PROMPT)//4} tokens)")
    print(f"  MAX_OUTPUT_TOKENS env: {os.getenv('MAX_OUTPUT_TOKENS', '(no set, default 2000)')}")
    print(f"  timeout intento: 240s (Etapa 3)")
    print()

    t0 = time.time()
    try:
        resp = await adapter._chat_completion(PROMPT, per_attempt_timeout=240.0)
        dt = time.time() - t0
        print(f"  RESULTADO: OK en {dt:.1f}s")
        print(f"  respuesta chars: {len(resp)} (~{len(resp)//4} tokens)")
        print(f"  primeros 200   : {resp[:200]!r}")
    except Exception as e:
        dt = time.time() - t0
        print(f"  RESULTADO: FALLO en {dt:.1f}s -> {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
