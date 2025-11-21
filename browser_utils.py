# browser_utils.py
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

async def fetch_quiz_page(url: str) -> tuple[str, str]:
    """
    Returns (html, text) of the fully rendered quiz page.
    """
    logger.info(f"Fetching quiz page: {url}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            logger.info("Launched chromium browser")
            page = await browser.new_page()
            logger.info(f"Navigating to page: {url}")
            await page.goto(url, wait_until="networkidle")
            logger.info("Page loaded, waiting for network idle")
            html = await page.content()
            text = await page.inner_text("body")
            logger.info(f"Retrieved page content - HTML length: {len(html)}, text length: {len(text)}")
            await browser.close()
            logger.info("Browser closed")
        return html, text
    except Exception as e:
        logger.error(f"Error fetching quiz page {url}: {e}", exc_info=True)
        raise