"""
Simple in-memory trade state tracker.
In production, replace with Redis or database.
"""

from dataclasses import dataclass, field
from typing import Optional
import json
import os

STATE_FILE = "logs/trade_state.json"


@dataclass
class TradeState:
    has_open_trade: bool = False
    open_symbol: Optional[str] = None
    last_traded_symbol: Optional[str] = None
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0


class StateManager:

    def __init__(self):
        self.state = self._load()

    def _load(self) -> TradeState:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE) as f:
                    data = json.load(f)
                return TradeState(**data)
            except Exception:
                pass
        return TradeState()

    def save(self):
        os.makedirs("logs", exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(self.state.__dict__, f, indent=2)

    def open_trade(self, symbol: str):
        self.state.has_open_trade = True
        self.state.open_symbol = symbol
        self.state.total_trades += 1
        self.save()

    def close_trade(self, pnl: float):
        self.state.has_open_trade = False
        self.state.last_traded_symbol = self.state.open_symbol
        self.state.open_symbol = None
        self.state.total_pnl += pnl
        if pnl > 0:
            self.state.winning_trades += 1
        else:
            self.state.losing_trades += 1
        self.save()

    def get_stats(self) -> dict:
        total = self.state.total_trades
        win_rate = (
            self.state.winning_trades / total * 100 if total > 0 else 0
        )
        return {
            "total_trades": total,
            "winning_trades": self.state.winning_trades,
            "losing_trades": self.state.losing_trades,
            "win_rate_pct": round(win_rate, 1),
            "total_pnl": round(self.state.total_pnl, 4),
            "has_open_trade": self.state.has_open_trade,
            "open_symbol": self.state.open_symbol,
            "last_traded_symbol": self.state.last_traded_symbol,
        }


# Singleton
state_manager = StateManager()
