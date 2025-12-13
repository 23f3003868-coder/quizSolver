# tools/visualize_tool.py
import logging
from typing import Dict, Any
import pandas as pd

logger = logging.getLogger(__name__)

async def visualize_data(data: Dict[str, Any], visualization_type: str = "summary") -> Dict[str, Any]:
    """
    Generate visualizations or summaries of data.
    
    Args:
        data: Dictionary mapping URLs to data objects
        visualization_type: Type of visualization ('summary', 'plot', etc.)
        
    Returns:
        Dictionary with visualization information
    """
    logger.info(f"Visualizing data with type: {visualization_type}")
    
    summaries = {}
    for url, obj in data.items():
        if isinstance(obj, pd.DataFrame):
            summaries[url] = {
                "type": "dataframe",
                "shape": obj.shape,
                "columns": list(obj.columns),
                "dtypes": obj.dtypes.to_dict(),
                "head": obj.head().to_dict() if len(obj) > 0 else {}
            }
        elif isinstance(obj, dict):
            if "texts" in obj and "tables" in obj:
                summaries[url] = {
                    "type": "pdf",
                    "pages": len(obj["texts"]),
                    "tables": sum(len(t) for t in obj["tables"])
                }
            else:
                summaries[url] = {
                    "type": "json",
                    "keys": list(obj.keys()) if isinstance(obj, dict) else "list"
                }
        else:
            summaries[url] = {
                "type": type(obj).__name__,
                "value": str(obj)[:100]  # Truncate long values
            }
    
    logger.info(f"Generated summaries for {len(summaries)} data sources")
    return {
        "summaries": summaries,
        "visualization_type": visualization_type
    }

