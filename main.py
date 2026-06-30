"""
Entry point bot trading.
Loop: ambil data -> analisa momentum -> konfirmasi AI -> cek risk ->
      hitung TP/SL -> eksekusi -> tunggu interval -> ulang.
"""
import logging
import time
import sys
from datetime import datetime, date

from config.settings import mt5_config, trading_config, ai_config
from core.mt5_connector import MT5Connector
from core.momentum import analyze_momentum
from core.ai_analyzer import MultiAIAnalyzer
from core.risk_engine import (
    calculate_trade_plan,
    check_daily_loss_circuit_breaker,
    check_max_positions,
)
from core.executor import execute_trade

# ---- Logging setup ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("trading_bot.main")


class TradingBot:
    def __init__(self):
        self.connector = MT5Connector(mt5_config)
        self.ai = MultiAIAnalyzer(ai_config) if trading_config.use_ai_confirmation else None
        self.daily_start_balance = 0.0
        self.current_day = date.today()
        self.trading_halted = False

    def reset_daily_tracking(self):
        account_info = self.connector.get_account_info()
        self.daily_start_balance = account_info.balance
        self.current_day = date.today()
        self.trading_halted = False
        logger.info(f"Daily tracking reset. Start balance: {self.daily_start_balance}")

    def run_cycle(self):
        if date.today() != self.current_day:
            self.reset_daily_tracking()

        account_info = self.connector.get_account_info()

        # --- Circuit breaker check ---
        if check_daily_loss_circuit_breaker(
            account_info, self.daily_start_balance, trading_config.max_daily_loss_pct
        ):
            self.trading_halted = True
            return

        if self.trading_halted:
            logger.warning("Trading masih dihentikan (circuit breaker). Skip cycle.")
            return

        open_positions = self.connector.get_open_positions()
        if check_max_positions(open_positions, trading_config.max_open_positions):
            logger.info(f"Sudah mencapai max open positions ({len(open_positions)}). Skip.")
            return

        for symbol in trading_config.symbols:
            self.process_symbol(symbol, open_positions)

    def process_symbol(self, symbol: str, open_positions: list):
        # Skip jika sudah ada posisi terbuka untuk symbol ini
        if any(p.symbol == symbol for p in open_positions):
            return

        df = self.connector.get_ohlcv(symbol, trading_config.timeframe, count=200)
        if df.empty or len(df) < 50:
            logger.warning(f"Data tidak cukup untuk {symbol}")
            return

        signal = analyze_momentum(df, trading_config)

        if signal.direction == "NEUTRAL" or signal.strength < 0.4:
            logger.debug(f"[{symbol}] Tidak ada sinyal kuat. {signal}")
            return

        logger.info(f"[{symbol}] Sinyal momentum: {signal.direction} (strength={signal.strength})")

        # --- AI confirmation layer ---
        if self.ai:
            recent_prices = df["close"].tolist()
            ai_result = self.ai.confirm_signal(symbol, signal, recent_prices)
            if not ai_result.get("confirm") or ai_result.get("confidence", 0) < ai_config.ai_min_confidence:
                logger.info(f"[{symbol}] AI tidak konfirmasi sinyal: {ai_result.get('reasoning')}")
                return
            logger.info(f"[{symbol}] AI konfirmasi: {ai_result.get('reasoning')}")

        # --- Risk & trade plan ---
        symbol_info = self.connector.get_symbol_info(symbol)
        if symbol_info is None:
            return

        tick = symbol_info.bid if signal.direction == "SELL" else symbol_info.ask
        trade_plan = calculate_trade_plan(symbol, signal.direction, tick, signal.atr, trading_config)

        logger.info(
            f"[{symbol}] Trade plan: {trade_plan.direction} entry={trade_plan.entry_price} "
            f"SL={trade_plan.sl_price} TP={trade_plan.tp_price} RR={trade_plan.risk_reward_ratio}"
        )

        # --- Execute ---
        execute_trade(trade_plan, symbol_info, trading_config.magic_number)

    def start(self):
        if not self.connector.connect():
            logger.critical("Gagal konek ke MT5. Bot berhenti.")
            return

        self.reset_daily_tracking()
        logger.info("Bot trading dimulai. Mode: LIVE TRADING.")
        logger.info(f"Symbols: {trading_config.symbols} | Timeframe: {trading_config.timeframe}")

        try:
            while True:
                try:
                    self.run_cycle()
                except Exception as e:
                    logger.exception(f"Error di trading cycle: {e}")
                time.sleep(trading_config.poll_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Bot dihentikan manual (Ctrl+C).")
        finally:
            self.connector.disconnect()


if __name__ == "__main__":
    bot = TradingBot()
    bot.start()
