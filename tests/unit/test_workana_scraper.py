"""
Unit tests for the Workana scraper adapter.
Tests parsing logic, pagination, session handling, and error detection.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone
from urllib.parse import urljoin

from app.scraper.adapters.workana import WorkanaScraperAdapter


class TestNormalizeProjectLink:
    """Tests for _normalize_project_link static method."""

    def test_normalize_with_full_url(self):
        """Should return the same URL if already absolute."""
        result = WorkanaScraperAdapter._normalize_project_link("https://www.workana.com/jobs/123")
        assert result == "https://www.workana.com/jobs/123"

    def test_normalize_with_relative_url(self):
        """Should join relative URL with base."""
        result = WorkanaScraperAdapter._normalize_project_link("/jobs/123")
        assert result == "https://www.workana.com/jobs/123"

    def test_normalize_with_none(self):
        """Should return 'N/A' when href is None."""
        result = WorkanaScraperAdapter._normalize_project_link(None)
        assert result == "N/A"

    def test_normalize_with_empty_string(self):
        """Should return 'N/A' when href is empty."""
        result = WorkanaScraperAdapter._normalize_project_link("")
        assert result == "N/A"


class TestIsLoggedIn:
    """Tests for _is_logged_in method."""

    @pytest.mark.asyncio
    async def test_logged_in_when_avatar_present(self):
        """Should return True when .user-avatar element exists."""
        adapter = WorkanaScraperAdapter()
        mock_page = MagicMock()
        mock_page.query_selector = AsyncMock(return_value=MagicMock())
        result = await adapter._is_logged_in(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_not_logged_in_when_avatar_absent(self):
        """Should return False when .user-avatar element is missing."""
        adapter = WorkanaScraperAdapter()
        mock_page = MagicMock()
        mock_page.query_selector = AsyncMock(return_value=None)
        result = await adapter._is_logged_in(mock_page)
        assert result is False


class TestIsProjectNotFound:
    """Tests for _is_project_not_found method."""

    @pytest.mark.asyncio
    async def test_detects_not_found_page(self):
        """Should return True when error-section with 'Proyecto no encontrado' is present."""
        adapter = WorkanaScraperAdapter()
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_locator.inner_text = AsyncMock(return_value="Proyecto no encontrado")
        mock_page.locator.return_value = mock_locator
        result = await adapter._is_project_not_found(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_detects_not_found_with_different_text(self):
        """Should return False when text differs."""
        adapter = WorkanaScraperAdapter()
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_locator.inner_text = AsyncMock(return_value="Página no encontrada")
        mock_page.locator.return_value = mock_locator
        result = await adapter._is_project_not_found(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_detects_not_found_when_no_element(self):
        """Should return False when error-section element is absent."""
        adapter = WorkanaScraperAdapter()
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator
        result = await adapter._is_project_not_found(mock_page)
        assert result is False


class TestAutoScroll:
    """Tests for auto_scroll method."""

    @pytest.mark.asyncio
    async def test_scrolls_five_times(self):
        """Should scroll 5 times with 1.5s waits."""
        adapter = WorkanaScraperAdapter()
        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        await adapter.auto_scroll(mock_page)
        assert mock_page.evaluate.call_count == 5
        assert mock_page.wait_for_timeout.call_count == 5
        mock_page.wait_for_timeout.assert_called_with(1500)


class TestFetchFullDetail:
    """Tests for fetch_full_detail method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_project_not_found(self):
        """Should return None when _is_project_not_found returns True."""
        adapter = WorkanaScraperAdapter()
        with patch.object(adapter, '_is_project_not_found', new_callable=AsyncMock) as mock_not_found:
            mock_not_found.return_value = True
            with patch('app.scraper.adapters.workana.async_playwright') as mock_pw:
                mock_browser = AsyncMock()
                mock_context = AsyncMock()
                mock_page = AsyncMock()
                mock_pw.return_value.__aenter__.return_value.chromium.launch = AsyncMock(return_value=mock_browser)
                mock_browser.new_context = AsyncMock(return_value=mock_context)
                mock_context.new_page = AsyncMock(return_value=mock_page)
                mock_page.goto = AsyncMock()
                mock_page.wait_for_selector = AsyncMock()
                result = await adapter.fetch_full_detail("http://test.com/123")
                assert result is None

    @pytest.mark.asyncio
    async def test_returns_detail_when_project_found(self):
        """Should return detail dict when project exists."""
        adapter = WorkanaScraperAdapter()
        with patch.object(adapter, '_is_project_not_found', new_callable=AsyncMock) as mock_not_found:
            mock_not_found.return_value = False
            with patch('app.scraper.adapters.workana.async_playwright') as mock_pw:
                mock_browser = AsyncMock()
                mock_context = AsyncMock()
                mock_page = AsyncMock()
                mock_pw.return_value.__aenter__.return_value.chromium.launch = AsyncMock(return_value=mock_browser)
                mock_browser.new_context = AsyncMock(return_value=mock_context)
                mock_context.new_page = AsyncMock(return_value=mock_page)
                mock_page.goto = AsyncMock()
                mock_page.wait_for_selector = AsyncMock()
                # Mock locators for detail extraction
                mock_expander = AsyncMock()
                mock_expander.inner_text = AsyncMock(return_value="Full description content")

                mock_extra_details = AsyncMock()
                mock_extra_details.all_text_contents = AsyncMock(return_value=[])

                mock_skills = AsyncMock()
                mock_skills.all_text_contents = AsyncMock(return_value=["Python", "React"])

                mock_budget = AsyncMock()
                mock_budget.inner_text = AsyncMock(return_value="$1000 - $2000")

                def locator_side_effect(selector):
                    if selector == ".expander":
                        return mock_expander
                    elif selector == "article > p.mt20":
                        return mock_extra_details
                    elif selector == ".skills .skill":
                        return mock_skills
                    elif selector == ".budget":
                        return mock_budget
                    return AsyncMock()

                # page.locator() is NOT awaitable; it returns a Locator object.
                # We need a regular MagicMock, not AsyncMock.
                mock_page.locator = MagicMock()
                mock_page.locator.side_effect = locator_side_effect
                result = await adapter.fetch_full_detail("http://test.com/123")
                assert result is not None
                assert "full_description" in result
                assert "skills" in result
                assert "budget_detail" in result
                assert "scraped_at_detail" in result


class TestGetProjects:
    """Tests for get_projects method (high-level)."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_projects(self):
        """Should return empty list when no project items found."""
        adapter = WorkanaScraperAdapter()
        with patch('app.scraper.adapters.workana.async_playwright') as mock_pw:
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            mock_pw.return_value.__aenter__.return_value.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_page.goto = AsyncMock()
            mock_page.wait_for_selector = AsyncMock()
            mock_page.query_selector_all = AsyncMock(return_value=[])
            mock_page.content = AsyncMock(return_value="")
            mock_page.screenshot = AsyncMock()
            mock_context.storage_state = AsyncMock()
            result = await adapter.get_projects()
            assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
