# Deploy Trading Bot di VirtualBox (Ubuntu Server) — Langkah Lengkap

## 0. Yang Perlu Anda Sadari Dulu

VM di VirtualBox jalan di komputer fisik Anda. Konsekuensinya:
- **Komputer Anda harus nyala 24/7** kalau mau bot jalan terus-menerus (beda dengan VPS cloud yang memang didesain nyala terus).
- Kalau komputer mati/restart/update Windows, bot ikut mati. Pertimbangkan setting power plan supaya tidak sleep otomatis.
- Koneksi internet rumah Anda jadi single point of failure — kalau internet putus, bot tidak bisa eksekusi order maupun cek harga.

Kalau ini cuma untuk testing/development dulu sebelum pindah ke VPS cloud beneran, ini pendekatan yang masuk akal. Kalau niatnya production jangka panjang, VPS cloud (DigitalOcean, Vultr, Contabo) lebih reliable karena uptime-nya dikelola provider.

## 1. Install VirtualBox + Ubuntu Server

1. Download & install VirtualBox: https://www.virtualbox.org/wiki/Downloads
2. Download Ubuntu Server 22.04 LTS ISO: https://ubuntu.com/download/server
3. Buat VM baru di VirtualBox:
   - RAM: 4-8 GB
   - CPU: 2+ core
   - Disk: 25+ GB
   - Network: **Bridged Adapter** (penting — supaya VM dapat IP sendiri di jaringan lokal Anda dan akses internet stabil)
4. Mount ISO, boot, install Ubuntu Server. Saat instalasi, **centang "Install OpenSSH server"**.
5. Setelah selesai, reboot VM.

## 2. Cari IP VM dan SSH Masuk

Di dalam VM (console VirtualBox), jalankan:
```bash
ip a
```
Catat IP yang muncul di interface (biasanya `enp0s3` atau sejenisnya, formatnya `192.168.x.x`).

Dari komputer utama Anda (Terminal di Mac/Linux, atau PowerShell/PuTTY di Windows):
```bash
ssh username_anda@192.168.x.x
```
Mulai sekarang kerja dari sini saja, lebih nyaman daripada di console VirtualBox.

## 3. Update Sistem & Install Dependencies Dasar

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip git wget nano
```

## 4. Install Wine (untuk jalankan MT5 terminal)

```bash
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install -y wine64 wine32 winetricks

# Install Python di dalam Wine (MT5 butuh ini agar terminal jalan dengan baik)
winetricks python310 corefonts
```

Proses ini agak lama, sabar saja.

## 5. Install MT5 Terminal dari HFM

```bash
wget https://download.mql5.com/cdn/web/hf.markets/mt5/hfmarkets5setup.exe
wine hfmarkets5setup.exe
```

Installer akan buka jendela GUI Wine. Kalau VM Anda headless (tanpa display), pakai VNC atau jalankan VirtualBox dengan GUI window terbuka untuk proses install ini saja (sekali saja, setelahnya bisa headless).

Setelah terinstall, **login manual sekali** ke akun HFM Anda lewat MT5 terminal (supaya kredensial tersimpan & terminal "kenal" akun Anda), lalu:

```bash
# Jalankan MT5 terminal di background
wine "C:\Program Files\HFM MT5 Terminal\terminal64.exe" &
```

## 6. Upload Project Bot ke VM

Dari **komputer utama Anda** (bukan di dalam VM), copy file project ke VM via `scp`:

```bash
scp trading-bot.tar.gz username_anda@192.168.x.x:~/
```

Lalu di dalam VM (via SSH):
```bash
tar -xzf trading-bot.tar.gz
cd trading-bot
```

## 7. Setup Python Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 8. Isi Konfigurasi

```bash
cp .env.example .env
nano .env
```

Isi:
```
MT5_LOGIN=login_akun_hfm_anda
MT5_PASSWORD=password_anda
MT5_SERVER=HFMarketsGlobal-Live   # cek nama persis di MT5 terminal
GEMINI_API_KEY=...
DEEPSEEK_API_KEY=...
```

Simpan dengan `Ctrl+O`, Enter, lalu `Ctrl+X` keluar.

## 9. Test Koneksi Sebelum Jalan Otomatis

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

Kalau ini print info akun Anda (balance, currency, dll) — koneksi sudah benar, lanjut ke step berikutnya.

## 10. Jalankan Bot

**Manual dulu (lihat langsung outputnya, untuk memastikan tidak ada error):**
```bash
python3 main.py
```
Biarkan jalan beberapa menit, perhatikan `logs/bot.log`, pastikan sinyal & AI confirmation tercatat dengan benar. Tekan `Ctrl+C` untuk stop.

**Kalau sudah yakin, jalankan permanen via systemd** (auto-restart kalau crash, auto-start kalau VM reboot):

```bash
# Edit dulu path & user di file service sesuai VM Anda
nano trading-bot.service
```
Sesuaikan `User=`, `WorkingDirectory=`, dan `ExecStart=` dengan username dan path Anda di VM.

```bash
sudo cp trading-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl start trading-bot

# Cek jalan tidaknya
sudo systemctl status trading-bot
tail -f logs/bot.log
```

## 11. Supaya VM & MT5 Terminal Otomatis Jalan Saat Reboot

Bot via systemd sudah auto-start, tapi **MT5 terminal (Wine) tidak otomatis** kecuali Anda setup juga. Tambahkan ke crontab:

```bash
crontab -e
```
Tambahkan baris:
```
@reboot wine "C:\Program Files\HFM MT5 Terminal\terminal64.exe" &
```

## 12. (Opsional tapi Disarankan) Supaya VM Tidak Mati Saat Komputer Sleep

Di komputer host (Windows/Mac):
- **Windows**: Settings > System > Power & Sleep > matikan sleep otomatis selama VM perlu jalan
- **Mac**: System Settings > Battery > matikan "Put hard disks to sleep"

Dan pastikan VirtualBox VM disetting **start otomatis saat host boot** kalau komputer Anda restart (pakai `VBoxManage` autostart atau tools seperti `vboxautostart-service` di Linux host).

## Troubleshooting Umum

| Masalah | Kemungkinan Penyebab |
|---|---|
| `MT5Connector.connect()` return False | Wine MT5 terminal belum jalan, atau kredensial salah, atau nama server salah |
| Order gagal terus (`retcode != DONE`) | Cek `symbol_info.trade_mode`, lot size di bawah minimum broker, atau market lagi closed |
| Python `MetaTrader5` import error | Package ini sebenarnya didesain untuk Windows; di Linux+Wine kadang perlu install dengan Wine Python juga, bukan cuma native Python. Kalau terus bermasalah, ini sinyal kuat untuk pindah ke VPS Windows |
