"""
Telegram Notification Module (PRO VERSION)
"""

import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


class TelegramNotifier:

    def __init__(self):
        self.token   = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def send(self, message: str) -> bool:
        if not self.token or not self.chat_id:
            logger.warning("Telegram not configured — skipping notification")
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                    },
                )
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")
            return False

    # 🚀 TRADE EXECUTED (UPGRADED - DYNAMIC TP/SL)
    async def trade_executed(
        self,
        symbol: str,
        side: str,
        qty: float,
        entry: float,
        sl: float,
        tp: float,
        leverage: int,
        confidence: int,
        reason: str
    ):
        emoji = "🟢" if side == "BUY" else "🔴"

        msg = f"""
{emoji} <b>SCALP TRADE EXECUTED</b>

<b>Symbol:</b> {symbol}
<b>Side:</b> {side}
<b>Leverage:</b> {leverage}x

<b>Entry:</b> ${entry:,.6f}
🛑 <b>Stop Loss:</b> ${sl:,.6f}
🎯 <b>Take Profit:</b> ${tp:,.6f}

<b>Quantity:</b> {qty}
<b>Confidence:</b> {confidence}%

<i>{reason}</i>
"""
        await self.send(msg)

    # ⏭️ TRADE SKIPPED (CLEAN)
    async def trade_skipped(self, symbol: str, reason: str):
        msg = f"""
⏭️ <b>TRADE SKIPPED</b>

<b>Symbol:</b> {symbol}
<i>{reason}</i>
"""
        await self.send(msg)

    # ⚠️ ERROR ALERT
    async def error_alert(self, context: str, error: str):
        msg = f"""
⚠️ <b>ERROR</b>

<b>Context:</b> {context}
<code>{error[:300]}</code>
"""
        await self.send(msg)

    # 🔍 SCAN RESULT (IMPROVED)
    async def scan_complete(self, top_coins: list):
        coins_str = "\n".join(
            f"{i+1}. <b>{c['symbol']}</b> | score={c['score']} | Δ={c['price_change_pct']}%"
            for i, c in enumerate(top_coins)
        )

        msg = f"""
🔍 <b>SCAN COMPLETE</b>

Top Coins:
{coins_str}
"""
        await self.send(msg)
