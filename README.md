# AI Momentum Trading Bot — HFM/MT5

Bot trading otomatis: analisa momentum (RSI/MACD/EMA) + konfirmasi AI (Claude) +
risk management berbasis ATR, eksekusi via MetaTrader5 ke broker HFM.

## ⚠️ PERINGATAN PENTING

- **Trading forex/CFD berisiko tinggi.** Anda bisa kehilangan modal, bahkan lebih dari deposit (tergantung leverage).
- Bot ini BELUM diuji secara historis (backtest) maupun di demo account.
- **Sangat disarankan**: jalankan dulu di **demo account HFM** minimal 2-4 minggu sebelum live, untuk validasi logic, debug edge case, dan lihat performa nyata.
- `lot_size` di config sengaja diset kecil (0.01). Jangan naikkan sebelum yakin.
- `max_daily_loss_pct` adalah circuit breaker — pastikan diset sesuai toleransi risiko Anda, bukan default begitu saja.
- Tidak ada bot yang menjamin profit. Past performance ≠ future results.

## Kenapa Butuh Wine/Windows?

MT5 adalah aplikasi Windows native. Python `MetaTrader5` package butuh
MT5 terminal berjalan di background. Dua opsi:

**Opsi A — VPS Windows** (lebih simpel & stabil, direkomendasikan)
HFM biasanya menyediakan VPS Windows gratis untuk akun dengan volume tertentu — cek dashboard HFM Anda. Kalau tidak ada, sewa VPS Windows (mis. Contabo, Vultr Windows plan).

**Opsi B — Ubuntu + Wine** (sesuai permintaan awal Anda)
Lebih kompleks tapi bisa. Berikut langkahnya.

## Instalasi di Ubuntu VPS (via Wine)

```bash
# 1. Update sistem
sudo apt update && sudo apt upgrade -y

# 2. Install Wine
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install -y wine64 wine32 winetricks

# 3. Install Python di dalam Wine (MT5 terminal butuh ini)
winetricks python310

# 4. Download & install MT5 terminal dari HFM
wget https://download.mql5.com/cdn/web/hf.markets/mt5/hfmarkets5setup.exe
wine hfmarkets5setup.exe
# Login ke MT5 terminal dengan akun HFM Anda sekali secara manual dulu

# 5. Jalankan MT5 terminal headless di background
wine "C:\Program Files\HFM MT5 Terminal\terminal64.exe" &

# 6. Setup environment Python (native Linux, BUKAN di dalam Wine)
sudo apt install -y python3-venv python3-pip
cd ~/trading-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Catatan**: package Python `MetaTrader5` berkomunikasi dengan terminal MT5 yang
jalan via Wine melalui shared memory/IPC. Di sebagian setup Linux ini kurang stabil
dibanding native Windows — kalau sering disconnect, pertimbangkan pindah ke Opsi A (VPS Windows).

## Setup Konfigurasi

```bash
cp .env.example .env
nano .env   # isi MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, GEMINI_API_KEY, DEEPSEEK_API_KEY
```

**Cara dapat API key:**
- Gemini: https://aistudio.google.com/apikey (ada free tier dengan rate limit)
- DeepSeek: https://platform.deepseek.com/api_keys (berbayar per token, jauh lebih murah dari kebanyakan provider)

**Strategi AI yang dipakai bot ini: KONSENSUS.** Tiap sinyal momentum yang cukup kuat
dikirim ke Gemini DAN DeepSeek secara independen. Order hanya dieksekusi jika:
1. Kedua AI sama-sama `confirm: true`
2. Kedua AI sepakat arahnya (BUY/SELL) sama dengan sinyal momentum
3. Confidence masing-masing AI ≥ `AI_MIN_CONFIDENCE`

Kalau salah satu API error/timeout/limit, bot **tidak akan trading** untuk sinyal itu
(fail-safe konservatif) — bukan otomatis pakai yang satunya saja. Ini sengaja lebih
ketat supaya tidak ada eksekusi berdasarkan satu AI yang mungkin keliru.

Cek nama server persis di MT5 terminal Anda (File > Login to Trade Account > pilih server),
biasanya formatnya seperti `HFMarketsGlobal-Live` atau `HFMarketsLive-Server1`.

Edit `config/settings.py` untuk sesuaikan:
- `symbols` — pair yang mau ditradingkan
- `lot_size` — mulai dari minimum (0.01)
- `max_daily_loss_pct` — batas rugi harian sebelum bot auto-stop
- `max_open_positions` — maksimal posisi terbuka bersamaan

## Test Manual Sebelum Jalan Otomatis

```bash
source venv/bin/activate
python3 -c "
from config.settings import mt5_config
from core.mt5_connector import MT5Connector
c = MT5Connector(mt5_config)
print('Connected:', c.connect())
print(c.get_account_info())
c.disconnect()
"
```

Kalau ini berhasil print info akun Anda, koneksi sudah benar.

## Jalankan Bot

**Manual (untuk testing):**
```bash
source venv/bin/activate
python3 main.py
```

**Sebagai service (production, auto-restart kalau crash):**
```bash
sudo cp trading-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl start trading-bot

# Cek status & logs
sudo systemctl status trading-bot
journalctl -u trading-bot -f
tail -f logs/bot.log
```

## Monitoring

- `logs/bot.log` — semua aktivitas bot (sinyal, AI confirmation, eksekusi)
- Cek posisi terbuka langsung dari MT5 terminal atau MyFXBook/HFM dashboard
- **Sangat disarankan** tambahkan notifikasi Telegram/Discord untuk setiap order
  (belum termasuk di kerangka ini — bisa ditambahkan di `executor.py`)

## Struktur Folder

```
trading-bot/
├── config/settings.py       # semua parameter bot
├── core/
│   ├── mt5_connector.py     # koneksi & data feed MT5
│   ├── momentum.py          # indikator RSI/MACD/EMA/ATR
│   ├── ai_analyzer.py       # konfirmasi via Claude API
│   ├── risk_engine.py       # TP/SL calculation + circuit breaker
│   └── executor.py          # eksekusi order ke MT5
├── logs/
├── main.py                  # entry point + main loop
├── requirements.txt
├── .env.example
└── trading-bot.service      # systemd unit file
```

## Yang Masih Perlu Anda Tambahkan/Pertimbangkan

1. **Backtesting** — kerangka ini belum termasuk backtest engine. Sebelum live,
   uji strategi momentum ini di data historis (bisa pakai `backtrader` atau `vectorbt`).
2. **Notifikasi** — Telegram bot untuk alert real-time tiap ada order/error.
3. **Trailing stop** — saat ini TP/SL statis setelah entry; trailing stop bisa
   menambah profit di trend kuat.
4. **News filter** — hindari trading saat high-impact news (NFP, rate decision)
   karena volatilitas ekstrem bisa membuat SL/TP tidak akurat.
5. **Multi-timeframe confirmation** — sinyal M15 dikonfirmasi tren H1/H4 biasanya
   lebih reliable.
