"""
Analisis momentum berbasis indikator kuantitatif.
Ini adalah lapisan "hard rules" yang presisi — AI di layer terpisah
hanya mengkonfirmasi/menambah konteks, bukan menghitung angka.
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass


@dataclass
class MomentumSignal:
    direction: str  # "BUY", "SELL", "NEUTRAL"
    rsi: float
    macd_hist: float
    atr: float
    ema_fast: float
    ema_slow: float
    strength: float  # 0.0 - 1.0, seberapa kuat sinyal


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def analyze_momentum(df: pd.DataFrame, config) -> MomentumSignal:
    """
    Hitung indikator dan tentukan sinyal momentum dasar.
    Strategi: EMA crossover + RSI filter + MACD histogram confirmation.
    """
    close = df["close"]

    rsi = calculate_rsi(close, config.rsi_period)
    atr = calculate_atr(df, config.atr_period)
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    _, _, macd_hist = calculate_macd(close)

    last_rsi = rsi.iloc[-1]
    last_atr = atr.iloc[-1]
    last_ema_fast = ema_fast.iloc[-1]
    last_ema_slow = ema_slow.iloc[-1]
    last_macd_hist = macd_hist.iloc[-1]
    prev_macd_hist = macd_hist.iloc[-2]

    direction = "NEUTRAL"
    strength = 0.0

    # Bullish: EMA fast > EMA slow, MACD histogram naik, RSI belum overbought
    bullish_trend = last_ema_fast > last_ema_slow
    bearish_trend = last_ema_fast < last_ema_slow
    macd_rising = last_macd_hist > prev_macd_hist

    if bullish_trend and macd_rising and last_rsi < config.rsi_overbought:
        direction = "BUY"
        strength = min(1.0, (config.rsi_overbought - last_rsi) / 40 + 0.4)
    elif bearish_trend and not macd_rising and last_rsi > config.rsi_oversold:
        direction = "SELL"
        strength = min(1.0, (last_rsi - config.rsi_oversold) / 40 + 0.4)

    return MomentumSignal(
        direction=direction,
        rsi=round(last_rsi, 2),
        macd_hist=round(last_macd_hist, 5),
        atr=round(last_atr, 5),
        ema_fast=round(last_ema_fast, 5),
        ema_slow=round(last_ema_slow, 5),
        strength=round(strength, 2),
    )
