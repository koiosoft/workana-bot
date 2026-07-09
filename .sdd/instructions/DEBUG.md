## Current Objective
Debug and resolve the 502 Bad Gateway error encountered during the refinement of a staff augmentation proposal, which originates from a 404 Not Found error in the AI service.

## Task List
- [x] **Error in app/api/routes/proposals.py:124**
  - **Error:** Refinement failed for project 6a4f9e64f1ebc6a8f407c278: La API de IA falló durante el refinamiento de propuesta: 404 Not Found.
  - **Context:** The error occurs when calling the intelligence service to refine a proposal, which results in a 404 Not Found error from the AI API.
  - **Action Required:** Investigate the `refine_proposal_intel` function call to ensure the correct model ID and contract type are passed. Confirm that the intelligence adapter is correctly initialized and that the model ID "deepseek/deepseek-v4-pro" exists in the database or is supported by the adapter. Additionally, verify that the contract type "staff_augmentation" is properly handled by the adapter's refine method.

- [x] **Error in app/intelligence/factory.py:154**
  - **Error:** ⚠️ Model 'deepseek/deepseek-v4-pro' not found in DB — falling back to STANDARD adapter
  - **Context:** The model ID "deepseek/deepseek-v4-pro" is not found in the `models` collection, so the fallback to the STANDARD adapter is triggered.
  - **Action Required:** Check the `models` collection in the database to confirm that the model "deepseek/deepseek-v4-pro" is correctly registered with the appropriate provider key. If it is not present, either add the model to the database or ensure the test environment includes this model for the test to pass.

- [x] **Error in app/intelligence/adapters/gemini:refine_proposal:340**
  - **Error:** Error en API de IA durante el refinamiento de propuesta: 404 Not Found.
  - **Context:** The AI service returns a 404 Not Found error when attempting to refine the proposal using the fallback STANDARD adapter.
  - **Action Required:** Verify that the STANDARD adapter is correctly configured and that the model it uses is accessible. Confirm that the adapter's API endpoint is reachable and that the model ID used by the STANDARD adapter is valid and properly registered in the database. Additionally, ensure that the adapter's refine method is correctly handling the contract type and proposal data.

- [x] Check unit tests and fix them if thear errors.
- [x] Check integration tests and fix them if thear errors.