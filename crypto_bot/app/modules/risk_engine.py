"""
Simplified Scalping Risk Engine (Hybrid Safe Version)
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# 🔒 Safety limits
MAX_SPREAD_PCT = 0.5
MAX_ATR_PCT = 8.0


@dataclass
class TradeParameters:
    symbol: str
    side: str
    leverage: int
    position_size_usdt: float
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: int
    approved: bool = True
    reject_reason: str = ""


@dataclass
class SafetyCheckResult:
    passed: bool
    reason: str = ""


class RiskEngine:
    """
    Simplified scalping risk engine.
    Fast decisions + basic protection.
    """

    def calculate(
        self,
        symbol: str,
        side: str,
        confidence: int,
        entry_price: float,
        account_balance: float,
        quantity_precision: int = 3,
    ) -> TradeParameters:

        # 🔥 FIXED SAFE SETTINGS
        trade_size = min(2, account_balance * 0.1)

        # 🔥 leverage based on confidence
        if confidence >= 80:
            leverage = 4
        elif confidence >= 65:
            leverage = 3
        else:
            leverage = 2

        # 🔥 SCALPING TP / SL
        take_profit = entry_price * 1.015
        stop_loss   = entry_price * 0.985

        # 🔥 quantity calc
        raw_qty = trade_size / entry_price
        quantity = round(raw_qty, quantity_precision)

        logger.info(
            f"Scalp Trade → {symbol} | lev={leverage}x | size={trade_size}$ | SL={stop_loss} | TP={take_profit}"
        )

        return TradeParameters(
            symbol=symbol,
            side=side,
            leverage=leverage,
            position_size_usdt=round(trade_size, 2),
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=round(stop_loss, 6),
            take_profit=round(take_profit, 6),
            confidence=confidence,
            approved=True,
        )


class SafetyFilter:
    """
    Lightweight safety filter for scalping.
    """

    def check(
        self,
        symbol: str,
        atr_pct: float,
        spread_pct: float,
        has_open_trade: bool,
    ) -> SafetyCheckResult:

        # ❌ avoid multiple trades
        if has_open_trade:
            return SafetyCheckResult(False, "Already in trade")

        # ❌ avoid extreme volatility
        if atr_pct > MAX_ATR_PCT:
            return SafetyCheckResult(False, "Too volatile")

        # ❌ avoid high spread
        if spread_pct > MAX_SPREAD_PCT:
            return SafetyCheckResult(False, "Spread too high")

        # ✅ safe
        return SafetyCheckResult(True, "")
