#!/usr/bin/env python3
import time
import requests
import json
import os
import subprocess
import csv
import re
from config.notifications import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

if not TELEGRAM_BOT_TOKEN:
    print("TELEGRAM_BOT_TOKEN is not set in environment. Please set it.")
    exit(1)

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def send_message(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    try:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        print("Failed to send message:", e)

def edit_message(chat_id, message_id, text, parse_mode="Markdown"):
    """Edit an existing bot message (used for live progress updates)."""
    try:
        payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": parse_mode}
        resp = requests.post(f"{BASE_URL}/editMessageText", json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        print("Failed to edit message:", e)
        return {}

def send_message_get_id(chat_id, text, parse_mode="Markdown"):
    """Send a message and return its message_id for later editing."""
    try:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        resp = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10)
        data = resp.json()
        return data.get("result", {}).get("message_id")
    except Exception as e:
        print("Failed to send message:", e)
        return None

def load_jobs_csv(filepath):
    """Load jobs from a CSV file into a list of dicts."""
    jobs = []
    if not os.path.exists(filepath):
        return jobs
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                jobs.append(row)
    except Exception:
        pass
    return jobs

# ─────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────

def get_stats():
    state_file = os.path.join(DIRECTORY, "data", "dashboard_state.json")
    summary_file = os.path.join(DIRECTORY, "output", "latest", "run_summary.json")
    
    stats_text = "📊 *Dashboard Stats*\n\n"
    
    try:
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)
                kanban = state.get("kanban", {})
                applied_count = len(kanban)
                stats_text += f"Total di Kanban: {applied_count} lowongan\n"
                status_counts = {}
                for k, v in kanban.items():
                    status_counts[v] = status_counts.get(v, 0) + 1
                for s, c in status_counts.items():
                    stats_text += f"  - {s.capitalize()}: {c}\n"
        else:
            stats_text += "Kanban: Belum ada data lamaran.\n"
    except:
        pass
        
    try:
        if os.path.exists(summary_file):
            with open(summary_file, 'r') as f:
                summary = json.load(f)
                date_str = summary.get("finished_at", "Unknown")
                stats_text += f"\n🔄 *Scrape Terakhir*: {date_str[:16].replace('T', ' ')}\n"
                stats_text += f"Links Discovered: {summary.get('total_links_discovered', 0)}\n"
                stats_text += f"Duplikat Dihapus: {summary.get('duplicates_removed', 0)}\n"
                stats_text += f"Total Lowongan: {summary.get('total_exported', 0)}\n"
                stats_text += f"Strong Match: {summary.get('strong_match_count', 0)}\n"
                stats_text += f"Good Match: {summary.get('good_match_count', 0)}\n"
                stats_text += f"Apply Today: {summary.get('total_apply_today', 0)}\n"
    except:
        pass

    return stats_text

# ─────────────────────────────────────────────
# TOP JOBS
# ─────────────────────────────────────────────

def get_top_jobs(n=5):
    """Return top N ranked jobs as a formatted Telegram message."""
    jobs_file = os.path.join(DIRECTORY, "output", "latest", "jobs_ranked.csv")
    jobs = load_jobs_csv(jobs_file)
    
    if not jobs:
        return "❌ Belum ada data lowongan. Jalankan scraper dulu dengan /run."
    
    msg = f"🏆 *Top {n} Lowongan Terbaik*\n_(berdasarkan run terakhir)_\n\n"
    inline_keyboard = []
    
    for i, job in enumerate(jobs[:n], 1):
        score = job.get("Score", job.get("match_score", "?"))
        title = job.get("Job Title", job.get("job_title", "?"))
        company = job.get("Company", job.get("company", "?"))
        location = job.get("Location", job.get("location", "?"))
        link = job.get("Link", job.get("job_url", ""))
        
        msg += f"*{i}. {title}*\n"
        msg += f"   🏢 {company} | 📍 {location}\n"
        msg += f"   ⭐ Score: {score}/100\n\n"
        
        if link and link not in ("Tidak tercantum", ""):
            inline_keyboard.append([{"text": f"🔗 {i}. {company[:20]}", "url": link}])
    
    reply_markup = {"inline_keyboard": inline_keyboard} if inline_keyboard else None
    return msg, reply_markup

