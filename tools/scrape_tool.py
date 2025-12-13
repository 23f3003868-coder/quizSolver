# tools/scrape_tool.py
import logging
from typing import Dict, Any
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

async def scrape_web_page(url: str) -> Dict[str, Any]:
    """
    Scrape a web page using Playwright to get fully rendered HTML and text.
    
    Args:
        url: The URL to scrape
        
    Returns:
        Dictionary with 'html' and 'text' keys
    """
    logger.info(f"Scraping web page: {url}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle")
            html = await page.content()
            text = await page.inner_text("body")
            await browser.close()
            
            logger.info(f"Successfully scraped page: {url}, HTML length: {len(html)}, text length: {len(text)}")
            return {
                "html": html,
                "text": text,
                "url": url
            }
    except Exception as e:
        logger.error(f"Error scraping web page {url}: {e}", exc_info=True)
        raise

