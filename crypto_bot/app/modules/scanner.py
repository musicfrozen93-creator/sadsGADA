import asyncio
import random
import logging
import httpx

logger = logging.getLogger(__name__)


class MarketScanner:

    BASE_URL = "https://fapi.binance.com"

    async def get_all_tickers(self):
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.BASE_URL}/fapi/v1/ticker/24hr")
            return resp.json()

    def passes_filters(self, ticker):
        try:
            volume = float(ticker["quoteVolume"])
            change = abs(float(ticker["priceChangePercent"]))

            # basic filters
            if volume < 10_000_000:
                return None
            if change < 0.5:
                return None

            return {
                "symbol": ticker["symbol"],
                "price": float(ticker["lastPrice"]),
                "volume_24h": volume,
                "price_change_pct": float(ticker["priceChangePercent"]),
            }

        except:
            return None

    async def enrich_with_spread_and_trend(self, coin):
        try:
            async with httpx.AsyncClient() as client:
                depth = await client.get(
                    f"{self.BASE_URL}/fapi/v1/depth",
                    params={"symbol": coin["symbol"], "limit": 5}
                )
                data = depth.json()

            bid = float(data["bids"][0][0])
            ask = float(data["asks"][0][0])

            spread_pct = (ask - bid) / bid * 100

            # simple trend score
            trend_strength = abs(coin["price_change_pct"])

            score = coin["volume_24h"] * trend_strength

            return {
                **coin,
                "bid": bid,
                "ask": ask,
                "spread_pct": spread_pct,
                "trend_strength": trend_strength,
                "score": score,
            }

        except:
            return None

    async def scan(self, top_n: int = 5) -> list[dict]:

        logger.info("🔍 Starting market scan (SCALPING MODE)...")

        tickers = await self.get_all_tickers()

        candidates = [c for t in tickers if (c := self.passes_filters(t)) is not None]

        tasks = [self.enrich_with_spread_and_trend(c) for c in candidates]
        enriched = await asyncio.gather(*tasks)

        valid = [c for c in enriched if c is not None]

        sorted_coins = sorted(valid, key=lambda x: x["score"], reverse=True)

        top_10 = sorted_coins[:10]

        selection_pool = top_10[:5] if len(top_10) >= 5 else top_10
        selected = random.choice(selection_pool) if selection_pool else None

        if not selected:
            return []

        logger.info(f"🎯 Selected coin: {selected['symbol']}")

        return [selected]
