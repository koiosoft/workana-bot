#!/bin/bash
# ssd-prompt.sh

if [ -f "$1" ]; then
    REQUIREMENTS=$(cat "$1")
else
    REQUIREMENTS="$*"
fi

# Usamos un delimitador claro para separar la instrucción del formato del contenido
cat << EOF
Act as a Senior Software Architect. 

Generate the content for INSTRUCTIONS.md based on the requirements below.

REQUIREMENTS:
$REQUIREMENTS

FORMAT RULES:
1. Output ONLY the Markdown content.
2. DO NOT include any conversational filler, explanations, or introductions.
3. Use the following exact structure:

## Current Objective
[A concise statement of the immediate development goal]

## Task List
- [ ] [Task 1]
- [ ] [Task 2]
- [ ] [Task 3]
EOF