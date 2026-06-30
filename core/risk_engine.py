"""
Risk Engine: menghitung TP/SL berbasis ATR dan position sizing.
Semua perhitungan harga di sini bersifat deterministik (bukan dari AI)
supaya konsisten dan teraudit.
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger("trading_bot.risk")


@dataclass
class TradePlan:
    symbol: str
    direction: str  # "BUY" / "SELL"
    entry_price: float
    sl_price: float
    tp_price: float
    lot_size: float
    risk_reward_ratio: float


def calculate_trade_plan(symbol: str, direction: str, entry_price: float,
                          atr: float, config) -> TradePlan:
    sl_distance = atr * config.sl_atr_multiplier
    tp_distance = atr * config.tp_atr_multiplier

    if direction == "BUY":
        sl_price = entry_price - sl_distance
        tp_price = entry_price + tp_distance
    else:  # SELL
        sl_price = entry_price + sl_distance
        tp_price = entry_price - tp_distance

    rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0

    return TradePlan(
        symbol=symbol,
        direction=direction,
        entry_price=entry_price,
        sl_price=round(sl_price, 5),
        tp_price=round(tp_price, 5),
        lot_size=config.lot_size,
        risk_reward_ratio=round(rr_ratio, 2),
    )


def check_daily_loss_circuit_breaker(account_info, daily_start_balance: float,
                                      max_daily_loss_pct: float) -> bool:
    """
    Return True jika bot HARUS BERHENTI trading karena sudah
    melebihi batas rugi harian. Ini adalah safety net paling penting
    untuk live trading.
    """
    if daily_start_balance <= 0:
        return False
    current_equity = account_info.equity
    loss_pct = ((daily_start_balance - current_equity) / daily_start_balance) * 100

    if loss_pct >= max_daily_loss_pct:
        logger.critical(
            f"CIRCUIT BREAKER AKTIF! Rugi harian {loss_pct:.2f}% "
            f">= batas {max_daily_loss_pct}%. Bot berhenti trading."
        )
        return True
    return False


def check_max_positions(open_positions: list, max_positions: int) -> bool:
    """Return True jika sudah mencapai batas posisi terbuka."""
    return len(open_positions) >= max_positions
