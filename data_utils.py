# data_utils.py
import os
import tempfile
from typing import Dict, Any, List
import logging

import httpx
import pandas as pd
import pdfplumber

logger = logging.getLogger(__name__)

async def download_files(file_urls: list[str]) -> dict[str, str]:
    """
    Download each URL to a temp file.
    Returns mapping: {url: local_path}
    """
    logger.info(f"Downloading {len(file_urls)} files")
    downloaded: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=60) as client:
        for i, url in enumerate(file_urls):
            logger.info(f"Downloading file {i+1}/{len(file_urls)}: {url}")
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                logger.info(f"Response status: {resp.status_code}, size: {len(resp.content)} bytes")

                suffix = guess_suffix_from_url(url)
                logger.debug(f"Guessed suffix for {url}: {suffix}")

                fd, path = tempfile.mkstemp(suffix=suffix)
                logger.debug(f"Created temp file: {path}")

                with os.fdopen(fd, "wb") as f:
                    f.write(resp.content)
                downloaded[url] = path
                logger.info(f"Saved file to: {path}")
            except Exception as e:
                logger.error(f"Error downloading file {url}: {e}", exc_info=True)
                raise
    logger.info(f"Successfully downloaded {len(downloaded)} files")
    return downloaded

def guess_suffix_from_url(url: str) -> str:
    logger.debug(f"Guessing suffix for URL: {url}")
    for ext in [".csv", ".xlsx", ".xls", ".pdf"]:
        if url.lower().endswith(ext):
            logger.debug(f"Guessed suffix: {ext}")
            return ext
    logger.debug("No known suffix found")
    return ""

def load_dataframes(downloaded: dict[str, str]) -> dict[str, Any]:
    """
    Load downloaded files into pandas / pdfplumber structures.
    Returns mapping: {url: data}
    where data is:
      - pandas.DataFrame for CSV/Excel
      - dict with pdf info for PDFs
    """
    logger.info(f"Loading {len(downloaded)} downloaded files into dataframes")
    result: dict[str, Any] = {}
    for url, path in downloaded.items():
        logger.info(f"Loading file: {url} from {path}")
        try:
            if path.endswith(".csv"):
                logger.info(f"Loading CSV file: {url}")
                result[url] = pd.read_csv(path)
                logger.info(f"Loaded CSV with shape: {result[url].shape}")
            elif path.endswith((".xlsx", ".xls")):
                logger.info(f"Loading Excel file: {url}")
                result[url] = pd.read_excel(path)
                logger.info(f"Loaded Excel with shape: {result[url].shape}")
            elif path.endswith(".pdf"):
                logger.info(f"Loading PDF file: {url}")
                # For now: extract tables for each page
                with pdfplumber.open(path) as pdf:
                    tables: List = []
                    texts: List[str] = []
                    for page_num, page in enumerate(pdf.pages):
                        text = page.extract_text() or ""
                        texts.append(text)
                        page_tables = page.extract_tables() or []
                        tables.append(page_tables)
                        logger.debug(f"Extracted text from page {page_num+1}, length: {len(text)}")
                        logger.debug(f"Extracted {len(page_tables)} tables from page {page_num+1}")
                    result[url] = {
                        "texts": texts,
                        "tables": tables,  # list[page][table][rows]
                    }
                    logger.info(f"Loaded PDF with {len(texts)} pages and {sum(len(t) for t in tables)} total tables")
            else:
                logger.warning(f"Unknown file type for {url}, keeping raw path: {path}")
                # Unknown type, keep raw path
                result[url] = {"path": path}
        except Exception as e:
            logger.error(f"Error loading file {url} from {path}: {e}", exc_info=True)
            raise

    logger.info(f"Successfully loaded {len(result)} dataframes")
    return result