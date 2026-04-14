"""
Analyzer API endpoint
Full analysis pipeline: indicators + order book + AI decision
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.modules.analyzer  import TechnicalAnalyzer
from app.modules.orderbook import OrderBookAnalyzer
from app.modules.ai_engine import AIDecisionEngine

router = APIRouter()
logger = logging.getLogger(__name__)


class AnalyzeRequest(BaseModel):
    symbol: str
    price_change_pct: float = 0.0
    volume_24h: float = 0.0
    score: float = 0.0
    spread_pct: float = 0.0
    bid: float = 0.0
    ask: float = 0.0


@router.post("/analyze")
async def analyze_coin(req: AnalyzeRequest):
    """
    Full analysis for a single coin:
    1. Technical indicators
    2. Order book analysis
    3. AI decision
    """
    try:
        # 1. Technical Analysis
        tech = TechnicalAnalyzer()
        ind_result = await tech.analyze(req.symbol)
        indicators = tech.to_dict(ind_result)

        # 2. Order Book Analysis
        ob = OrderBookAnalyzer()
        ob_result = await ob.analyze(req.symbol, ind_result.current_price)
        orderbook = ob.to_dict(ob_result)

        # 3. AI Decision
        ai = AIDecisionEngine()
        ai_result = await ai.decide(indicators, orderbook, req.dict())
        decision = ai.to_dict(ai_result)

        return {
            "status": "ok",
            "symbol": req.symbol,
            "indicators": indicators,
            "orderbook": orderbook,
            "ai_decision": decision,
        }

    except Exception as e:
        logger.error(f"Analysis failed for {req.symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
