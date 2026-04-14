"""
AI Decision Engine
Uses OpenAI GPT to make high-quality trade decisions based on technical data
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a professional quantitative crypto futures trader managing a small account ($10-$50).
Your primary goal is CAPITAL PRESERVATION, then profit growth.

You receive technical analysis data and order book information.
You must output ONLY valid JSON — no markdown, no explanation, no preamble.

Decision rules:
- BUY: Strong bullish trend, RSI not overbought, MACD bullish crossover, price above EMAs, buy-side pressure
- SELL: Strong bearish trend, RSI not oversold, MACD bearish crossover, price below EMAs, sell-side pressure
- HOLD: Sideways market, conflicting signals, uncertainty, RSI in extreme zones without confirmation
- When in doubt → HOLD. Protecting capital is always more important than entering a trade.
- Only trade with confidence >= 70.
- Consider order book liquidity walls as key support/resistance.

Output format (strict JSON only):
{
  "decision": "BUY | SELL | HOLD",
  "confidence": <integer 0-100>,
  "risk_level": "LOW | MEDIUM | HIGH",
  "entry_bias": "LONG | SHORT | NONE",
  "key_support": <float or null>,
  "key_resistance": <float or null>,
  "reason": "<concise explanation, max 120 chars>"
}"""


@dataclass
class AIDecision:
    decision: str       # BUY | SELL | HOLD
    confidence: int     # 0-100
    risk_level: str     # LOW | MEDIUM | HIGH
    entry_bias: str     # LONG | SHORT | NONE
    key_support: Optional[float]
    key_resistance: Optional[float]
    reason: str
    raw_response: str = ""


class AIDecisionEngine:

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model   = settings.OPENAI_MODEL
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def build_prompt(self, indicators: dict, orderbook: dict, scanner_data: dict) -> str:
        """Build a structured, information-dense prompt for the AI"""
        return f"""
SYMBOL: {indicators['symbol']}
TIMEFRAME: {indicators['timeframe']}
CURRENT PRICE: {indicators['current_price']}

=== TREND ===
Direction: {indicators['trend']['direction']}
EMA 20: {indicators['trend']['ema_20']}
EMA 50: {indicators['trend']['ema_50']}
EMA 200: {indicators['trend']['ema_200']}

=== MOMENTUM ===
RSI: {indicators['momentum']['rsi']} ({indicators['momentum']['rsi_signal']})

=== MACD ===
Line: {indicators['macd']['line']}
Signal: {indicators['macd']['signal']}
Histogram: {indicators['macd']['histogram']}
Crossover: {indicators['macd']['crossover']}

=== BOLLINGER BANDS ===
Upper: {indicators['bollinger_bands']['upper']}
Middle: {indicators['bollinger_bands']['middle']}
Lower: {indicators['bollinger_bands']['lower']}
Width %: {indicators['bollinger_bands']['width_pct']}
Price Position: {indicators['bollinger_bands']['price_position']}

=== VOLATILITY ===
ATR: {indicators['volatility']['atr']}
ATR %: {indicators['volatility']['atr_pct']}%

=== ORDER BOOK ===
Bias: {orderbook['bias']}
Imbalance Score: {orderbook['imbalance_score']} (range: -100 to +100)
Support Zones: {orderbook['support_zones']}
Resistance Zones: {orderbook['resistance_zones']}
Suggested Long SL: {orderbook['suggested_long_sl']}
Suggested Short SL: {orderbook['suggested_short_sl']}
Buy Walls (top): {orderbook['buy_walls'][:2]}
Sell Walls (top): {orderbook['sell_walls'][:2]}

=== MARKET CONTEXT ===
24h Price Change: {scanner_data.get('price_change_pct', 'N/A')}%
24h Volume (USDT): {scanner_data.get('volume_24h', 'N/A')}
Market Score: {scanner_data.get('score', 'N/A')}

Based on all the above, make a trading decision. Output strict JSON only.
""".strip()

    async def decide(self, indicators: dict, orderbook: dict, scanner_data: dict) -> AIDecision:
        """Call OpenAI and parse the decision"""
        prompt = self.build_prompt(indicators, orderbook, scanner_data)
        logger.info(f"🤖 Requesting AI decision for {indicators['symbol']}...")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            "temperature": 0.2,    # Low temperature = more deterministic
            "max_tokens": 300,
            "response_format": {"type": "json_object"},
        }

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(self.api_url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                raw = data["choices"][0]["message"]["content"]
                parsed = json.loads(raw)

                decision = AIDecision(
                    decision=parsed.get("decision", "HOLD").upper(),
                    confidence=int(parsed.get("confidence", 0)),
                    risk_level=parsed.get("risk_level", "HIGH").upper(),
                    entry_bias=parsed.get("entry_bias", "NONE").upper(),
                    key_support=parsed.get("key_support"),
                    key_resistance=parsed.get("key_resistance"),
                    reason=parsed.get("reason", "")[:200],
                    raw_response=raw,
                )

                logger.info(
                    f"  Decision={decision.decision} | Confidence={decision.confidence} | "
                    f"Risk={decision.risk_level} | Reason: {decision.reason}"
                )
                return decision

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"AI response parse failed (attempt {attempt+1}): {e}")
            except Exception as e:
                logger.error(f"OpenAI API error (attempt {attempt+1}): {e}")
                if attempt == 2:
                    raise

        # Fallback safe decision
        logger.warning("All AI attempts failed — defaulting to HOLD")
        return AIDecision(
            decision="HOLD",
            confidence=0,
            risk_level="HIGH",
            entry_bias="NONE",
            key_support=None,
            key_resistance=None,
            reason="AI decision engine unavailable — defaulting to HOLD for safety",
        )

    def to_dict(self, decision: AIDecision) -> dict:
        return {
            "decision": decision.decision,
            "confidence": decision.confidence,
            "risk_level": decision.risk_level,
            "entry_bias": decision.entry_bias,
            "key_support": decision.key_support,
            "key_resistance": decision.key_resistance,
            "reason": decision.reason,
        }
