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

def send_message(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    try:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        requests.post(f"{BASE_URL}/sendMessage", json=payload)
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
    cmd = text.split()[0].lower() if text else ""
    
    main_keyboard = {
        "keyboard": [
            [{"text": "📊 Lihat Stats"}, {"text": "🌅 Morning Brief"}],
            [{"text": "🚀 Jalankan Scraper"}, {"text": "🏓 Ping Bot"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }
    
    if cmd == '/ping' or text == '🏓 Ping Bot':
        send_message(chat_id, "🏓 Pong! Agent is running normally.")
    
    elif cmd == '/stats' or text == '📊 Lihat Stats':
        send_message(chat_id, get_stats())
        
    elif cmd == '/run' or text == '🚀 Jalankan Scraper':
        send_message(chat_id, "🚀 Menjalankan Scraper dengan mode Powerful...\nMohon tunggu sekitar 2-3 menit.")
        
        try:
            # Run scraper
            script_path = os.path.join(DIRECTORY, "scraper", "main.py")
            process = subprocess.run(
                ["python3", script_path, "--powerful"], 
                capture_output=True, text=True, cwd=DIRECTORY
            )
            
            if process.returncode == 0:
                send_message(chat_id, "✅ Scraping selesai! Silakan buka Dashboard untuk melihat hasilnya.")
            else:
                send_message(chat_id, f"❌ Terjadi kesalahan saat scraping:\n{process.stderr[-200:]}")
        except Exception as e:
            send_message(chat_id, f"❌ Gagal menjalankan skrip: {e}")
            
    elif cmd == '/brief' or text == '🌅 Morning Brief':
        check_morning_brief(force=True)
            
    elif cmd == '/help' or cmd == '/start' or text == 'Mulai':
        help_text = (
            "🤖 **MT Job Tracker Agent**\n\n"
            "Gunakan tombol di bawah untuk mengontrol bot dengan cepat!"
        )
        send_message(chat_id, help_text, reply_markup=main_keyboard)

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

def check_morning_brief(force=False):
    """Check if it's 8:00 AM and send daily top 3 jobs if not sent yet today, or if forced."""
    now = time.localtime()
    if force or now.tm_hour == 8:
        today_str = time.strftime("%Y-%m-%d")
        state_file = os.path.join(DIRECTORY, "data", "brief_state.json")
        last_sent = ""
        
        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    last_sent = json.load(f).get("last_sent_date", "")
            except:
                pass
                
        if force or last_sent != today_str:
            # We need to send the brief!
            apply_today_path = os.path.join(DIRECTORY, "output", "latest", "apply_today.csv")
            if os.path.exists(apply_today_path):
                import csv
                try:
                    jobs = []
                    with open(apply_today_path, "r", encoding="utf-8-sig") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            score = float(row.get("Score", 0))
                            jobs.append((row, score))
                    
                    if jobs:
                        jobs.sort(key=lambda x: x[1], reverse=True)
                        top_3 = jobs[:3]
                        
                        msg = "🌅 *Top 3 Lowongan MT Terbaik Hari Ini* 🌅\n\n"
                        inline_keyboard = []
                        
                        for idx, (job, score) in enumerate(top_3, 1):
                            msg += f"{idx}. *{job.get('Job Title')}* @ {job.get('Company')}\n"
                            msg += f"   🎯 Score: {score}\n"
                            msg += f"   📍 Lokasi: {job.get('Location')}\n\n"
                            
                            if job.get('Link') and job.get('Link') != 'Tidak tercantum':
                                inline_keyboard.append([{"text": f"🔗 Apply: {job.get('Company')}", "url": job.get('Link')}])
                            
                        msg += "Semangat apply hari ini! 💪"
                        reply_markup = {"inline_keyboard": inline_keyboard} if inline_keyboard else None
                        send_message(TELEGRAM_CHAT_ID, msg, reply_markup=reply_markup)
                        
                        # Save state
                        with open(state_file, "w") as f:
                            json.dump({"last_sent_date": today_str}, f)
                except Exception as e:
                    print(f"Failed to generate morning brief: {e}")

def check_deadlines(force=False):
    """Check for high score jobs that are closing within 48 hours and haven't been applied to."""
    now = time.localtime()
    if force or now.tm_hour == 17: # Run at 5 PM
        today_str = time.strftime("%Y-%m-%d")
        state_file = os.path.join(DIRECTORY, "data", "deadline_alert_state.json")
        last_sent = ""
        
        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    last_sent = json.load(f).get("last_sent_date", "")
            except:
                pass
                
        if force or last_sent != today_str:
            jobs_path = os.path.join(DIRECTORY, "output", "latest", "jobs_ranked.csv")
            dashboard_state_file = os.path.join(DIRECTORY, "data", "dashboard_state.json")
            
            if os.path.exists(jobs_path):
                import csv
                import re
                
                # Load Kanban state
                kanban = {}
                if os.path.exists(dashboard_state_file):
                    try:
                        with open(dashboard_state_file, "r") as f:
                            kanban = json.load(f).get("kanban", {})
                    except:
                        pass

                def slugify(text):
                    return re.sub(r'[^a-z0-9]', '', str(text).lower())

                urgent_jobs = []
                try:
                    with open(jobs_path, "r", encoding="utf-8-sig") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            score = float(row.get("Score", 0))
                            if score < 80: continue
                            
                            job_id = slugify(row.get("Company", "") + row.get("Job Title", "") + row.get("Location", ""))
                            if job_id in kanban: continue # Already applied or in progress
                            
                            days_str = row.get("days_until_deadline", "")
                            try:
                                days = int(float(days_str))
                                if 0 <= days <= 2:
                                    urgent_jobs.append((row, days))
                            except ValueError:
                                # Fallback if status is urgent
                                if row.get("deadline_status") == "Urgent":
                                    urgent_jobs.append((row, 1))

                    if urgent_jobs:
                        msg = "⚠️ *Peringatan Tenggat Waktu (Deadline)!*\n\nLowongan prioritas ini akan tutup dalam 1-2 hari. Segera apply!\n\n"
                        inline_keyboard = []
                        
                        for idx, (job, days) in enumerate(urgent_jobs[:5], 1):
                            msg += f"{idx}. *{job.get('Job Title')}* @ {job.get('Company')}\n"
                            msg += f"   🎯 Score: {job.get('Score')} | ⏳ Sisa: {days} Hari\n\n"
                            
                            if job.get('Link') and job.get('Link') != 'Tidak tercantum':
                                inline_keyboard.append([{"text": f"🔗 Apply {job.get('Company')}", "url": job.get('Link')}])
                        
                        reply_markup = {"inline_keyboard": inline_keyboard} if inline_keyboard else None
                        send_message(TELEGRAM_CHAT_ID, msg, reply_markup=reply_markup)
                        
                        with open(state_file, "w") as f:
                            json.dump({"last_sent_date": today_str}, f)
                except Exception as e:
                    print(f"Failed to check deadlines: {e}")

def check_follow_up():
    now = time.localtime()
    if now.tm_hour == 10: # Check at 10 AM
        today_str = time.strftime("%Y-%m-%d")
        state_file = os.path.join(DIRECTORY, "data", "followup_state.json")
        last_sent = ""
        try:
            if os.path.exists(state_file):
                with open(state_file, "r") as f:
                    last_sent = json.load(f).get("last_sent_date", "")
        except: pass
        
        if last_sent != today_str:
            dashboard_state_file = os.path.join(DIRECTORY, "data", "dashboard_state.json")
            try:
                with open(dashboard_state_file, "r") as f:
                    data = json.load(f)
                    kanban = data.get("kanban", {})
                    apply_dates = data.get("apply_dates", {})
                
                reminders = []
                for job_id, status in kanban.items():
                    if status == "applied" and job_id in apply_dates:
                        days_ago = (time.time() - time.mktime(time.strptime(apply_dates[job_id], "%Y-%m-%d"))) / 86400
                        if days_ago >= 7 and days_ago < 8:
                            reminders.append(job_id)
                
                if reminders:
                    msg = "🔔 *Reminder Follow-Up*\n\nAnda sudah melamar pekerjaan berikut 7 hari yang lalu tapi belum ada update:\n"
                    for rid in reminders:
                        msg += f"- {rid}\n"
                    msg += "\nSilakan periksa email atau kirimkan email follow-up!"
                    send_message(TELEGRAM_CHAT_ID, msg)
                
                with open(state_file, "w") as f:
                    json.dump({"last_sent_date": today_str}, f)
            except Exception as e:
                print("Follow up error:", e)

def check_weekly_stats():
    now = time.localtime()
    if now.tm_wday == 6 and now.tm_hour == 17: # Sunday 17:00
        today_str = time.strftime("%Y-%m-%d")
        state_file = os.path.join(DIRECTORY, "data", "weekly_stats_state.json")
        last_sent = ""
        try:
            if os.path.exists(state_file):
                with open(state_file, "r") as f:
                    last_sent = json.load(f).get("last_sent_date", "")
        except: pass
        
        if last_sent != today_str:
            send_message(TELEGRAM_CHAT_ID, get_stats())
            with open(state_file, "w") as f:
                json.dump({"last_sent_date": today_str}, f)

def check_auto_scraper():
    now = time.localtime()
    if now.tm_hour == 7: # 07:00 AM
        today_str = time.strftime("%Y-%m-%d")
        state_file = os.path.join(DIRECTORY, "data", "auto_scraper_state.json")
        last_sent = ""
        try:
            if os.path.exists(state_file):
                with open(state_file, "r") as f:
                    last_sent = json.load(f).get("last_sent_date", "")
        except: pass
        
        if last_sent != today_str:
            send_message(TELEGRAM_CHAT_ID, "⚙️ *Auto-Scraper* dimulai untuk pencarian harian...")
            import threading
            def run_scrape():
                try:
                    subprocess.run(["python3", "scraper/main.py", "--mode", "all", "--core-only", "--global-limit", "10"], cwd=DIRECTORY)
                    send_message(TELEGRAM_CHAT_ID, "✅ *Auto-Scraper* harian selesai dijalankan!")
                except Exception as e:
                    send_message(TELEGRAM_CHAT_ID, f"❌ *Auto-Scraper* error: {e}")
            threading.Thread(target=run_scrape, daemon=True).start()
            
            with open(state_file, "w") as f:
                json.dump({"last_sent_date": today_str}, f)

def main():
    print("🤖 Telegram Agent started. Listening for commands...")
    offset = None
    last_gmail_sync = 0
    
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
                        
                        if text and str(chat_id) == str(TELEGRAM_CHAT_ID):
                            print(f"Received command: {text}")
                            process_command(text, chat_id)
            
            # Check proactive tasks every polling cycle - ALL DISABLED (On-demand only)
            # check_reminders()
            # check_morning_brief()
            # check_deadlines()
            # check_follow_up()
            # check_weekly_stats()
            # check_auto_scraper() # Disabled: running on-demand only per user request
            
        except requests.exceptions.RequestException:
            time.sleep(5)
        except Exception as e:
            print(f"Error in polling loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
