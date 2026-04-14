"""
Telegram Notification Module
Sends trade alerts, errors, and status updates to a Telegram chat
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

    async def trade_executed(self, symbol: str, side: str, qty: float, entry: float,
                              sl: float, tp: float, leverage: int, confidence: int, reason: str):
        emoji = "🟢" if side == "BUY" else "🔴"
        msg = (
            f"{emoji} <b>TRADE EXECUTED</b>\n"
            f"Symbol: <b>{symbol}</b>\n"
            f"Side: <b>{side} (LONG)</b>\n"
            f"Quantity: {qty}\n"
            f"Entry: <b>${entry:,.6f}</b>\n"
            f"Stop Loss: ${sl:,.6f}\n"
            f"Take Profit: ${tp:,.6f}\n"
            f"Leverage: {leverage}x\n"
            f"AI Confidence: {confidence}%\n"
            f"Reason: <i>{reason}</i>"
        )
        await self.send(msg)

    async def trade_skipped(self, symbol: str, reason: str):
        msg = (
            f"⏭️ <b>TRADE SKIPPED</b>\n"
            f"Symbol: {symbol}\n"
            f"Reason: <i>{reason}</i>"
        )
        await self.send(msg)

    async def error_alert(self, context: str, error: str):
        msg = (
            f"⚠️ <b>ERROR</b>\n"
            f"Context: {context}\n"
            f"Error: <code>{error[:300]}</code>"
        )
        await self.send(msg)

    async def scan_complete(self, top_coins: list):
        coins_str = "\n".join(
            f"  {i+1}. {c['symbol']} — score={c['score']} | vol={c['price_change_pct']}%"
            for i, c in enumerate(top_coins)
        )
        msg = f"🔍 <b>SCAN COMPLETE</b>\nTop candidates:\n{coins_str}"
        await self.send(msg)
