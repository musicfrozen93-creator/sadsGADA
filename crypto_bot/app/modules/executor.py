# ✅ Track last traded symbols
last_trades = []


async def execute_trade(self, params: TradeParameters) -> OrderResult:
    """
    Full trade execution flow with duplicate protection
    """

    symbol = params.symbol

    # ❌ Prevent duplicate trades (last 3 trades)
    if symbol in last_trades[-3:]:
        logger.warning(f"⚠️ Skipping duplicate trade for {symbol}")
        return OrderResult(
            success=False,
            order_id=None,
            symbol=symbol,
            side=params.side,
            quantity=params.quantity,
            entry_price=params.entry_price,
            error="Duplicate coin trade skipped"
        )

    logger.info(f"⚡ Executing {params.side} trade on {symbol}...")

    try:
        # 🔍 Get precision info
        precision = await self.get_precision(symbol)

        # 🔍 Validate minimum notional
        notional = params.quantity * params.entry_price
        if notional < precision.min_notional:
            raise ValueError(
                f"Notional {notional:.2f} USDT below minimum {precision.min_notional}"
            )

        # 🔍 Validate minimum quantity
        if params.quantity < precision.min_qty:
            raise ValueError(
                f"Quantity {params.quantity} below minimum {precision.min_qty}"
            )

        # ⚙️ Configure margin & leverage
        await self.set_margin_type(symbol, "ISOLATED")
        await self.set_leverage(symbol, params.leverage)
        logger.info(f"Leverage set to {params.leverage}x (ISOLATED)")

        # 🚀 Place MARKET order
        order = await self.place_market_order(
            symbol, params.side, params.quantity, precision
        )

        order_id = order.get("orderId")

        if not order_id:
            raise ValueError("Order failed: No order ID returned")

        logger.info(f"✅ Market order placed: #{order_id}")

        # 🔁 Determine closing side
        close_side = "SELL" if params.side == "BUY" else "BUY"

        # 🛡️ Stop Loss
        sl_order = await self.place_stop_loss(
            symbol, close_side, params.quantity, params.stop_loss, precision
        )
        logger.info(f"Stop-loss set at {params.stop_loss}")

        # 🎯 Take Profit
        tp_order = await self.place_take_profit(
            symbol, close_side, params.quantity, params.take_profit, precision
        )
        logger.info(f"Take-profit set at {params.take_profit}")

        # ✅ SAVE ONLY SUCCESSFUL TRADES
        last_trades.append(symbol)

        # keep only last 5 trades
        if len(last_trades) > 5:
            last_trades.pop(0)

        return OrderResult(
            success=True,
            order_id=order_id,
            symbol=symbol,
            side=params.side,
            quantity=params.quantity,
            entry_price=params.entry_price,
            stop_loss_order_id=sl_order.get("orderId"),
            take_profit_order_id=tp_order.get("orderId"),
        )

    except Exception as e:
        logger.error(f"❌ Trade execution failed for {symbol}: {str(e)}")

        return OrderResult(
            success=False,
            order_id=None,
            symbol=symbol,
            side=params.side,
            quantity=params.quantity,
            entry_price=params.entry_price,
            error=str(e),
        )
