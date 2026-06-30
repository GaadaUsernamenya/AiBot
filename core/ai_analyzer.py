"""
Lapisan konfirmasi AI MULTI-PROVIDER: Gemini + DeepSeek.
Strategi: KONSENSUS — order hanya dieksekusi jika KEDUA AI setuju
arah sinyalnya (direction sama) DAN masing-masing confidence
melewati threshold. Ini lebih konservatif dibanding single-AI,
karena mengurangi false positive dari satu model yang "halu".

Catatan desain:
- Kedua provider dipanggil secara independen (bukan salah satu
  melihat jawaban yang lain), supaya konsensusnya jujur, bukan
  bias anchoring.
- Kalau salah satu provider error/timeout, default-nya TIDAK
  trading (fail-safe konservatif) — bukan otomatis pakai yang satu lagi,
  karena strategi yang dipilih adalah konsensus, bukan fallback.
- Angka TP/SL tetap dihitung deterministik dari ATR (risk_engine.py),
  AI di sini cuma filter eksekusi.
"""
import json
import logging
import requests

logger = logging.getLogger("trading_bot.ai")


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def confirm_signal(self, prompt: str) -> dict:
        try:
            resp = requests.post(
                f"{self.base_url}?key={self.api_key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300},
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as e:
            logger.error(f"Gemini provider error: {e}")
            return {"confirm": False, "confidence": 0.0, "reasoning": f"Gemini error: {e}"}


class DeepSeekProvider:
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.deepseek.com/chat/completions"

    def confirm_signal(self, prompt: str) -> dict:
        try:
            resp = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 300,
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as e:
            logger.error(f"DeepSeek provider error: {e}")
            return {"confirm": False, "confidence": 0.0, "reasoning": f"DeepSeek error: {e}"}


def build_prompt(symbol: str, momentum_signal, recent_prices: list) -> str:
    return f"""Kamu adalah asisten analisis trading. Evaluasi sinyal momentum berikut
secara OBJEKTIF dan KONSERVATIF. Jangan asal mengkonfirmasi.

Symbol: {symbol}
Sinyal momentum terdeteksi: {momentum_signal.direction}
RSI: {momentum_signal.rsi}
MACD histogram: {momentum_signal.macd_hist}
EMA fast/slow: {momentum_signal.ema_fast} / {momentum_signal.ema_slow}
ATR: {momentum_signal.atr}
Strength score (0-1): {momentum_signal.strength}
20 harga close terakhir: {recent_prices[-20:]}

Tugas kamu: nilai apakah sinyal ini cukup meyakinkan untuk dieksekusi,
dengan mempertimbangkan kemungkinan choppy market, divergence, atau
sinyal palsu (fakeout).

Jawab HANYA dalam format JSON berikut, tanpa teks lain, tanpa markdown:
{{"confirm": true/false, "confidence": 0.0-1.0, "direction": "BUY/SELL/NEUTRAL", "reasoning": "alasan singkat 1-2 kalimat"}}"""


class MultiAIAnalyzer:
    """
    Konfirmasi sinyal menggunakan Gemini DAN DeepSeek.
    Eksekusi hanya jika KEDUANYA setuju.
    """

    def __init__(self, ai_config):
        self.gemini = GeminiProvider(ai_config.gemini_api_key, ai_config.gemini_model)
        self.deepseek = DeepSeekProvider(ai_config.deepseek_api_key, ai_config.deepseek_model)
        self.min_confidence = ai_config.ai_min_confidence

    def confirm_signal(self, symbol: str, momentum_signal, recent_prices: list) -> dict:
        prompt = build_prompt(symbol, momentum_signal, recent_prices)

        gemini_result = self.gemini.confirm_signal(prompt)
        deepseek_result = self.deepseek.confirm_signal(prompt)

        logger.info(f"[{symbol}] Gemini: {gemini_result}")
        logger.info(f"[{symbol}] DeepSeek: {deepseek_result}")

        gemini_confirm = gemini_result.get("confirm", False)
        deepseek_confirm = deepseek_result.get("confirm", False)
        gemini_conf = gemini_result.get("confidence", 0.0)
        deepseek_conf = deepseek_result.get("confidence", 0.0)
        gemini_dir = gemini_result.get("direction", "NEUTRAL")
        deepseek_dir = deepseek_result.get("direction", "NEUTRAL")

        # --- Syarat KONSENSUS ---
        both_confirm = gemini_confirm and deepseek_confirm
        same_direction = gemini_dir == deepseek_dir == momentum_signal.direction
        both_above_threshold = (
            gemini_conf >= self.min_confidence and deepseek_conf >= self.min_confidence
        )

        consensus = both_confirm and same_direction and both_above_threshold
        combined_confidence = round(min(gemini_conf, deepseek_conf), 2)  # ambil yang terlemah, konservatif

        reasoning = (
            f"Gemini: {gemini_result.get('reasoning', '-')} | "
            f"DeepSeek: {deepseek_result.get('reasoning', '-')}"
        )

        if not consensus:
            reason_detail = []
            if not both_confirm:
                reason_detail.append("salah satu/keduanya tidak confirm")
            if not same_direction:
                reason_detail.append(f"arah beda (Gemini={gemini_dir}, DeepSeek={deepseek_dir})")
            if not both_above_threshold:
                reason_detail.append(f"confidence di bawah threshold ({self.min_confidence})")
            logger.info(f"[{symbol}] TIDAK ada konsensus: {', '.join(reason_detail)}")

        return {
            "confirm": consensus,
            "confidence": combined_confidence,
            "reasoning": reasoning,
            "detail": {
                "gemini": gemini_result,
                "deepseek": deepseek_result,
            },
        }
