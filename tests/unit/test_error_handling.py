import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.bots.telegram.handlers import process_projects
from app.exceptions import AIConnectionError
from app.intelligence.adapters.gemini import GeminiAdapter
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_retries_on_gemini_server_error_and_succeeds():
    with patch("app.intelligence.adapters.gemini.GeminiAdapter", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.generate_proposal.side_effect = [
            AIConnectionError("Server error"),
            {"content": "Proposal"}
        ]

        # Create proper mock Update and Context objects
        update = MagicMock()
        update.effective_user.id = "12345"
        update.message = AsyncMock()
        context = MagicMock()

        await process_projects(update=update, context=context)
