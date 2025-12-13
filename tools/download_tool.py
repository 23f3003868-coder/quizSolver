# tools/download_tool.py
import os
import tempfile
import logging
from typing import Dict, Any, List
import httpx
import pandas as pd
import pdfplumber
import json

logger = logging.getLogger(__name__)

async def download_file(url: str, email: str = None, secret: str = None) -> Dict[str, Any]:
    """
    Download a file from a URL and load it into a usable format.
    
    Supports:
    - CSV files → pandas.DataFrame
    - Excel files → pandas.DataFrame
    - PDF files → dict with 'texts' and 'tables'
    - JSON files → parsed JSON object
    
    Args:
        url: The URL to download from
        email: Optional email for authenticated requests
        secret: Optional secret for authenticated requests
        
    Returns:
        Dictionary with 'data' key containing the loaded data and 'type' indicating the format
    """
    logger.info(f"Downloading file: {url}")
    
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            # Add authentication if provided
            params = {}
            if email and secret:
                params['email'] = email
                params['secret'] = secret
            
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            
            # Determine file type from URL or content
            suffix = _guess_suffix_from_url(url)
            
            # Save to temp file
            fd, path = tempfile.mkstemp(suffix=suffix)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(resp.content)
                
                # Load based on file type
                if path.endswith(".csv"):
                    data = pd.read_csv(path)
                    data_type = "dataframe"
                    logger.info(f"Loaded CSV with shape: {data.shape}")
                elif path.endswith((".xlsx", ".xls")):
                    data = pd.read_excel(path)
                    data_type = "dataframe"
                    logger.info(f"Loaded Excel with shape: {data.shape}")
                elif path.endswith(".pdf"):
                    with pdfplumber.open(path) as pdf:
                        tables = []
                        texts = []
                        for page in pdf.pages:
                            text = page.extract_text() or ""
                            texts.append(text)
                            page_tables = page.extract_tables() or []
                            tables.append(page_tables)
                    data = {
                        "texts": texts,
                        "tables": tables
                    }
                    data_type = "pdf"
                    logger.info(f"Loaded PDF with {len(texts)} pages")
                elif path.endswith((".json", ".jsonl")):
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    data_type = "json"
                    logger.info(f"Loaded JSON data")
                else:
                    # Unknown type, return raw content
                    with open(path, 'rb') as f:
                        data = f.read()
                    data_type = "raw"
                    logger.warning(f"Unknown file type for {url}, returning raw content")
                
                return {
                    "data": data,
                    "type": data_type,
                    "url": url
                }
            finally:
                # Clean up temp file
                try:
                    os.unlink(path)
                except:
                    pass
                    
    except Exception as e:
        logger.error(f"Error downloading file {url}: {e}", exc_info=True)
        raise

def _guess_suffix_from_url(url: str) -> str:
    """Guess file suffix from URL."""
    for ext in [".csv", ".xlsx", ".xls", ".pdf", ".json", ".jsonl"]:
        if url.lower().endswith(ext):
            return ext
    return ""

