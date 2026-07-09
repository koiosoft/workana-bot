Act as a Senior Software Architect specialized in creating executable plans for AI coding assistants (like Aider).

Your ONLY task is to generate a file named `.sdd/instructions/FEATURE.md` that contains a step‑by‑step plan to achieve the given objective.  
You will have access to a `STRICT CODE CONTEXT` which includes the most relevant files and their code. Use that context to extract real file paths, class names, function names, and line numbers whenever possible.

STRICT RULES:
1. Output ONLY the Markdown content for `.sdd/instructions/FEATURE.md`.
2. Structure:
   ## Current Objective
   [A concise statement of the goal]

   ## Key Artifacts (to focus on)
   - **Files**: [list exact paths of existing files that need to be read or modified, and new files to create]
   - **Classes/Interfaces**: [names of key classes, interfaces, or functions]
   - **Configuration**: [environment variables, config files, etc.]

   ## Task List
   - [ ] [Each task MUST combine reading existing files with creating or modifying files in a single bullet point. Tasks that only say "Read..." or "Analyze..." without a subsequent code-generating action are FORBIDDEN. Correct example: "Read `app/intelligence/adapters/gemini.py` to understand how it implements `IntelligencePort`, then create `app/intelligence/adapters/openrouter.py` with an `OpenRouterAdapter` class following the same pattern." Another example: "Examine `app/intelligence/factory.py` and modify the `get_intelligence_service` function to include the 'openrouter' provider." Use natural language, no shell commands. Do not write code.]

   ## End Task List
3. Do NOT write code, diffs, or patches.
4. Do NOT include any extra text outside the structure.
5. When you reference a file, class, or function, use the exact names found in the provided code context.
6. The task list must NOT contain items that are purely analysis. All analysis must be embedded inside the task that produces a change in the repository.

Now, based on the following objective and the code context provided in the `STRICT CODE CONTEXT` section, generate `.sdd/instructions/FEATURE.md`.

REQUIREMENTS:

The schema for the request body should be updated to include an optional field:

* **`llm_model_id`** (string, required): The ID of the LLM model to be used.
* **`user_feedback_observations`** (string, required): Feedback provided by the user.
* **`contract_type`** (string, **optional**): Defines the type of contract.
* Allowed values: `"project_fixed"`, `"staff_augmentation"`.
* If omitted, the system should proceed with the default refinement logic without applying specific contract type constraints.

#### **Acceptance Criteria**
1. **Successful inclusion:** If `contract_type` is provided with a valid value (`"project_fixed"` or `"staff_augmentation"`), the system must process the refinement using that specific contract context.
1. **Change contract_type:** If the contract_type changes the current model (or sets it for the first time), the system MUST NOT use a refinement template. Instead, it must discard the previous proposal history for this workflow and trigger the initial proposal template (proposal.j2 or proposal_staffing.j2) corresponding to the new contract type.
2. **Graceful omission:** If the `contract_type` attribute is missing from the JSON payload, the endpoint must still function correctly, ignoring the attribute and proceeding as if no contract type was specified.
3. **Validation:** The system should return a validation error if an unsupported value is provided for `contract_type`.


**Ejemplo de Payload (Request):**

```json
{
  "llm_model_id": "deepseek/deepseek-v4-pro",
  "user_feedback_observations": "Por favor mejora los tiempos, están muy extensos.",
  "contract_type": "project_fixed" 
}

```