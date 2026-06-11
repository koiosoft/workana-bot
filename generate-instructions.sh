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
[ -f "INSTRUCTIONS.md" ] && { echo "🗑️  Reiniciando INSTRUCTIONS.md..."; rm -f INSTRUCTIONS.md; }
touch INSTRUCTIONS.md

echo "📝 Usando instructor: $INSTRUCTOR_CONFIG"
echo "🎯 Modo: $MODE"

if [ "$MODE" = "script" ]; then
    echo "📝 Generando INSTRUCTIONS.md..."
    echo ""

    # Quitamos --no-stream para que veas la generación en vivo en tu terminal
    aider --config "$INSTRUCTOR_CONFIG" \
          --message-file CUSTOM-PROMPT.txt \
          --chat-mode ask \
          --no-show-model-warnings \
          --no-pretty \
          --stream \
          2>&1 | tee /tmp/aider_output.txt

    exit_code=${PIPESTATUS[0]}  # Capturar código de salida de aider (no de tee)
    echo ""
    echo "Código de salida: $exit_code"

    if [ $exit_code -eq 0 ]; then
        echo "🧹 Filtrando la última respuesta válida..."

        # 1. Eliminamos el bloque de pensamiento <think> completo si existiera
        sed -e '/<think>/,/\<\/think\>/d' /tmp/aider_output.txt > /tmp/no_think.md

        # 2. Buscamos la ÚLTIMA línea que contenga "## Current Objective" (sin importar mayúsculas)
        LAST_MATCH_LINE=$(grep -in "## [Cc]urrent [Oo]bjective" /tmp/no_think.md | tail -n 1 | cut -d: -f1)

        if [ -n "$LAST_MATCH_LINE" ]; then
            # Extraemos desde esa última línea detectada hasta el final del archivo
            tail -n +"$LAST_MATCH_LINE" /tmp/no_think.md > /tmp/raw_instructions.md
        else
            # Si por alguna razón falló el corte, tomamos el archivo limpio completo
            cat /tmp/no_think.md > /tmp/raw_instructions.md
        fi

        # 3. Limpieza Quirúrgica: Nos aseguramos de borrar las líneas de control de Aider 
        # y los reportes de tokens que Qwen mete al final, cortando JUSTO en "## End Task List"
        sed -n '1,/## End Task List/p' /tmp/raw_instructions.md > INSTRUCTIONS.md

        if [ -s INSTRUCTIONS.md ]; then
            echo ""
            echo "✅ INSTRUCTIONS.md generado con éxito."
            echo "📄 Tamaño: $(wc -l < INSTRUCTIONS.md) líneas, $(wc -c < INSTRUCTIONS.md) bytes."
        else
            echo "❌ El archivo generado está vacío. Revisa la salida de aider."
            exit 1
        fi
    else
        echo "❌ Aider falló con código $exit_code. Revisa el mensaje de error de arriba."
        exit 1
    fi
else
    echo "🚀 Abriendo modo interactivo. Aider se iniciará con tu prompt."
    echo "💡 Puedes usar comandos como /add <archivo> para añadir contexto, luego pide 'Genera INSTRUCTIONS.md'."
    echo "   Cuando termines, escribe /exit para salir."
    echo ""
    aider --config "$INSTRUCTOR_CONFIG" --message "$(cat CUSTOM-PROMPT.txt)" --no-show-model-warnings
    # Extraer el contenido Markdown (desde "## Current Objective" hasta el final)
    sed -n '/^## Current Objective/,$p' /tmp/aider_output.txt > INSTRUCTIONS.md
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