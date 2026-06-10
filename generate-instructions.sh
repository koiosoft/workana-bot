#!/bin/bash
# Uso: ./generate-instructions.sh [--interactive|--script] [ruta_config_instructor]
# Si no se da ruta, lista los disponibles en .aider/instructor/ (buscando en script/ e interactive/)
# El modo se deduce automáticamente de la subcarpeta (script -> --script, interactive -> --interactive)
# Si se pasa --interactive o --script, fuerza ese modo y el archivo debe estar en la subcarpeta correspondiente.

DEFAULT_CONFIG_DIR=".aider/instructor"
MODE_FORCED=""
CONFIG_ARG=""

# Procesar argumentos
while [[ $# -gt 0 ]]; do
    case $1 in
        --interactive)
            MODE_FORCED="interactive"
            shift
            ;;
        --script)
            MODE_FORCED="script"
            shift
            ;;
        *)
            if [ -z "$CONFIG_ARG" ]; then
                CONFIG_ARG="$1"
                shift
            else
                echo "❌ Argumento no reconocido: $1"
                exit 1
            fi
            ;;
    esac
done

# Función para listar archivos .yml en script/ e interactive/
list_instructors() {
    local files=()
    if [ -d "$DEFAULT_CONFIG_DIR/script" ]; then
        for f in "$DEFAULT_CONFIG_DIR/script"/*.yml; do
            [ -f "$f" ] && files+=("$f|script")
        done
    fi
    if [ -d "$DEFAULT_CONFIG_DIR/interactive" ]; then
        for f in "$DEFAULT_CONFIG_DIR/interactive"/*.yml; do
            [ -f "$f" ] && files+=("$f|interactive")
        done
    fi
    if [ ${#files[@]} -eq 0 ]; then
        return 1
    fi
    echo "Instructores disponibles:"
    local i=1
    for entry in "${files[@]}"; do
        local file="${entry%|*}"
        local mode="${entry##*|}"
        local name=$(basename "$file")
        echo "  $i) [$mode] $name"
        ((i++))
    done
    # Guardar lista global para usar después
    SELECTED_FILES=()
    for entry in "${files[@]}"; do
        SELECTED_FILES+=("${entry%|*}")
    done
    return 0
}

# Seleccionar configuración
if [ -z "$CONFIG_ARG" ]; then
    if ! list_instructors; then
        echo "❌ No se encontraron configuraciones en $DEFAULT_CONFIG_DIR/{script,interactive}"
        exit 1
    fi
    read -p "Selecciona el número (o 0 para cancelar): " choice
    if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -gt 0 ] && [ "$choice" -le "${#SELECTED_FILES[@]}" ]; then
        INSTRUCTOR_CONFIG="${SELECTED_FILES[$((choice-1))]}"
    else
        echo "❌ Cancelado"
        exit 0
    fi
else
    INSTRUCTOR_CONFIG="$CONFIG_ARG"
    if [[ ! "$INSTRUCTOR_CONFIG" = /* ]]; then
        INSTRUCTOR_CONFIG="$DEFAULT_CONFIG_DIR/$INSTRUCTOR_CONFIG"
    fi
fi

[ ! -f "$INSTRUCTOR_CONFIG" ] && { echo "❌ No existe: $INSTRUCTOR_CONFIG"; exit 1; }
[ ! -f "CUSTOM-PROMPT.txt" ] && { echo "❌ Falta CUSTOM-PROMPT.txt en el directorio actual"; exit 1; }

# Determinar modo automáticamente por la ruta (si no se forzó)
if [ -n "$MODE_FORCED" ]; then
    MODE="$MODE_FORCED"
else
    if [[ "$INSTRUCTOR_CONFIG" == *"/script/"* ]]; then
        MODE="script"
    elif [[ "$INSTRUCTOR_CONFIG" == *"/interactive/"* ]]; then
        MODE="interactive"
    else
        # Preguntar si no está en subcarpeta esperada
        echo "⚠️  El archivo no está en subcarpeta script/ ni interactive/."
        echo "¿Cómo quieres ejecutarlo?"
        echo "1) Scripting (automático, sin leer archivos extra)"
        echo "2) Interactivo (puedes añadir archivos manualmente)"
        read -p "Elige (1/2): " mode_choice
        [ "$mode_choice" = "2" ] && MODE="interactive" || MODE="script"
    fi
fi

# Eliminar INSTRUCTIONS.md previo
[ -f "INSTRUCTIONS.md" ] && { echo "🗑️  Eliminando INSTRUCTIONS.md previo..."; rm -f INSTRUCTIONS.md; }

echo "📝 Usando instructor: $INSTRUCTOR_CONFIG"
echo "🎯 Modo: $MODE"

if [ "$MODE" = "script" ]; then
    aider --config "$INSTRUCTOR_CONFIG" --message-file CUSTOM-PROMPT.txt
    if [ $? -eq 0 ] && [ -f "INSTRUCTIONS.md" ]; then
        echo ""
        echo "✅ INSTRUCTIONS.md generado (modo scripting). Contenido:"
        echo "======================================================"
        cat INSTRUCTIONS.md
        echo "======================================================"
    else
        echo "❌ Falló la generación"
        exit 1
    fi
else
    echo "🚀 Abriendo modo interactivo. Aider se iniciará con tu prompt."
    echo "💡 Puedes usar comandos como /add <archivo> para añadir contexto, luego pide 'Genera INSTRUCTIONS.md'."
    echo "   Cuando termines, escribe /exit para salir."
    echo ""
    aider --config "$INSTRUCTOR_CONFIG" --message "$(cat CUSTOM-PROMPT.txt)"
    echo ""
    if [ -f "INSTRUCTIONS.md" ]; then
        echo "✅ INSTRUCTIONS.md fue generado durante la sesión."
        echo "======================================================"
        cat INSTRUCTIONS.md
        echo "======================================================"
    else
        echo "⚠️  No se encontró INSTRUCTIONS.md. Quizás no lo generaste en el chat."
    fi
fi

echo ""
echo "💡 Ahora ejecuta manualmente el executor, por ejemplo:"
echo "   aider --config .aider/executor/local-qwen14b.yml --file INSTRUCTIONS.md"