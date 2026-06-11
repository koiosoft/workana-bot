#!/usr/bin/env python3
"""
Orquestador Context-Aware de Arquitectura Plana e Independiente.
Utiliza RAG local para indexar archivos de código relevantes según el escenario 
(feature/bug) y compila las instrucciones de desarrollo mediante Fabric CLI.
"""

import datetime
import os
import sys
import json
import tempfile
import shutil
import argparse
import subprocess
from pathlib import Path

# Instalar previamente si faltan: pip install sentence-transformers numpy
from sentence_transformers import SentenceTransformer, util  # type: ignore
import numpy as np  # type: ignore

# --- CONFIGURACIÓN DE RUTAS ---
ORCHESTRATOR_DIR = Path(__file__).resolve().parent
ROOT_DIR = ORCHESTRATOR_DIR.parent

CONVENTIONS_PATH = ROOT_DIR / "CONVENTIONS.md"
FEATURE_PROMPT_PATH = ROOT_DIR / "CUSTOM-PROMPT.txt"
BUG_PROMPT_PATH = ROOT_DIR / "CUSTOM-PROMPT-LOG.txt"
LOG_PATH = ROOT_DIR / "sdd.log"
OUTPUT_PATH = ROOT_DIR / "INSTRUCTIONS.md"

# --- CONSTANTE GLOBAL DE FALLBACK SEGURO (MÍNIMO) ---
DEFAULT_CONFIG = {
    "include_extensions": [".py", ".js", ".ts", ".json", ".md"],
    "exclude_extensions": [],
    "exclude_dirs": ["node_modules", ".git", "venv", "dist", "build", "__pycache__"],
    "max_file_size_bytes": 1048576,        # 1 MB
    "max_chars_for_embedding": 1500,
    "top_n_files": 5,
    "embedding_model": "all-MiniLM-L6-v2",
    "fabric_context_lines": 500
}

def print_step(msg): print(f"\n[\033[94m*\033[0m] {msg}...")
def print_success(msg): print(f"[\033[92m✓\033[0m] {msg}")
def print_warning(msg): print(f"[\033[93m!\033[0m] {msg}")
def print_error(msg): print(f"\n[\033[91mERROR\033[0m] {msg}", file=sys.stderr)

def load_rag_config():
    """Carga la configuración declarativa externa para la indexación."""
    config_path = os.environ.get("RAG_CONFIG_PATH")
    if not config_path:
        config_path = ORCHESTRATOR_DIR / "config.json"
    
    config_file = Path(config_path)
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print_error(f"El archivo de configuración {config_file} contiene errores de sintaxis JSON: {e}")
            sys.exit(1)
            
    print_warning(f"No se localizó '{config_file.name}'. Operando bajo modo de contingencia con parámetros base.")
    return DEFAULT_CONFIG

def verify_fabric():
    """Garantiza la presencia de Fabric CLI en el PATH del sistema."""
    if not shutil.which("fabric"):
        print_error("Fabric CLI no está disponible globalmente en el sistema.")
        print("👉 Instálalo con: pipx install fabric-ai")
        sys.exit(1)
    result = subprocess.run(["fabric", "--help"], capture_output=True, text=True, encoding="utf-8")
    if "pattern" not in result.stdout.lower() and "system" not in result.stdout.lower():
        print_error("Conflicto detectado: El comando 'fabric' pertenece a la herramienta SSH clásica.")
        sys.exit(1)

def run_rag_localization(problem_text, config):
    """Indexa dinámicamente el repositorio de manera local y determinista."""
    include_ext = config.get("include_extensions", DEFAULT_CONFIG["include_extensions"])
    exclude_ext = set(config.get("exclude_extensions", DEFAULT_CONFIG["exclude_extensions"]))
    exclude_dirs = set(config.get("exclude_dirs", DEFAULT_CONFIG["exclude_dirs"]))
    max_size = config.get("max_file_size_bytes", DEFAULT_CONFIG["max_file_size_bytes"])
    max_chars = config.get("max_chars_for_embedding", DEFAULT_CONFIG["max_chars_for_embedding"])
    top_n = config.get("top_n_files", DEFAULT_CONFIG["top_n_files"])
    model_name = config.get("embedding_model", DEFAULT_CONFIG["embedding_model"])

    print(f"DEBUG: exclude_dirs = {exclude_dirs}")

    files = []
    for ext in include_ext:
        if ext in exclude_ext:
            continue
        for p in ROOT_DIR.rglob(f"*{ext}"):
            # Obtener las partes de la ruta relativa respecto a ROOT_DIR para evitar la raíz '/'
            rel_parts = p.relative_to(ROOT_DIR).parts
            # Verificar si alguna parte está en exclude_dirs o empieza con '.'
            if any(part in exclude_dirs or part.startswith('.') for part in rel_parts):
                continue
            if p.is_file() and p.stat().st_size <= max_size:
                files.append(p)

        if not files:
            print_error("La búsqueda RAG no interceptó ningún archivo válido con los criterios proporcionados.")
            return []

    print(f"Indexando {len(files)} archivos locales usando el modelo '{model_name}'...")
    model = SentenceTransformer(model_name)
    prob_emb = model.encode(problem_text, convert_to_tensor=True)

    batch_size = 32
    similarities = []
    
    for i in range(0, len(files), batch_size):
        batch_files = files[i:i+batch_size]
        texts = []
        for f in batch_files:
            try:
                texts.append(f.read_text(encoding='utf-8', errors='ignore')[:max_chars])
            except Exception:
                texts.append("")
                
        batch_embs = model.encode(texts, convert_to_tensor=True)
        sims = util.cos_sim(prob_emb, batch_embs)[0].cpu().numpy()
        similarities.extend(sims)

    similarities = np.array(similarities)
    actual_top_n = min(top_n, len(files))
    top_indices = np.argsort(similarities)[-actual_top_n:][::-1]
    
    selected_files = [str(files[idx].relative_to(ROOT_DIR)) for idx in top_indices]
    print_success(f"Archivos de alta relevancia seleccionados: {', '.join(selected_files)}")
    return selected_files

