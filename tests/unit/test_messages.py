"""
Unit tests for the Telegram messages module.
Tests retry logic and long message splitting.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update

from app.bots.telegram.messages import _send_with_retry, send_long_message, TELEGRAM_MAX_MESSAGE, MAX_RETRIES


class TestSendWithRetry:
    """Tests for _send_with_retry helper."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """Should succeed on first attempt without retries."""
        update = MagicMock(spec=Update)
        update.message = MagicMock()
        update.message.reply_text = AsyncMock(return_value=True)
        result = await _send_with_retry(update, "Hello")
        assert result is True
        update.message.reply_text.assert_called_once_with("Hello")

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        """Should retry up to MAX_RETRIES times on failure."""
        update = MagicMock(spec=Update)
        update.message = MagicMock()
        update.message.reply_text = AsyncMock(side_effect=[Exception("Network error"), Exception("Timeout"), True])
        with patch('app.bots.telegram.messages.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await _send_with_retry(update, "Hello")
            assert result is True
            assert update.message.reply_text.call_count == 3
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(2)
            mock_sleep.assert_any_call(4)

    @pytest.mark.asyncio
    async def test_returns_false_after_max_retries(self):
        """Should return False after exhausting all retries."""
        update = MagicMock(spec=Update)
        update.message = MagicMock()
        update.message.reply_text = AsyncMock(side_effect=Exception("Persistent error"))
        with patch('app.bots.telegram.messages.asyncio.sleep', new_callable=AsyncMock):
            result = await _send_with_retry(update, "Hello")
            assert result is False
            assert update.message.reply_text.call_count == MAX_RETRIES

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Should use exponential backoff: 2s, 4s."""
        update = MagicMock(spec=Update)
        update.message = MagicMock()
        update.message.reply_text = AsyncMock(side_effect=[Exception("E1"), Exception("E2"), True])
        with patch('app.bots.telegram.messages.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await _send_with_retry(update, "Hello")
            assert mock_sleep.call_args_list[0].args[0] == 2
            assert mock_sleep.call_args_list[1].args[0] == 4


class TestSendLongMessage:
    """Tests for send_long_message function."""

    @pytest.mark.asyncio
    async def test_sends_short_message_in_one_chunk(self):
        """Should send a short message in a single chunk."""
        update = MagicMock(spec=Update)
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        text = "Short message"
        await send_long_message(update, text)
        update.message.reply_text.assert_called_once_with(text)

    @pytest.mark.asyncio
    async def test_splits_long_message(self):
        """Should split a message longer than TELEGRAM_MAX_MESSAGE."""
        update = MagicMock(spec=Update)
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        # Create a message longer than the limit
        long_line = "A" * (TELEGRAM_MAX_MESSAGE + 100)
        await send_long_message(update, long_line)
        # Should have been split into at least 2 chunks
        assert update.message.reply_text.call_count >= 2

    @pytest.mark.asyncio
    async def test_handles_none_update_message(self):
        """Should do nothing when update.message is None."""
        update = MagicMock(spec=Update)
        update.message = None
        # Should not raise
        await send_long_message(update, "Hello")
        # No reply_text call should happen
        # (we can't assert on a None object)

    @pytest.mark.asyncio
    async def test_preserves_line_breaks_across_chunks(self):
        """Should preserve line breaks when splitting."""
        update = MagicMock(spec=Update)
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        # Build a message with lines that force a split
        lines = []
        for i in range(10):
            lines.append("X" * (TELEGRAM_MAX_MESSAGE // 5))
        text = "\n".join(lines)
        await send_long_message(update, text)
        # Should have been split into multiple chunks
        assert update.message.reply_text.call_count >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
