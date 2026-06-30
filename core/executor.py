"""
Modul eksekusi order ke MT5.
"""
import logging
import MetaTrader5 as mt5

logger = logging.getLogger("trading_bot.executor")


def execute_trade(trade_plan, symbol_info, magic_number: int):
    """Kirim order market ke MT5 sesuai trade_plan."""
    order_type = mt5.ORDER_TYPE_BUY if trade_plan.direction == "BUY" else mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(trade_plan.symbol).ask if trade_plan.direction == "BUY" \
        else mt5.symbol_info_tick(trade_plan.symbol).bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": trade_plan.symbol,
        "volume": trade_plan.lot_size,
        "type": order_type,
        "price": price,
        "sl": trade_plan.sl_price,
        "tp": trade_plan.tp_price,
        "deviation": 20,  # slippage toleransi (points)
        "magic": magic_number,
        "comment": "ai-momentum-bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(
            f"Order GAGAL [{trade_plan.symbol}] {trade_plan.direction} | "
            f"retcode={result.retcode} | comment={result.comment}"
        )
        return None

    logger.info(
        f"Order BERHASIL [{trade_plan.symbol}] {trade_plan.direction} | "
        f"lot={trade_plan.lot_size} | entry={price} | "
        f"SL={trade_plan.sl_price} | TP={trade_plan.tp_price} | "
        f"ticket={result.order}"
    )
    return result
