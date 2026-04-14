"""
Smart Scalping Risk Engine (Dynamic + Profit Optimized)
"""

import logging
from dataclasses import dataclass

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
    Smart scalping risk engine.
    Dynamic TP/SL + adaptive leverage + better profit margins.
    """

    def calculate(
        self,
        symbol: str,
        side: str,
        confidence: int,
        entry_price: float,
        account_balance: float,
        atr_pct: float = 1.0,
        quantity_precision: int = 3,
    ) -> TradeParameters:

        # 🔥 dynamic trade size
        trade_size = max(2, account_balance * 0.1)

        # 🔥 leverage tuning
        if confidence >= 80:
            leverage = 5
        elif confidence >= 65:
            leverage = 4
        else:
            leverage = 3

        # 🔥 volatility factor (ATR)
        volatility = atr_pct / 100 if atr_pct else 0.01

        # 🔥 TP/SL (fees-aware)
        tp_multiplier = 2.0 + (confidence / 100)   # 2.0 → 3.0 range
        sl_multiplier = 1.2

        take_profit = entry_price * (1 + volatility * tp_multiplier)
        stop_loss   = entry_price * (1 - volatility * sl_multiplier)

        # 🔥 quantity calculation
        raw_qty = trade_size / entry_price
        quantity = round(raw_qty, quantity_precision)

        logger.info(
            f"SMART Trade → {symbol} | lev={leverage}x | size={trade_size}$ | SL={stop_loss} | TP={take_profit}"
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
