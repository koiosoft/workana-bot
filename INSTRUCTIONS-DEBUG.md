## Current Objective
Resolve the AI service error occurring during the proposal refinement process, which results in a 502 Bad Gateway response due to a 404 Not Found error from the AI API.

## Task List
- [x] **Error in app/intelligence/adapters/gemini.py:263**
  - **Error:** Error en API de IA durante el refinamiento de propuesta: 404 Not Found. {'message': '', 'status': 'Not Found'}
  - **Context:** The GeminiAdapter's `refine_proposal` method is attempting to call the AI API with a model ID that is not recognized or supported by the service, leading to a 404 error.
  - **Action Required:** Investigate the model ID being passed to the AI API. Ensure that the model ID `deepseek/deepseek-v4-pro` is valid and supported by the AI service. Verify that the model ID is correctly configured in the database and that the intelligence service is correctly mapping the model ID to the appropriate AI API endpoint. Additionally, check for any missing or incorrect configuration in the AI service setup that might be causing the 404 error. Confirm that the AI service is accessible and that there are no network or authentication issues preventing the API call from succeeding.