"""Saneamiento determinista de la salida del formateador de descripciones.

Este modulo vive FUERA de los adapters porque la logica es **comun a todos los
providers** (OpenRouter, Gemini): el LLM de cualquiera de ellos puede devolver
un objeto JSON en vez de prosa cuando la llamada viaja con
``response_format={"type":"json_object"}`` (o cuando el modelo simplemente
decide envolver el resultado).

Contexto (bug de produccion): el prompt ``s1-analysis/format-description.j2``
pide PROSA formateada y prohibe resumir/alterar. Pero ``_chat_completion``
forzaba el modo JSON en TODAS las llamadas, de modo que el modelo trataba la
tarea como "devuelve un objeto JSON" y se guardaba el envoltorio crudo como
``full_description``. Sintomas observados en Atlas (79/115 proyectos):

  - ``{"1":""}``, ``{ "version": "1.0" }``, ``{"meta":"","content":[]}``
    -> envoltorio sin el texto.
  - ``{"objetivo":"Reestructurar el texto plano...","lists":"format-lists"}``
    -> ECO de las instrucciones del prompt.
  - ``{"": "No se ha proporcionado un texto en el bloque de descripcion..."}``
    -> PROMPT LEAK (el modelo cree que no recibio texto).

El adapter NO reimplementa este contrato: solo obtiene el texto crudo del
proveedor y delega en :func:`apply_formatted_description`, que sanea la salida
y, si no hay texto plano util, cae a la descripcion original (espejo de
BUGFIX B2). Tanto OpenRouter como Gemini comparten exactamente la misma
validacion, evitando la duplicacion entre adapters.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from loguru import logger

# Fragmentos que delatan que el LLM devolvio el prompt / sus instrucciones en
# vez del resultado. Se comparan en minusculas contra el texto candidato.
_PROMPT_LEAK_MARKERS = (
    "no se ha proporcionado un texto",
    "no se ha proporcionado",
    "por favor, proporciona el texto",
    "por favor proporciona el texto",
    "texto plano, gigante y continuo",
    "reglas indicadas",
    "a continuacion, se presenta el resultado formateado",
    "a continuación, se presenta el resultado formateado",
)

# Marcadores de que el modelo devolvio las CLAVES/esquema de las instrucciones
# ("format-lists", "paragraphs-plain", "descriptionLength", ...) en vez del texto.
_INSTRUCTION_ECHO_MARKERS = (
    "format-lists",
    "paragraphs-plain",
    "descriptionslength",
    "descriptionlength",
    "list-dash",
    "wrap-inline",
)

# Claves tipicas bajo las que varios modelos esconden el texto util.
_TEXT_KEYS = (
    "texto",
    "text",
    "content",
    "contenido",
    "resultado",
    "result",
    "respuesta",
    "descripcion",
    "description",
    "output",
    "markdown",
    "body",
    "cuerpo",
    "json",
    "data",
)


def _collect_strings(value: Any) -> list[str]:
    """Aplana recursivamente *value* y devuelve todos los strings no vacios."""
    out: list[str] = []
    if isinstance(value, str):
        if value.strip():
            out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_collect_strings(v))
    elif isinstance(value, (list, tuple)):
        for v in value:
            out.extend(_collect_strings(v))
    return out


def _looks_like_prompt_leak(text: str) -> bool:
    low = text.lower()
    return any(marker in low for marker in _PROMPT_LEAK_MARKERS)


def _looks_like_instruction_echo(text: str) -> bool:
    low = text.lower()
    # El eco puro suele ser corto y contener varias de estas claves de esquema.
    hits = sum(1 for marker in _INSTRUCTION_ECHO_MARKERS if marker in low)
    return hits >= 1 and len(text) < 400


def _extract_best_text(obj: Any) -> Optional[str]:
    """Devuelve el texto mas largo encontrado dentro del objeto JSON.

    Se prefiere una clave conocida (p. ej. ``texto``/``content``); si ninguna
    existe, se toma el string mas largo de todo el arbol. Se descartan los
    candidatos que son prompt-leak o eco de instrucciones.
    """
    candidates: list[str] = []
    if isinstance(obj, dict):
        for key in _TEXT_KEYS:
            if key in obj:
                candidates.extend(_collect_strings(obj[key]))
    candidates.extend(_collect_strings(obj))

    usable = [
        c
        for c in candidates
        if not _looks_like_prompt_leak(c) and not _looks_like_instruction_echo(c)
    ]
    if not usable:
        return None
    return max(usable, key=len)


def sanitize_formatted_description(raw: str, original: str) -> Optional[str]:
    """Normaliza la salida del formateador de descripciones.

    Devuelve el texto plano formateado, o ``None`` cuando la respuesta no
    contiene texto util (envoltorio vacio, prompt leak o eco de instrucciones),
    en cuyo caso el llamante debe conservar *original*.

    Reglas:
      - Texto plano directo -> se devuelve tal cual (trim).
      - JSON (objeto/array, opcionalmente en bloque ```json) -> se extrae el
        string util mas largo; si no hay, ``None``.
      - Resultado sospechosamente corto (< 50% del original) -> ``None`` para
        evitar reemplazar una descripcion valida por un fragmento mutilado.
    """
    if raw is None:
        return None

    text = raw.strip()
    if not text:
        return None

    # Despojar un posible bloque ```json ... ```
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    candidate: Optional[str] = None
    stripped = text.lstrip()
    if stripped[:1] in "{[":
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            # JSON no parseable: puede ser un envoltorio truncado. Intentamos
            # rescatar strings con un parseo laxo del contenido.
            candidate = _extract_strings_from_broken_json(text)
        else:
            candidate = _extract_best_text(obj)
    else:
        candidate = text

    if not candidate:
        return None

    candidate = candidate.strip()
    if not candidate:
        return None

    if _looks_like_prompt_leak(candidate) or _looks_like_instruction_echo(candidate):
        return None

    # Guarda de longitud: evita reemplazar por un fragmento mutilado.
    if original and len(candidate) < max(1, int(len(original.strip()) * 0.5)):
        return None

    return candidate


def _extract_strings_from_broken_json(text: str) -> Optional[str]:
    """Rescata el string util mas largo de un JSON potencialmente truncado.

    No intenta reconstruir el objeto: solo captura los literales de cadena con
    una regex tolerante a truncamiento y elige el mas largo (filtrando leaks).
    """
    matches = re.findall(r'"((?:[^"\\]|\\.)*)"', text)
    usable: list[str] = []
    for m in matches:
        try:
            decoded = json.loads(f'"{m}"')
        except json.JSONDecodeError:
            decoded = m
        if not decoded.strip():
            continue
        if _looks_like_prompt_leak(decoded) or _looks_like_instruction_echo(decoded):
            continue
        usable.append(decoded)
    if not usable:
        return None
    return max(usable, key=len)


def apply_formatted_description(raw_response: str, original: str) -> str:
    """Contrato COMPARTIDO del formateo de descripciones (todos los adapters).

    Encapsula la politica completa en un unico lugar para no duplicarla entre
    OpenRouter y Gemini (espejo del patron de ``estimate_normalizer``):

      1. Sanea la respuesta cruda del LLM (unwrap de JSON, filtrado de
         prompt-leak/eco, guarda de longitud).
      2. Si hay texto plano util, lo devuelve.
      3. Si no, registra el aviso y devuelve *original* (nunca persistir basura).

    Los adapters NO deben reimplementar este bloque: solo obtener el texto
    crudo del proveedor y delegar aqui.
    """
    formatted = sanitize_formatted_description(raw_response, original)
    if formatted:
        logger.success("✅ Descripción formateada exitosamente.")
        return formatted

    logger.warning(
        "La IA de formateo no devolvió texto plano útil (vacío/JSON/leak). "
        "Usando descripción original."
    )
    return original


def classify_damaged_description(full_description: Optional[str]) -> str:
    """Clasifica el estado de un ``full_description`` ya persistido.

    Reutiliza las MISMAS heuristicas que el saneador en vivo, para que el
    criterio de remediacion y el del pipeline no diverjan. Devuelve una de:

      - ``"missing"``      : el campo no existe (None).
      - ``"empty"``        : existe pero es cadena vacia/whitespace.
      - ``"json_wrapper"`` : es un objeto/array JSON (con o sin texto dentro).
      - ``"broken_json"``  : empieza con '{'/'[' pero no parsea.
      - ``"prompt_leak"``  : contiene texto de fuga del prompt.
      - ``"instruction_echo"`` : devuelve las claves/esquema de instrucciones.
      - ``"ok"``           : texto plano legible (Markdown incluido).
    """
    if full_description is None:
        return "missing"

    text = full_description.strip()
    if not text:
        return "empty"

    if _looks_like_prompt_leak(text):
        return "prompt_leak"
    if _looks_like_instruction_echo(text):
        return "instruction_echo"

    if text[:1] in "{[":
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return "broken_json"
        # El envoltorio es JSON; refinamos mirando SU CONTENIDO, porque puede
        # ser un eco de instrucciones o una fuga del prompt embebida.
        inner = " ".join(_collect_strings(obj))
        if _looks_like_prompt_leak(inner):
            return "prompt_leak"
        if _looks_like_instruction_echo(inner):
            return "instruction_echo"
        return "json_wrapper"

    return "ok"


def is_damaged_description(full_description: Optional[str]) -> bool:
    """True si el ``full_description`` NO es texto plano legible."""
    return classify_damaged_description(full_description) != "ok"
