"""
Executor API endpoint
Applies risk engine, safety filters, and executes trades on Binance
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.modules.risk_engine import RiskEngine, SafetyFilter
from app.modules.executor   import BinanceExecutor
from app.modules.telegram   import TelegramNotifier
from app.utils.state        import state_manager
from app.config             import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class ExecuteRequest(BaseModel):
    # From scanner
    symbol: str
    price_change_pct: float
    volume_24h: float
    score: float
    spread_pct: float
    bid: float
    ask: float
    # From analyzer
    current_price: float
    atr: float
    atr_pct: float
    trend_direction: str
    orderbook_bias: str
    suggested_long_sl: float
    suggested_short_sl: float
    # From AI
    decision: str      # BUY | SELL | HOLD
    confidence: int
    risk_level: str
    reason: str


@router.post("/execute")
async def execute_trade(req: ExecuteRequest):
    """
    Main execution endpoint:
    1. Apply risk engine to compute parameters
    2. Run safety filter checks
    3. Execute trade if approved
    4. Send Telegram notification
    """
    telegram = TelegramNotifier()
    state    = state_manager.state

    # ── Early exits ──────────────────────────────────────────────────
    if req.decision == "HOLD":
        await telegram.trade_skipped(req.symbol, f"AI decision: HOLD — {req.reason}")
        return {"status": "skipped", "reason": "AI decided HOLD"}

    if req.confidence < settings.MIN_CONFIDENCE:
        msg = f"Confidence {req.confidence} < minimum {settings.MIN_CONFIDENCE}"
        await telegram.trade_skipped(req.symbol, msg)
        return {"status": "skipped", "reason": msg}

    # ── Risk engine ───────────────────────────────────────────────────
    side = "BUY" if req.decision == "BUY" else "SELL"
    orderbook_sl = (
        req.suggested_long_sl  if side == "BUY" else req.suggested_short_sl
    )

    # Get live balance
    try:
        binance = BinanceExecutor()
        balance = await binance.get_account_balance()
    except Exception:
        balance = settings.ACCOUNT_BALANCE  # Fallback to config

    risk_engine = RiskEngine()
    trade_params = risk_engine.calculate(
        symbol=req.symbol,
        side=side,
        confidence=req.confidence,
        entry_price=req.current_price,
        atr=req.atr,
        orderbook_sl=orderbook_sl,
        account_balance=balance,
    )

    if not trade_params.approved:
        await telegram.trade_skipped(req.symbol, trade_params.reject_reason)
        return {"status": "skipped", "reason": trade_params.reject_reason}

    # ── Safety filter ─────────────────────────────────────────────────
    safety = SafetyFilter(last_traded_symbol=state.last_traded_symbol)
    safety_result = safety.check(
        symbol=req.symbol,
        atr_pct=req.atr_pct,
        spread_pct=req.spread_pct,
        has_open_trade=state.has_open_trade,
        scanner_data={"volume_24h": req.volume_24h},
    )

    if not safety_result.passed:
        reason = " | ".join(safety_result.failed_checks)
        await telegram.trade_skipped(req.symbol, reason)
        return {"status": "skipped", "reason": reason, "checks": safety_result.failed_checks}

    # ── Execute ───────────────────────────────────────────────────────
    result = await binance.execute_trade(trade_params)

    if result.success:
        state_manager.open_trade(req.symbol)
        await telegram.trade_executed(
            symbol=req.symbol,
            side=side,
            qty=trade_params.quantity,
            entry=req.current_price,
            sl=trade_params.stop_loss,
            tp=trade_params.take_profit,
            leverage=trade_params.leverage,
            confidence=req.confidence,
            reason=req.reason,
        )
        return {
            "status": "executed",
            "order_id": result.order_id,
            "symbol": req.symbol,
            "side": side,
            "quantity": trade_params.quantity,
            "entry_price": req.current_price,
            "stop_loss": trade_params.stop_loss,
            "take_profit": trade_params.take_profit,
            "leverage": trade_params.leverage,
            "risk_reward": trade_params.risk_reward,
            "confidence": req.confidence,
        }
    else:
        await telegram.error_alert("Trade Execution", result.error or "Unknown error")
        raise HTTPException(status_code=500, detail=result.error)
