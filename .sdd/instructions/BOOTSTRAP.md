## Current Objective
Update the request body schema to include an optional `contract_type` field and modify the system to handle its validation and processing logic according to the specified acceptance criteria.

## Target Architecture & Conventions (to be established)
- **System Goals**: 
  - Allow optional specification of a contract type (`project_fixed` or `staff_augmentation`) in API requests.
  - Validate the contract type against allowed values and enforce specific processing logic when provided.
  - Ensure backward compatibility by ignoring the `contract_type` field if it is omitted.
  - Gracefully handle invalid contract type values by returning a validation error.
- **High-level Architecture**:
  - **API Layer**: Handles incoming HTTP requests, validates request payloads, and routes to appropriate processing logic.
  - **Processing Layer**: Contains logic to determine whether to apply contract-specific refinement or proceed with the default refinement logic.
  - **Template Engine**: Manages the rendering of proposal templates based on the contract type.
  - **Logging Layer**: Ensures proper logging of contract type processing and validation.
- **Key Conventions**:
  - Use clear and consistent error handling for validation failures.
  - Maintain separation of concerns between validation logic and processing logic.
  - Follow RESTful API design principles for request and response formats.
  - Use descriptive and consistent naming for variables and functions.
- **Technology Stack**:
  - Python (for backend logic).
  - JSON (for request and response payloads).
  - Fabric CLI (for generating instructions and templates).
  - Sentence Transformers (for embedding and similarity calculations in RAG localization).

## Key Artifacts (to focus on)
- **Files**:
  - `instructor.py`: Contains the main logic for processing requests and generating instructions.
  - `.sdd/instructions/BOOTSTRAP.md`: The file to be generated based on the request payload and template logic.
  - `.sdd/inputs/BOOTSTRAP.md`: The template file used to generate `.sdd/instructions/BOOTSTRAP.md`.
  - `.sdd/inputs/REQUIREMENTS.md`: Contains additional requirements used during the generation of `.sdd/instructions/BOOTSTRAP.md`.
  - `.sdd/logs/instruction-generation/fabric_payload_{timestamp}.log`: Log file to store the payload and processing details.
- **Classes/Interfaces**:
  - `instructor.py`: Main module with functions like `call_fabric`, `get_aggregated_specs`, and `run_rag_localization`.
- **Configuration**:
  - `RAG_CONFIG_PATH`: Environmental variable that points to the RAG configuration file.
  - `LOG_PATH`: Environmental variable that specifies the base path for logs.
  - `DEFAULT_VENDOR` and `DEFAULT_MODEL`: Configuration values stored in `~/.config/fabric/.env`.

## Task List
- [ ] Read `instructor.py` to understand how the system processes request payloads and interacts with Fabric, then modify the validation logic to include the new `contract_type` field with the allowed values `"project_fixed"` and `"staff_augmentation"`, and add validation to return an error if an unsupported value is provided.
- [ ] Examine the `call_fabric` function in `instructor.py` and modify the logic to check if `contract_type` is provided and has changed from the current model or is being set for the first time. If so, discard the previous proposal history and use the appropriate template (`proposal.j2` or `proposal_staffing.j2`) based on the new `contract_type`.
- [ ] Analyze the `get_aggregated_specs` function in `instructor.py` and update it to ensure that `.sdd/core/CONVENTIONS.md` and `.sdd/core/SPEC.md` are excluded when the `--bootstrap` command is used.
- [ ] Read the logic for the `--feature` command in `instructor.py` and transfer the validation logic to the `--bootstrap` command, ensuring that it uses the correct templates and instructions from `.sdd/inputs/BOOTSTRAP.md` and `.sdd/inputs/REQUIREMENTS.md`.
- [ ] Modify the `--init` command logic in `instructor.py` to validate that the `BOOTSTRAP.md` file exists in the source `.sdd` directory and copy it to the destination `.sdd` directory, ensuring that the `--bootstrap` command can proceed without errors.
- [ ] Update the logging logic in `instructor.py` to ensure that the log file `fabric_payload_{timestamp}.log` is created in the `.sdd/logs/instruction-generation` directory, and if the directory does not exist, create it before writing the log.

## End Task List