import pytest
from unittest.mock import AsyncMock, patch
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

        await process_projects(update=AsyncMock(), context=AsyncMock())
