"""
Dynamic Risk Engine & Safety Filter Layer
Computes leverage, position size, SL/TP based on AI confidence.
Applies pre-trade safety checks.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

# Safety limits
MAX_ATR_PCT   = 8.0   # Skip if ATR% > 8% (extreme volatility)
MAX_SPREAD_PCT = 0.3  # Tighter check at execution time
MIN_VOLUME_RATIO = 0.5  # Current volume must be >50% of avg


@dataclass
class TradeParameters:
    symbol: str
    side: str                 # BUY | SELL
    leverage: int
    position_size_usdt: float
    quantity: float           # In base asset
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    risk_pct: float
    confidence: int
    approved: bool = True
    reject_reason: str = ""


@dataclass
class SafetyCheckResult:
    passed: bool
    failed_checks: list[str] = field(default_factory=list)


class RiskEngine:
    """
    Converts AI decision into concrete trade parameters.
    Applies leverage and position sizing based on confidence tiers.
    """

    def __init__(self):
        self.tiers = settings.RISK_TIERS

    def get_tier(self, confidence: int) -> Optional[dict]:
        """Return risk tier for given confidence, or None if below minimum"""
        for tier in self.tiers:
            if tier["min"] <= confidence < tier["max"]:
                return tier
        return None

    def compute_stop_loss(
        self,
        side: str,
        entry_price: float,
        atr: float,
        orderbook_sl: float,
    ) -> float:
        """
        Stop-loss = better of ATR-based SL or order-book wall SL.
        Uses 1.5x ATR distance as default.
        """
        atr_sl_long  = entry_price - (atr * 1.5)
        atr_sl_short = entry_price + (atr * 1.5)

        if side == "BUY":
            # Use orderbook suggestion if tighter (less risk)
            if orderbook_sl > 0 and orderbook_sl > atr_sl_long:
                return round(orderbook_sl, 8)
            return round(atr_sl_long, 8)
        else:
            if orderbook_sl > 0 and orderbook_sl < atr_sl_short:
                return round(orderbook_sl, 8)
            return round(atr_sl_short, 8)

    def compute_take_profit(
        self,
        side: str,
        entry_price: float,
        stop_loss: float,
        rr_ratio: float = 2.0,
    ) -> float:
        """Take profit at minimum 1:2 risk-reward ratio"""
        risk = abs(entry_price - stop_loss)
        if side == "BUY":
            return round(entry_price + (risk * rr_ratio), 8)
        else:
            return round(entry_price - (risk * rr_ratio), 8)

    def calculate(
        self,
        symbol: str,
        side: str,
        confidence: int,
        entry_price: float,
        atr: float,
        orderbook_sl: float,
        account_balance: float,
        quantity_precision: int = 3,
        price_precision: int = 4,
    ) -> TradeParameters:
        """Compute full trade parameters from risk tier"""

        tier = self.get_tier(confidence)
        if tier is None:
            return TradeParameters(
                symbol=symbol, side=side, leverage=1,
                position_size_usdt=0, quantity=0,
                entry_price=entry_price, stop_loss=0, take_profit=0,
                risk_reward=0, risk_pct=0, confidence=confidence,
                approved=False,
                reject_reason=f"Confidence {confidence} below minimum {settings.MIN_CONFIDENCE}",
            )

        leverage   = tier["leverage"]
        risk_pct   = tier["risk_pct"]
        capital_at_risk = account_balance * risk_pct  # USDT to risk on this trade
        position_size_usdt = capital_at_risk * leverage

        stop_loss   = self.compute_stop_loss(side, entry_price, atr, orderbook_sl)
        take_profit = self.compute_take_profit(side, entry_price, stop_loss)
        sl_distance = abs(entry_price - stop_loss)
        rr = round(abs(take_profit - entry_price) / sl_distance, 2) if sl_distance > 0 else 0

        # Quantity in base asset
        raw_quantity = position_size_usdt / entry_price
        quantity = round(raw_quantity, quantity_precision)

        logger.info(
            f"  Risk Tier: lev={leverage}x | risk={risk_pct*100}% | "
            f"pos={position_size_usdt:.2f} USDT | qty={quantity} | "
            f"SL={stop_loss} | TP={take_profit} | RR={rr}"
        )

        return TradeParameters(
            symbol=symbol,
            side=side,
            leverage=leverage,
            position_size_usdt=round(position_size_usdt, 2),
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=round(stop_loss, price_precision),
            take_profit=round(take_profit, price_precision),
            risk_reward=rr,
            risk_pct=risk_pct,
            confidence=confidence,
            approved=True,
        )


class SafetyFilter:
    """
    Pre-trade safety check layer.
    All checks must pass before trade execution.
    """

    def __init__(self, last_traded_symbol: Optional[str] = None):
        self.last_traded_symbol = last_traded_symbol

    def check(
        self,
        symbol: str,
        atr_pct: float,
        spread_pct: float,
        has_open_trade: bool,
        scanner_data: dict,
    ) -> SafetyCheckResult:
        """Run all safety checks. Returns result with list of failed checks."""
        failed = []

        # 1. No existing open trade
        if has_open_trade:
            failed.append("OPEN_TRADE_EXISTS: Already have an active position")

        # 2. ATR not excessively high
        if atr_pct > MAX_ATR_PCT:
            failed.append(f"EXTREME_VOLATILITY: ATR%={atr_pct} > {MAX_ATR_PCT}%")

        # 3. Spread still acceptable
        if spread_pct > MAX_SPREAD_PCT:
            failed.append(f"SPREAD_TOO_WIDE: {spread_pct}% > {MAX_SPREAD_PCT}%")

        # 4. No consecutive same-coin trade
        if self.last_traded_symbol and self.last_traded_symbol == symbol:
            failed.append(f"CONSECUTIVE_SAME_COIN: Last trade was also {symbol}")

        # 5. Volume integrity check (simplified: just ensure volume is still above threshold)
        current_volume = scanner_data.get("volume_24h", 0)
        if current_volume < settings.MIN_VOLUME_24H * MIN_VOLUME_RATIO:
            failed.append(f"VOLUME_DROP: Volume {current_volume} dropped below safety threshold")

        result = SafetyCheckResult(passed=len(failed) == 0, failed_checks=failed)

        if result.passed:
            logger.info(f"  ✅ All safety checks passed for {symbol}")
        else:
            logger.warning(f"  ❌ Safety checks FAILED for {symbol}: {failed}")

        return result
