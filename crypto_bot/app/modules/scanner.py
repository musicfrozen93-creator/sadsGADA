"""
Market Scanner Module
Scans Binance Futures USDT pairs and filters/ranks them by quality score
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CoinCandidate:
    symbol: str
    price: float
    volume_24h: float
    price_change_pct: float
    bid: float
    ask: float
    spread_pct: float
    score: float = 0.0
    trend_strength: float = 0.0


class MarketScanner:
    """
    Scans Binance Futures for high-quality trading candidates.
    Applies strict filters to protect small account capital.
    """

    def __init__(self):
        self.base_url = settings.binance_base_url
        self.excluded = {s.replace("USDT", "") for s in settings.EXCLUDED_COINS}

    async def get_all_tickers(self) -> list[dict]:
        """Fetch 24h ticker stats for all USDT perpetual futures"""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.base_url}/fapi/v1/ticker/24hr")
            resp.raise_for_status()
            tickers = resp.json()

        # Filter USDT pairs only
        return [t for t in tickers if t["symbol"].endswith("USDT")]

    async def get_book_ticker(self, symbol: str) -> dict:
        """Fetch best bid/ask for spread calculation"""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/fapi/v1/ticker/bookTicker",
                params={"symbol": symbol},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_klines(self, symbol: str, interval: str = "1h", limit: int = 24) -> list:
        """Fetch recent klines to compute trend strength"""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/fapi/v1/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
            )
            resp.raise_for_status()
            return resp.json()

    def compute_trend_strength(self, klines: list) -> float:
        """
        Simple trend strength: ratio of up-candles vs total candles (0-100).
        Positive trend = more up candles consistently.
        """
        if not klines:
            return 50.0
        closes = [float(k[4]) for k in klines]
        up_candles = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i - 1])
        return round((up_candles / (len(closes) - 1)) * 100, 2)

    def compute_score(self, vol_pct: float, volume_24h: float, trend: float) -> float:
        """
        score = (volatility * 0.4) + (normalized_volume * 0.3) + (trend_strength * 0.3)
        Volume is log-normalized to 0-100 range.
        """
        import math
        norm_volume = min(math.log10(max(volume_24h, 1)) / math.log10(1_000_000_000) * 100, 100)
        return round(
            (min(vol_pct, 30) / 30 * 100 * 0.4)
            + (norm_volume * 0.3)
            + (trend * 0.3),
            2,
        )

    def passes_filters(self, ticker: dict) -> Optional[CoinCandidate]:
        """Apply all scanner filters. Returns None if coin fails any filter."""
        symbol = ticker["symbol"]
        base = symbol.replace("USDT", "")

        # Exclude major coins
        if base in self.excluded:
            return None

        try:
            price = float(ticker["lastPrice"])
            volume = float(ticker["quoteVolume"])  # 24h volume in USDT
            change_pct = abs(float(ticker["priceChangePercent"]))
        except (ValueError, KeyError):
            return None

        # Price filter
        if not (settings.MIN_PRICE <= price <= settings.MAX_PRICE):
            return None

        # Volume filter
        if volume < settings.MIN_VOLUME_24H:
            return None

        # Volatility filter
        if change_pct < settings.MIN_PRICE_CHANGE:
            return None

        return CoinCandidate(
            symbol=symbol,
            price=price,
            volume_24h=volume,
            price_change_pct=change_pct,
            bid=0.0,
            ask=0.0,
            spread_pct=0.0,
        )

    async def enrich_with_spread_and_trend(self, candidate: CoinCandidate) -> Optional[CoinCandidate]:
        """Add spread and trend data; returns None if spread filter fails."""
        try:
            book = await self.get_book_ticker(candidate.symbol)
            bid = float(book["bidPrice"])
            ask = float(book["askPrice"])
            spread_pct = ((ask - bid) / bid) * 100 if bid > 0 else 999

            if spread_pct > settings.MAX_SPREAD_PCT:
                return None

            klines = await self.get_klines(candidate.symbol)
            trend = self.compute_trend_strength(klines)
            score = self.compute_score(candidate.price_change_pct, candidate.volume_24h, trend)

            candidate.bid = bid
            candidate.ask = ask
            candidate.spread_pct = round(spread_pct, 4)
            candidate.trend_strength = trend
            candidate.score = score
            return candidate

        except Exception as e:
            logger.warning(f"Failed to enrich {candidate.symbol}: {e}")
            return None

    async def scan(self, top_n: int = 3) -> list[dict]:
        """
        Main scan method. Returns top N ranked coins as dicts.
        """
        logger.info("🔍 Starting market scan...")

        tickers = await self.get_all_tickers()
        logger.info(f"Total USDT pairs fetched: {len(tickers)}")

        # First-pass filter (sync, fast)
        candidates = [c for t in tickers if (c := self.passes_filters(t)) is not None]
        logger.info(f"Candidates after basic filters: {len(candidates)}")

        # Enrich with spread + trend (async, batched)
        tasks = [self.enrich_with_spread_and_trend(c) for c in candidates]
        enriched = await asyncio.gather(*tasks)
        valid = [c for c in enriched if c is not None]

        logger.info(f"Candidates after spread/trend filter: {len(valid)}")

        # Sort by score descending, take top N
        ranked = sorted(valid, key=lambda x: x.score, reverse=True)[:top_n]

        result = []
        for coin in ranked:
            result.append({
                "symbol": coin.symbol,
                "price": coin.price,
                "volume_24h": coin.volume_24h,
                "price_change_pct": coin.price_change_pct,
                "spread_pct": coin.spread_pct,
                "trend_strength": coin.trend_strength,
                "score": coin.score,
                "bid": coin.bid,
                "ask": coin.ask,
            })
            logger.info(f"  ✅ {coin.symbol} | score={coin.score} | vol={coin.price_change_pct}% | spread={coin.spread_pct}%")

        return result
