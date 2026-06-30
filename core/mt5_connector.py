"""
Modul koneksi ke MT5 dan pengambilan data harga.
"""
import logging
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime

logger = logging.getLogger("trading_bot.mt5")

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


class MT5Connector:
    def __init__(self, config):
        self.config = config
        self.connected = False

    def connect(self) -> bool:
        init_kwargs = {}
        if self.config.terminal_path:
            init_kwargs["path"] = self.config.terminal_path

        if not mt5.initialize(**init_kwargs):
            logger.error(f"MT5 initialize() gagal: {mt5.last_error()}")
            return False

        authorized = mt5.login(
            login=self.config.login,
            password=self.config.password,
            server=self.config.server,
        )
        if not authorized:
            logger.error(f"MT5 login gagal: {mt5.last_error()}")
            mt5.shutdown()
            return False

        account_info = mt5.account_info()
        logger.info(
            f"Terhubung ke MT5 | Akun: {account_info.login} | "
            f"Balance: {account_info.balance} {account_info.currency} | "
            f"Server: {account_info.server}"
        )
        self.connected = True
        return True

    def disconnect(self):
        mt5.shutdown()
        self.connected = False
        logger.info("Koneksi MT5 ditutup")

    def get_ohlcv(self, symbol: str, timeframe: str, count: int = 200) -> pd.DataFrame:
        """Ambil data candle terbaru sebagai DataFrame."""
        tf = TIMEFRAME_MAP.get(timeframe, mt5.TIMEFRAME_M15)
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            logger.warning(f"Tidak ada data untuk {symbol}")
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def get_account_info(self):
        return mt5.account_info()

    def get_open_positions(self, symbol: str = None):
        if symbol:
            return mt5.positions_get(symbol=symbol) or []
        return mt5.positions_get() or []

    def get_symbol_info(self, symbol: str):
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.error(f"Symbol {symbol} tidak ditemukan")
            return None
        if not info.visible:
            mt5.symbol_select(symbol, True)
        return mt5.symbol_info(symbol)
