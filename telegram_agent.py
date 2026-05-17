#!/usr/bin/env python3
import time
import requests
import json
import os
import subprocess
from config.notifications import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

if not TELEGRAM_BOT_TOKEN:
    print("TELEGRAM_BOT_TOKEN is not set in config/notifications.py")
    exit(1)

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

def send_message(chat_id, text):
    try:
        requests.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text})
    except Exception as e:
        print("Failed to send message:", e)

def get_stats():
    state_file = os.path.join(DIRECTORY, "data", "dashboard_state.json")
    summary_file = os.path.join(DIRECTORY, "output", "latest", "run_summary.json")
    
    stats_text = "📊 **Dashboard Stats**\n\n"
    
    try:
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)
                kanban = state.get("kanban", {})
                applied_count = len(kanban)
                stats_text += f"Total di Kanban: {applied_count} lowongan\n"
                
                # Breakdown by status
                status_counts = {}
                for k, v in kanban.items():
                    status_counts[v] = status_counts.get(v, 0) + 1
                for s, c in status_counts.items():
                    stats_text += f" - {s.capitalize()}: {c}\n"
        else:
            stats_text += "Kanban: Belum ada data lamaran.\n"
    except:
        pass
        
    try:
        if os.path.exists(summary_file):
            with open(summary_file, 'r') as f:
                summary = json.load(f)
                date_str = summary.get("finished_at", "Unknown")
                stats_text += f"\n🔄 **Scrape Terakhir**: {date_str[:16].replace('T', ' ')}\n"
                stats_text += f"Links Discovered: {summary.get('total_links_discovered', 0)}\n"
                stats_text += f"Duplicates Removed: {summary.get('duplicates_removed', 0)}\n"
    except:
        pass

    return stats_text

def process_command(text, chat_id):
    cmd = text.split()[0].lower()
    
    if cmd == '/ping':
        send_message(chat_id, "🏓 Pong! Agent is running normally.")
    
    elif cmd == '/stats':
        send_message(chat_id, get_stats())
        
    elif cmd == '/run':
        send_message(chat_id, "🚀 Menjalankan Scraper dengan mode Powerful & AI...\nMohon tunggu sekitar 2-3 menit.")
        
        try:
            # Run scraper
            script_path = os.path.join(DIRECTORY, "scraper", "main.py")
            process = subprocess.run(
                ["python3", script_path, "--powerful", "--use-ai"], 
                capture_output=True, text=True, cwd=DIRECTORY
            )
            
            if process.returncode == 0:
                send_message(chat_id, "✅ Scraping selesai! Silakan buka Dashboard untuk melihat hasilnya.")
            else:
                send_message(chat_id, f"❌ Terjadi kesalahan saat scraping:\n{process.stderr[-200:]}")
        except Exception as e:
            send_message(chat_id, f"❌ Gagal menjalankan skrip: {e}")
            
    elif cmd == '/help' or cmd == '/start':
        help_text = (
            "🤖 **MT Job Tracker Agent**\n\n"
            "Perintah yang tersedia:\n"
            "/ping - Cek status bot\n"
            "/stats - Lihat statistik lamaran Anda\n"
            "/run - Jalankan scraper saat ini juga\n"
            "/help - Tampilkan pesan ini"
        )
        send_message(chat_id, help_text)

def check_reminders():
    """Check for upcoming interview reminders and send notifications."""
    state_file = os.path.join(DIRECTORY, "data", "dashboard_state.json")
    if not os.path.exists(state_file):
        return
    try:
        with open(state_file, 'r') as f:
            data = json.load(f)
        reminders = data.get("reminders", {})
        now = time.strftime("%Y-%m-%d %H:%M")
        
        # Check H-1 hour reminders
        for job_id, dt_str in list(reminders.items()):
            try:
                # Parse reminder datetime
                reminder_time = time.strptime(dt_str.strip(), "%Y-%m-%d %H:%M")
                reminder_ts = time.mktime(reminder_time)
                now_ts = time.time()
                diff_minutes = (reminder_ts - now_ts) / 60
                
                # Send reminder 60 minutes before
                if 55 <= diff_minutes <= 65:
                    kanban = data.get("kanban", {})
                    send_message(TELEGRAM_CHAT_ID, f"⏰ PENGINGAT: Interview Anda dijadwalkan dalam ~1 jam!\n📅 {dt_str}\n\nSemangat dan persiapkan diri Anda! 💪")
            except:
                pass
    except:
        pass

def main():
    print("🤖 Telegram Agent started. Listening for commands...")
    offset = None
    
    while True:
        try:
            url = f"{BASE_URL}/getUpdates"
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset
                
            response = requests.get(url, params=params, timeout=40)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    for update in data["result"]:
                        offset = update["update_id"] + 1
                        message = update.get("message", {})
                        text = message.get("text", "")
                        chat_id = message.get("chat", {}).get("id")
                        
                        if text and text.startswith("/") and str(chat_id) == str(TELEGRAM_CHAT_ID):
                            print(f"Received command: {text}")
                            process_command(text, chat_id)
            
            # Check reminders every polling cycle
            check_reminders()
            
        except requests.exceptions.RequestException:
            # Ignore network errors and retry
            time.sleep(5)
        except Exception as e:
            print(f"Error in polling loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
