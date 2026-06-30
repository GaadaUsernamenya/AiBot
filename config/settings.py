"""
Konfigurasi Bot Trading
PENTING: Jangan commit file ini ke git jika sudah diisi kredensial asli.
Gunakan environment variables di production (lihat .env.example).
"""
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class MT5Config:
    # Kredensial akun HFM (MT5)
    login: int = int(os.getenv("MT5_LOGIN", "0"))
    password: str = os.getenv("MT5_PASSWORD", "")
    server: str = os.getenv("MT5_SERVER", "HFMarketsGlobal-Live")  # cek nama server persis di MT5 Anda
    # Path ke terminal MT5 (kosongkan jika MT5 sudah default terinstall)
    terminal_path: str = os.getenv("MT5_PATH", "")


@dataclass
class TradingConfig:
    symbols: List[str] = field(default_factory=lambda: ["EURUSD", "GBPUSD", "XAUUSD"])
    timeframe: str = "M15"  # M1, M5, M15, M30, H1, H4, D1
    lot_size: float = 0.01  # mulai KECIL, terutama untuk live trading
    max_open_positions: int = 3
    max_daily_loss_pct: float = 3.0  # circuit breaker: stop trading kalau rugi >3%/hari
    magic_number: int = 778899  # identifier unik untuk order dari bot ini

    # Risk management (ATR-based)
    atr_period: int = 14
    sl_atr_multiplier: float = 1.5
    tp_atr_multiplier: float = 2.5

    # Momentum thresholds
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0

    # AI analysis
    use_ai_confirmation: bool = True

    # Loop
    poll_interval_seconds: int = 60


@dataclass
class AIConfig:
    # Gemini
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # DeepSeek
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    ai_min_confidence: float = float(os.getenv("AI_MIN_CONFIDENCE", "0.65"))


mt5_config = MT5Config()
trading_config = TradingConfig()
ai_config = AIConfig()