def get_apply_today():
    """Return apply_today.csv formatted as a Telegram message."""
    apply_file = os.path.join(DIRECTORY, "output", "latest", "apply_today.csv")
    jobs = load_jobs_csv(apply_file)
    
    if not jobs:
        return "📋 Tidak ada lowongan di daftar *Apply Today*.\n\nJalankan `/run` untuk mendapatkan rekomendasi terbaru.", None
    
    msg = f"📋 *Apply Today — {len(jobs)} Lowongan Prioritas*\n\n"
    inline_keyboard = []
    
    for i, job in enumerate(jobs[:10], 1):
        score = job.get("Score", job.get("match_score", "?"))
        title = job.get("Job Title", job.get("job_title", "?"))
        company = job.get("Company", job.get("company", "?"))
        gpa_status = job.get("gpa_status", "")
        deadline_status = job.get("deadline_status", "")
        link = job.get("Link", job.get("job_url", ""))
        
        dl_icon = "✅" if deadline_status == "Open" else "❓"
        
        msg += f"*{i}. {title}*\n"
        msg += f"   🏢 {company} | ⭐ {score} | {dl_icon} {deadline_status or 'Unknown'}\n\n"
        
        if link and link not in ("Tidak tercantum", ""):
            inline_keyboard.append([{"text": f"🔗 Apply: {company[:20]}", "url": link}])
    
    if len(jobs) > 10:
        msg += f"_...dan {len(jobs) - 10} lowongan lainnya. Buka Dashboard untuk list lengkap._"
    
    reply_markup = {"inline_keyboard": inline_keyboard} if inline_keyboard else None
    return msg, reply_markup

def search_jobs(keyword, max_results=5):
    """Search jobs from jobs_ranked.csv by keyword."""
    jobs_file = os.path.join(DIRECTORY, "output", "latest", "jobs_ranked.csv")
    jobs = load_jobs_csv(jobs_file)
    
    if not jobs:
        return "❌ Belum ada data lowongan. Jalankan `/run` dulu.", None
    
    kw = keyword.lower()
    found = []
    for job in jobs:
        searchable = " ".join([
            job.get("Job Title", ""), job.get("Company", ""),
            job.get("Location", ""), job.get("Why Match", "")
        ]).lower()
        if kw in searchable:
            found.append(job)
    
    if not found:
        return f"🔍 Tidak ditemukan lowongan dengan kata kunci: *{keyword}*", None
    
    msg = f"🔍 *Hasil Pencarian: \"{keyword}\"*\nDitemukan {len(found)} lowongan\n\n"
    inline_keyboard = []
    
    for i, job in enumerate(found[:max_results], 1):
        score = job.get("Score", "?")
        title = job.get("Job Title", "?")
        company = job.get("Company", "?")
        link = job.get("Link", "")
        
        msg += f"*{i}. {title}*\n"
        msg += f"   🏢 {company} | ⭐ {score}/100\n\n"
        
        if link and link not in ("Tidak tercantum", ""):
            inline_keyboard.append([{"text": f"🔗 {company[:25]}", "url": link}])
    
    if len(found) > max_results:
        msg += f"_...dan {len(found) - max_results} hasil lainnya._"
    
    reply_markup = {"inline_keyboard": inline_keyboard} if inline_keyboard else None
    return msg, reply_markup

# ─────────────────────────────────────────────
# MORNING BRIEF (on-demand)
# ─────────────────────────────────────────────

