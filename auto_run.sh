#!/bin/bash

# MT Job Tracker Auto-Run Script
# Digunakan untuk eksekusi via cron job / macOS LaunchAgent
# Schedule: setiap hari pukul 07:00 WIB

# Pindah ke direktori proyek
cd "/Users/fahry/Desktop/CLAUDE \"MT\" copy 2" || exit

LOG="cron_log.txt"

echo "========================================" >> "$LOG"
echo "Memulai Auto-Run pada: $(date)" >> "$LOG"
echo "========================================" >> "$LOG"

# Jalankan scraper mode powerful dengan AI
python3 scraper/main.py --mode all --include-optional --powerful --use-ai --max-pages-per-source 3 2>&1 | tee -a "$LOG"

echo "--- Scraper selesai: $(date) ---" >> "$LOG"

# Auto-push ke Railway agar dashboard & Telegram agent terupdate
git add output/latest/ cache/ 2>&1 >> "$LOG"
git commit -m "auto: scraper run $(date +%Y-%m-%d_%H-%M)" 2>&1 >> "$LOG"
git push origin main 2>&1 >> "$LOG"

echo "========================================" >> "$LOG"
echo "Selesai dan di-push pada: $(date)" >> "$LOG"
echo "========================================" >> "$LOG"
