"""
AI Decision Engine (SCALPING VERSION)
"""

import json
import logging
import asyncio
from dataclasses import dataclass
from typing import Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ✅ NEW SCALPING SYSTEM PROMPT
SYSTEM_PROMPT = """You are a crypto scalping AI trader.

Goal: make quick trades (1–5 minutes) on small accounts.

Rules:
- Ignore long-term signals
- Focus on short momentum
- Use RSI + basic trend only
- Do NOT require MACD or complex confirmations

Decision rules:
- RSI < 30 → BUY
- RSI > 70 → SELL
- Otherwise → HOLD

Confidence:
- Strong signal → 70–90
- Medium → 60–70
- Weak → below 60

Return ONLY JSON:
{
  "decision": "BUY | SELL | HOLD",
  "confidence": number (0-100),
  "reason": "short explanation"
}
"""


# ✅ SIMPLIFIED DECISION MODEL
@dataclass
class AIDecision:
    decision: str
    confidence: int
    reason: str
    raw_response: str = ""


class AIDecisionEngine:

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model   = settings.OPENAI_MODEL
        self.api_url = "https://api.openai.com/v1/chat/completions"

    # ✅ SIMPLE PROMPT (SCALPING)
    def build_prompt(self, indicators: dict, orderbook: dict, scanner_data: dict) -> str:
        return f"""
Symbol: {indicators['symbol']}
Price: {indicators['current_price']}
RSI: {indicators['momentum']['rsi']}
Trend: {indicators['trend']['direction']}

Make a scalping decision.
Return JSON only.
""".strip()

    # ✅ AI CALL
    async def decide(self, indicators: dict, orderbook: dict, scanner_data: dict) -> AIDecision:

        prompt = self.build_prompt(indicators, orderbook, scanner_data)

        logger.info(f"🤖 AI analyzing {indicators['symbol']}...")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 200,
            "response_format": {"type": "json_object"},
        }

        for attempt in range(3):
            try:
                # ✅ FIX 429 ERROR (RATE LIMIT)
                await asyncio.sleep(1)

                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(self.api_url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                raw = data["choices"][0]["message"]["content"]
                parsed = json.loads(raw)

                decision = AIDecision(
                    decision=parsed.get("decision", "HOLD").upper(),
                    confidence=int(parsed.get("confidence", 0)),
                    reason=parsed.get("reason", "")[:200],
                    raw_response=raw,
                )

                logger.info(
                    f"Decision={decision.decision} | Confidence={decision.confidence} | Reason={decision.reason}"
                )

                return decision

            except Exception as e:
                logger.warning(f"AI error (attempt {attempt+1}): {e}")
                if attempt == 2:
                    break

        # ✅ SAFE FALLBACK
        logger.warning("AI failed — default HOLD")

        return AIDecision(
            decision="HOLD",
            confidence=0,
            reason="AI error fallback",
        )

    # ✅ OUTPUT FORMAT
    def to_dict(self, decision: AIDecision) -> dict:
        return {
            "decision": decision.decision,
            "confidence": decision.confidence,
            "reason": decision.reason,
        }
