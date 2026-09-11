#!/usr/bin/env python3
"""
Exporta la sesion de Workana desde Chrome real y la convierte para el scraper.

Workana usa Cloudflare, que bloquea a Playwright headless. La solucion es
exportar las cookies desde Chrome normal (que ya paso el challenge) e
inyectarselas al scraper.

Uso:
    python scripts/export_session.py                     # Muestra la guia
    python scripts/export_session.py --help              # Esta ayuda
    python scripts/export_session.py <archivo_cookies>   # Convierte y copia

El archivo de cookies puede ser:
  - Formato Netscape (.txt)  -- de la extension "Get cookies.txt"
  - Formato JSON (.json)     -- de la extension "EditThisCookie"

Ejemplos:
    python scripts/export_session.py ~/Downloads/www.workana.com_cookies.txt
    python scripts/export_session.py ~/Desktop/EditThisCookie.json
"""
import json
import os
import sys

GUIDE = """
╔══════════════════════════════════════════════════════════╗
║           EXPORTAR SESION DE WORKANA                    ║
║   (para omitir Cloudflare en el scraper headless)        ║
╚══════════════════════════════════════════════════════════╝

Paso 1: Abre Chrome normal (NO Playwright, Chrome de verdad)
Paso 2: Ve a https://www.workana.com
Paso 3: Si aparece Cloudflare, resuelve el challenge (checkbox)
Paso 4: Inicia sesion en Workana con tu usuario y contrasena
Paso 5: Instala una extension para exportar cookies:
        • "Get cookies.txt"  → Chrome Web Store (recomendada)
        • "EditThisCookie"   → Chrome Web Store (alternativa)

Paso 6: Exporta las cookies haciendo clic en la extension:
        • Get cookies.txt  → guarda como .txt (formato Netscape)
        • EditThisCookie    → Export → guarda como .json

Paso 7: Ejecuta este script pasando el archivo exportado:

    python scripts/export_session.py ~/Downloads/workana_cookies.txt

Paso 8: Responde "si" cuando pregunte si copiar al contenedor.

La sesion expira eventualmente. Repite cuando el bot deje de
encontrar proyectos.
"""

def detect_format(path):
    """Detecta si es formato Netscape (.txt) o EditThisCookie JSON (.json)."""
    with open(path) as f:
        head = f.read(2048)
    if head.strip().startswith("["):
        return "editthis"
    if head.strip().startswith("{"):
        return "editthis"
    return "netscape"


def convert_editthis(input_path, output_path):
    """Convierte JSON de EditThisCookie a storage_state de Playwright."""
    with open(input_path) as f:
        raw = json.load(f)

    # Deduplicar: (name, domain_sin_punto) → ultima gana, prefiriendo www
    seen = {}
    for c in raw:
        domain = c.get("domain", "")
        key = (c["name"], domain.lstrip("."))
        if key in seen:
            if "www" in domain and "www" not in seen[key].get("domain", ""):
                seen[key] = c
        else:
            seen[key] = c

    cookies = []
    for c in seen.values():
        domain = c.get("domain", "").lstrip(".")
        same_site_map = {"lax": "Lax", "strict": "Strict", "unspecified": "None"}
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": domain,
            "path": c.get("path", "/"),
            "sameSite": same_site_map.get(c.get("sameSite", "lax"), "Lax"),
            "secure": c.get("secure", False),
            "httpOnly": c.get("httpOnly", False),
        }
        if "expirationDate" in c and not c.get("session", False):
            cookie["expires"] = int(c["expirationDate"])
        cookies.append(cookie)

    return cookies


def convert_netscape(input_path, output_path):
    """Convierte Netscape cookies.txt a storage_state de Playwright."""
    cookies = []
    with open(input_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                domain, _, path, secure, expires, name, value = parts[:7]
                cookies.append({
                    "domain": domain.lstrip("."),
                    "name": name,
                    "value": value,
                    "path": path,
                    "sameSite": "Lax",
                    "secure": secure == "TRUE",
                    "httpOnly": False,
                    "expires": int(expires),
                })
    return cookies


def write_output(cookies, output_path):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    state = {"cookies": cookies, "origins": []}
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2)
    print(f"\n  ✅ {len(cookies)} cookies convertidas a {output_path}")
    return output_path


def copy_to_container(path):
    container = "workana_bot"
    dest = f"{container}:/usr/src/app/state.json"
    print(f"\n  📦 Copiando al contenedor {container}...")
    ret = os.system(f"docker cp {path} {dest} 2>&1")
    if ret != 0:
        print(f"  ⚠️  No se pudo copiar. Asegurate de que el contenedor 'workana_bot' exista.")
        print(f"     Para copiarlo manualmente: docker cp {path} {dest}")
        return False
    print(f"  ✅ Archivo copiado a {dest}")
    print(f"\n  🔄 Reiniciando contenedor...")
    os.system(f"docker restart {container} 2>&1")
    print(f"  ✅ Contenedor reiniciado. La sesion esta activa.")
    return True


def main():
    if "--help" in sys.argv or "-h" in sys.argv or len(sys.argv) < 2:
        print(__doc__.strip())
        print(GUIDE)
        sys.exit(0)

    input_path = sys.argv[1]

    if not os.path.exists(input_path):
        print(f"❌ Archivo no encontrado: {input_path}")
        print(GUIDE)
        sys.exit(1)

    # Detectar formato
    fmt = detect_format(input_path)
    name = os.path.basename(input_path)
    print(f"\n  📄 Detectado: {name} ({'EditThisCookie' if fmt == 'editthis' else 'Get cookies.txt'} formato)")

    # Convertir
    output_path = os.path.join("app", "state.json")
    if fmt == "editthis":
        cookies = convert_editthis(input_path, output_path)
    else:
        cookies = convert_netscape(input_path, output_path)

    write_output(cookies, output_path)

    # Preguntar si copiar al contenedor
    print(f"\n  ❓ Copiar al contenedor workana_bot y reiniciar? (s/n)")
    try:
        ans = input("  > ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = "n"

    if ans in ("s", "si", "y", "yes"):
        copy_to_container(output_path)
    else:
        print(f"\n  Para copiarlo manualmente luego:")
        print(f"    docker cp {output_path} workana_bot:/usr/src/app/state.json")
        print(f"    docker-compose restart workana_bot")


if __name__ == "__main__":
    main()