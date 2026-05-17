#!/bin/bash

# MT Job Tracker Auto-Run Script
# Digunakan untuk eksekusi via cron job

# Pindah ke direktori proyek
cd "/Users/fahry/Desktop/CLAUDE \"MT\" copy 2" || exit

# Jika ada file log lama, pindahkan (opsional, untuk mencegah log terlalu besar)
# mv cron_log.txt cron_log_old.txt

echo "========================================"
echo "Memulai Auto-Run pada: $(date)"
echo "========================================"

# Jalankan scraper mode powerful
python3 scraper/main.py --powerful

echo "========================================"
echo "Selesai pada: $(date)"
echo "========================================"