def check_morning_brief(force=False):
    """Generate morning brief — on-demand only when called via /brief."""
    if not force:
        return
    
    apply_today_path = os.path.join(DIRECTORY, "output", "latest", "apply_today.csv")
    if os.path.exists(apply_today_path):
        try:
            jobs = []
            with open(apply_today_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    score = float(row.get("Score", 0) or 0)
                    jobs.append((row, score))
            
            if jobs:
                jobs.sort(key=lambda x: x[1], reverse=True)
                top_3 = jobs[:3]
                
                msg = "🌅 *Top 3 Lowongan MT Terbaik*\n\n"
                inline_keyboard = []
                
                for idx, (job, score) in enumerate(top_3, 1):
                    msg += f"{idx}. *{job.get('Job Title')}* @ {job.get('Company')}\n"
                    msg += f"   🎯 Score: {score}\n"
                    msg += f"   📍 Lokasi: {job.get('Location')}\n\n"
                    
                    if job.get('Link') and job.get('Link') != 'Tidak tercantum':
                        inline_keyboard.append([{"text": f"🔗 Apply: {job.get('Company')[:20]}", "url": job.get('Link')}])
                        
                msg += "Semangat apply hari ini! 💪"
                reply_markup = {"inline_keyboard": inline_keyboard} if inline_keyboard else None
                send_message(TELEGRAM_CHAT_ID, msg, reply_markup=reply_markup)
            else:
                send_message(TELEGRAM_CHAT_ID, "📭 Belum ada data Apply Today. Coba jalankan `/run` dulu.")
        except Exception as e:
            print(f"Failed to generate morning brief: {e}")
    else:
        send_message(TELEGRAM_CHAT_ID, "📭 File apply_today.csv belum ada. Coba jalankan `/run` dulu.")

# ─────────────────────────────────────────────
# KEYBOARD
# ─────────────────────────────────────────────

MAIN_KEYBOARD = {
    "keyboard": [
        [{"text": "📊 Lihat Stats"}, {"text": "🌅 Morning Brief"}],
        [{"text": "🚀 Jalankan Scraper"}, {"text": "📋 Apply Today"}],
        [{"text": "🏆 Top Lowongan"}, {"text": "🏓 Ping Bot"}]
    ],
    "resize_keyboard": True,
    "is_persistent": True
}

# ─────────────────────────────────────────────
# COMMAND PROCESSOR
# ─────────────────────────────────────────────

def process_command(text, chat_id):
    parts = text.strip().split(None, 1)
    cmd = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""

    if cmd == '/ping' or text == '🏓 Ping Bot':
        send_message(chat_id, "🏓 Pong! Agent is running normally.")

    elif cmd == '/stats' or text == '📊 Lihat Stats':
        send_message(chat_id, get_stats())

    elif cmd == '/run' or text == '🚀 Jalankan Scraper':
        _run_scraper_with_progress(chat_id)

    elif cmd == '/brief' or text == '🌅 Morning Brief':
        check_morning_brief(force=True)

    elif cmd == '/topjobs' or text == '🏆 Top Lowongan':
        result = get_top_jobs(5)
        if isinstance(result, tuple):
            msg, markup = result
            send_message(chat_id, msg, reply_markup=markup)
        else:
            send_message(chat_id, result)

    elif cmd == '/apply' or text == '📋 Apply Today':
        msg, markup = get_apply_today()
        send_message(chat_id, msg, reply_markup=markup)

    elif cmd == '/search':
        if not args.strip():
            send_message(chat_id, "🔍 Cara pakai: `/search [kata kunci]`\nContoh: `/search logistik`")
        else:
            msg, markup = search_jobs(args.strip())
            send_message(chat_id, msg, reply_markup=markup)

    elif cmd in ('/help', '/start') or text == 'Mulai':
        help_text = (
            "🤖 *MT Job Tracker Agent*\n\n"
            "Gunakan tombol di bawah atau perintah berikut:\n\n"
            "🚀 `/run` — Jalankan scraper (dengan progress update)\n"
            "📊 `/stats` — Lihat statistik dashboard\n"
            "🌅 `/brief` — Morning brief top 3 lowongan\n"
            "🏆 `/topjobs` — Top 5 lowongan terbaik saat ini\n"
            "📋 `/apply` — Daftar Apply Today\n"
            "🔍 `/search [kata]` — Cari lowongan\n"
            "🏓 `/ping` — Cek status bot"
        )
        send_message(chat_id, help_text, reply_markup=MAIN_KEYBOARD)

# ─────────────────────────────────────────────
# SCRAPER WITH LIVE PROGRESS
# ─────────────────────────────────────────────

def _run_scraper_with_progress(chat_id):
    """Run scraper as subprocess with real-time Telegram progress updates."""
    # Send initial message and get its ID for editing
    msg_id = send_message_get_id(chat_id, "⏳ *Memulai Scraper...*\nMenghubungi sumber lowongan kerja...")
    
    script_path = os.path.join(DIRECTORY, "scraper", "main.py")
    
    try:
        process = subprocess.Popen(
            ["python3", script_path, "--powerful"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=DIRECTORY
        )
        
        discovered = 0
        detail_started = False
        last_update_time = time.time()
        UPDATE_INTERVAL = 8  # seconds between Telegram edits to avoid rate limit

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            print(f"[SCRAPER] {line}")

            now = time.time()
            should_update = (now - last_update_time) >= UPDATE_INTERVAL

            # Detect discovery phase
            if "Discovering:" in line:
                source_name = line.split("Discovering:")[-1].strip()
                if should_update and msg_id:
                    edit_message(chat_id, msg_id,
                        f"🔍 *Scraper Berjalan...*\n\n"
                        f"📡 Discovery: `{source_name[:40]}`\n"
                        f"🔗 Link ditemukan: {discovered}")
                    last_update_time = now

            # Detect link count from page log
            elif "Page" in line and "links" in line:
                m = re.search(r'total (\d+)', line)
                if m:
                    discovered = int(m.group(1))

            # Detect detail scraping start
            elif "[DETAIL MODE]" in line:
                m = re.search(r'(\d+) new links', line)
                if m:
                    discovered = int(m.group(1))
                detail_started = True
                if msg_id:
                    edit_message(chat_id, msg_id,
                        f"⚙️ *Memproses Detail Lowongan...*\n\n"
                        f"🔗 Total link ditemukan: *{discovered}*\n"
                        f"🔄 Sedang scraping halaman detail...")
                    last_update_time = now

            # Detect scraping individual pages
            elif detail_started and "Parsing detail:" in line and should_update:
                progress_m = re.search(r'\[(\d+)/(\d+)\]', line)
                if progress_m and msg_id:
                    current = int(progress_m.group(1))
                    total = int(progress_m.group(2))
                    pct = int((current / total) * 100) if total > 0 else 0
                    bar_filled = int(pct / 10)
                    bar = "█" * bar_filled + "░" * (10 - bar_filled)
                    edit_message(chat_id, msg_id,
                        f"⚙️ *Memproses Detail Lowongan...*\n\n"
                        f"`{bar}` {pct}%\n"
                        f"📄 {current}/{total} halaman diproses")
                    last_update_time = now

        process.wait()
        return_code = process.returncode

        if return_code == 0:
            # Read summary for final message
            summary_file = os.path.join(DIRECTORY, "output", "latest", "run_summary.json")
            total_exported = 0
            total_apply = 0
            try:
                with open(summary_file, "r") as f:
                    s = json.load(f)
                    total_exported = s.get("total_exported", 0)
                    total_apply = s.get("total_apply_today", 0)
                    discovered = s.get("total_links_discovered", discovered)
            except:
                pass
            
            final_msg = (
                f"✅ *Scraping Selesai!*\n\n"
                f"🔗 Link ditemukan: *{discovered}*\n"
                f"📋 Total lowongan: *{total_exported}*\n"
                f"🎯 Apply Today: *{total_apply}* lowongan prioritas\n\n"
                f"Gunakan /apply untuk melihat rekomendasi, atau /topjobs untuk top 5 terbaik."
            )
            if msg_id:
                edit_message(chat_id, msg_id, final_msg)
            else:
                send_message(chat_id, final_msg)
        else:
            err_msg = f"❌ *Scraper gagal* (exit code {return_code})\n\nCoba jalankan lagi atau periksa log."
            if msg_id:
                edit_message(chat_id, msg_id, err_msg)
            else:
                send_message(chat_id, err_msg)

    except Exception as e:
        err = f"❌ *Error menjalankan scraper:*\n`{str(e)[:200]}`"
        if msg_id:
            edit_message(chat_id, msg_id, err)
        else:
            send_message(chat_id, err)

# ─────────────────────────────────────────────
# MAIN POLLING LOOP
# ─────────────────────────────────────────────

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

                        if text and str(chat_id) == str(TELEGRAM_CHAT_ID):
                            print(f"Received command: {text}")
                            process_command(text, chat_id)

            # All proactive scheduled tasks DISABLED — on-demand only
            # check_reminders()
            # check_morning_brief()
            # check_deadlines()
            # check_follow_up()
            # check_weekly_stats()
            # check_auto_scraper()

        except requests.exceptions.RequestException:
            time.sleep(5)
        except Exception as e:
            print(f"Error in polling loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