def create_temp_pattern(system_prompt, pattern_name="custom_pattern"):
    """Crea un patrón temporal de Fabric y retorna la ruta del directorio."""
    temp_dir = tempfile.mkdtemp(prefix="fabric_pattern_")
    pattern_dir = Path(temp_dir) / pattern_name
    pattern_dir.mkdir(parents=True)
    
    # El archivo system.md contiene el prompt del sistema
    system_file = pattern_dir / "system.md"
    system_file.write_text(system_prompt, encoding="utf-8")
    
    # También puede ser necesario un user.md vacío (opcional)
    (pattern_dir / "user.md").write_text("", encoding="utf-8")
    
    return temp_dir, pattern_name

def call_fabric(system_prompt, user_payload):
    pattern_name = "agent_instructor"
    pattern_dir = Path.home() / ".config/fabric/patterns"
    system_file = pattern_dir / pattern_name / "system.md"
    # Sobrescribe el system.md con el prompt actual (dinámico)
    system_file.write_text(system_prompt, encoding="utf-8")

    log_dir = ORCHESTRATOR_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"fabric_payload_{timestamp}.log"
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("=== SYSTEM PROMPT ===\n")
        f.write(system_prompt)
        f.write("\n\n=== USER PAYLOAD ===\n")
        f.write(user_payload)
    print(f"📝 Contexto guardado en: {log_file}")
    
    process = subprocess.Popen(
        ["fabric", "--pattern", pattern_name],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8"
    )
    stdout, stderr = process.communicate(input=user_payload)
    if process.returncode != 0:
        print_error(f"Fabric error: {stderr}")
        sys.exit(1)
    return stdout.strip()

def main():
    rag_config = load_rag_config()
    verify_fabric()
    
    if not CONVENTIONS_PATH.exists():
        print_error("Contrato de diseño ausente: Falta CONVENTIONS.md en la raíz de la app.")
        sys.exit(1)
    conventions = CONVENTIONS_PATH.read_text(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['auto', 'feature', 'bug'], default='feature')
    args = parser.parse_args()

    is_bug = False
    if args.mode == 'feature':
        is_bug = False
        print("[\033[92m+\033[0m] Escenario: FEATURE (par défaut)")
    else:  # modo bug explícito
        is_bug = True
        # Verificar si sdd.log tiene contenido
        if not LOG_PATH.exists() or LOG_PATH.stat().st_size == 0:
            print_warning(f"Modo BUG solicitado pero '{LOG_PATH.name}' está vacío o no existe.")
            print_warning("Continuando sin contenido de log. Asegúrate de que el archivo contenga el error si es necesario.")
        else:
            print(f"[\033[92m+\033[0m] Escenario: BUG (usando {LOG_PATH.name})")

    # Cargar prompts según modo
    if not is_bug:
        system_rules = FEATURE_PROMPT_PATH.read_text(encoding="utf-8")
        target_analisys = system_rules
    else:
        system_rules = BUG_PROMPT_PATH.read_text(encoding="utf-8")
        log_content = ""
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > 0:
            log_content = LOG_PATH.read_text(encoding="utf-8")
        else:
            log_content = "[No se encontró contenido de error en sdd.log]"
        target_analisys = f"LOG DE ERROR:\n{log_content}\n\nDIRECTRICES DE RESOLUCIÓN:\n{system_rules}"

    mode = "bug" if is_bug else "feature"
    print(f"[\033[92m+\033[0m] Escenario operativo determinado: {mode.upper()}")

    if mode == "feature":
        system_rules = FEATURE_PROMPT_PATH.read_text(encoding="utf-8")
        target_analisys = system_rules
    else:
        system_rules = BUG_PROMPT_PATH.read_text(encoding="utf-8")
        target_analisys = f"LOG DE ERROR:\n{LOG_PATH.read_text(encoding='utf-8')}\n\nDIRECTRICES DE RESOLUCIÓN:\n{system_rules}"

    retrieved_files = run_rag_localization(target_analisys, rag_config)

    code_context = ""
    fabric_lines = rag_config.get("fabric_context_lines", DEFAULT_CONFIG["fabric_context_lines"])
    
    for rel_path in retrieved_files:
        file_path = ROOT_DIR / rel_path
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()[:fabric_lines]
            code_context += f"\n--- FILE: {rel_path} ---\n{os.linesep.join(lines)}\n"

    print_step("Fabric: Compilando INSTRUCTIONS.md libre de alucinaciones semánticas")
    user_payload = f"GLOBAL CONVENTIONS:\n{conventions}\n\nSTRICT CODE CONTEXT:\n{code_context}\n\nINPUT DATA:\n{target_analisys}"
    instructions = call_fabric(system_rules, user_payload)

    if instructions:
        OUTPUT_PATH.write_text(instructions, encoding="utf-8")
        print_success(f"Estrategia de desarrollo consolidada en: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()