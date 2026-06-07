#!/bin/bash
# sdd.sh

LOG_FILE="LOG.md"
SDD_FILE="sdd.log"
TASK_FILE="INSTRUCTIONS.md"
FECHA_HORA=$(date "+%Y-%m-%d %H:%M:%S")

# Caso A: El archivo sdd.log TIENE un error
if [ -s "$SDD_FILE" ]; then
    
    # 1. Preparar el log de resolución
    echo "# Fix Report - $FECHA_HORA" > "$LOG_FILE"
    echo "- **Origin:** Error detected in \`$SDD_FILE\`" >> "$LOG_FILE"
    echo "- **Resolution:**" >> "$LOG_FILE"

    # 2. Instrucciones para Aider (Output de texto para la sesión actual)
    echo "---"
    echo "AN ERROR OCCURRED."
    echo "Please analyze the following error content from $SDD_FILE:"
    echo "---"
    cat "$SDD_FILE"
    echo "---"
    echo "1. Fix the code causing this error."
    echo "2. Reference $TASK_FILE to ensure the fix aligns with current goals."
    echo "3. Append the technical resolution directly into the \"- **Resolution:** \" section of $LOG_FILE. Keep the resolution concise and technical."
    echo "---"

    # 3. Limpiar sdd.log después de pasar el error al prompt de Aider
    > "$SDD_FILE"

# Caso B: El archivo sdd.log está VACÍO
else
    echo "Check $TASK_FILE for pending tasks..."
    # Opcional: leer el archivo de tareas si está vacío
    cat "$TASK_FILE"
fi