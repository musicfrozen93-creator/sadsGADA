async def scan(self, top_n: int = 5) -> list[dict]:
    """
    Scalping-optimized scan.
    Returns top coins but introduces randomness to avoid same coin repetition.
    """
    logger.info("🔍 Starting market scan (SCALPING MODE)...")

    tickers = await self.get_all_tickers()
    logger.info(f"Total USDT pairs fetched: {len(tickers)}")

    # First-pass filter
    candidates = [c for t in tickers if (c := self.passes_filters(t)) is not None]
    logger.info(f"Candidates after basic filters: {len(candidates)}")

    # Enrich
    tasks = [self.enrich_with_spread_and_trend(c) for c in candidates]
    enriched = await asyncio.gather(*tasks)
    valid = [c for c in enriched if c is not None]

    logger.info(f"Candidates after spread/trend filter: {len(valid)}")

    # 🔥 SORT ALL
    sorted_coins = sorted(valid, key=lambda x: x.score, reverse=True)

    # 🔥 TAKE TOP 10 (SCALPING POOL)
    top_10 = sorted_coins[:10]

    import random

    # 🔥 RANDOM PICK FROM TOP 5
    selection_pool = top_10[:5] if len(top_10) >= 5 else top_10
    selected = random.choice(selection_pool) if selection_pool else None

    if not selected:
        logger.warning("No valid coin found")
        return []

    logger.info(f"🎯 Selected coin for trade: {selected.symbol}")

    # Return as single-item list (important for n8n compatibility)
    return [{
        "symbol": selected.symbol,
        "price": selected.price,
        "volume_24h": selected.volume_24h,
        "price_change_pct": selected.price_change_pct,
        "spread_pct": selected.spread_pct,
        "trend_strength": selected.trend_strength,
        "score": selected.score,
        "bid": selected.bid,
        "ask": selected.ask,
    }]
