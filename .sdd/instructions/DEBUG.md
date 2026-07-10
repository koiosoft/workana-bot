## Current Objective
Resolve the `RemoteProtocolError` caused by the OpenRouter API server disconnecting unexpectedly during the formatting of project descriptions.

## Task List
- [x] **Error in app/intelligence/adapters/openrouter.py:492**
  - **Error:** `httpx.RemoteProtocolError: Server disconnected without sending a response.`
  - **Context:** The error occurred during an API call to OpenRouter in the `_chat_completion` method when the server closed the connection mid-request without sending a complete response.
  - **Action Required:** 
    1. Identify the `_chat_completion` method in `app/intelligence/adapters/openrouter.py` where the HTTP request to OpenRouter is made.
    2. Add explicit retry logic with exponential backoff for `RemoteProtocolError` and `TimeoutError` exceptions in the `httpx` client call.
    3. Ensure the circuit breaker is updated with the failure/success state after each retry attempt.
    4. Validate that the `OPENROUTER_API_KEY` is correctly configured and has sufficient permissions for the requested operations.
    5. Check network connectivity between the application and OpenRouter's API endpoint to rule out intermittent connectivity issues.
    6. Consider increasing the timeout value for the `httpx.AsyncClient` instance to accommodate potential delays in the OpenRouter service.