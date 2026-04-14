"""
Configuration management using environment variables
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # Binance
    BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
    BINANCE_SECRET_KEY: str = os.getenv("BINANCE_SECRET_KEY", "")
    BINANCE_TESTNET: bool = os.getenv("BINANCE_TESTNET", "true").lower() == "true"

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Trading parameters
    ACCOUNT_BALANCE: float = float(os.getenv("ACCOUNT_BALANCE", "20.0"))
    MIN_CONFIDENCE: int = int(os.getenv("MIN_CONFIDENCE", "70"))

    # Scanner filters
    MIN_VOLUME_24H: float = 5_000_000.0
    MIN_PRICE_CHANGE: float = 3.0
    MAX_SPREAD_PCT: float = 0.2
    MIN_PRICE: float = 0.001
    MAX_PRICE: float = 50.0
    EXCLUDED_COINS: list = None

    # Risk tiers
    RISK_TIERS: list = None

    def __post_init__(self):
        self.EXCLUDED_COINS = ["BTC", "ETH", "BNB", "BTCUSDT", "ETHUSDT", "BNBUSDT"]
        self.RISK_TIERS = [
            {"min": 70, "max": 80, "leverage": 5,  "risk_pct": 0.05},
            {"min": 80, "max": 90, "leverage": 10, "risk_pct": 0.10},
            {"min": 90, "max": 95, "leverage": 12, "risk_pct": 0.15},
            {"min": 95, "max": 101, "leverage": 15, "risk_pct": 0.20},
        ]

    @property
    def binance_base_url(self) -> str:
        if self.BINANCE_TESTNET:
            return "https://testnet.binancefuture.com"
        return "https://fapi.binance.com"


settings = Settings()
