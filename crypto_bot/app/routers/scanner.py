"""Scanner API endpoint"""

import logging
from fastapi import APIRouter, HTTPException
from app.modules.scanner import MarketScanner

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/scan")
async def scan_market():
    """
    Scan Binance Futures and return top 3 ranked coins.
    Called by n8n every 4 hours.
    """
    try:
        scanner = MarketScanner()
        results = await scanner.scan(top_n=3)
        return {
            "status": "ok",
            "count": len(results),
            "coins": results,
        }
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
