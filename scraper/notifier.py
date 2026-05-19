import requests

try:
    from config.notifications import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
except ImportError:
    TELEGRAM_BOT_TOKEN = ""
    TELEGRAM_CHAT_ID = ""

def send_telegram_message(text, parse_mode="Markdown"):
    """
    Mengirim pesan ke Telegram menggunakan Bot API.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("    ! Telegram token/chat_id tidak dikonfigurasi. Melewati notifikasi.")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("    * Notifikasi Telegram berhasil dikirim!")
            return True
        else:
            print(f"    ! Gagal mengirim Telegram: {response.text}")
            return False
    except Exception as e:
        print(f"    ! Error mengirim Telegram: {e}")
        return False

def notify_high_matches(ranked_jobs, run_id):
    """
    Memformat dan mengirimkan lowongan skor tinggi (>= 85) ke Telegram.
    """
    # Ambil lowongan apply today dengan skor tinggi
    top_jobs = [j for j in ranked_jobs if j.get("match_score", 0) >= 80 and j.get("not_apply_today_reason") is None]
    
    if not top_jobs:
        # Fallback jika tidak ada skor tinggi
        top_jobs = [j for j in ranked_jobs if j.get("not_apply_today_reason") is None][:3]
        if not top_jobs:
            return # Tidak ada rekomendasi apply today
            
    message = f"🚀 *MT Job Tracker Selesai*\nRun ID: `{run_id}`\n\n"
    message += f"Ditemukan {len(top_jobs)} lowongan prioritas:\n\n"
    
    for i, job in enumerate(top_jobs[:5], 1):
        title = job.get("job_title", "Posisi Tidak Diketahui")
        company = job.get("company", "Perusahaan Tidak Diketahui")
        score = job.get("match_score", 0)
        url = job.get("job_url", "") or job.get("apply_url", "")
        gpa_status = job.get("gpa_status", "")
        deadline_status = job.get("deadline_status", "")
        days_left = job.get("days_until_deadline", "")
        
        # GPA emoji
        gpa_emoji = "✅" if gpa_status in ("Meets GPA", "Priority GPA Match", "No GPA Listed") else "⚠️" if "Slight" in gpa_status else "❌" if "High" in gpa_status else "📋"
        
        # Deadline text
        dl_text = ""
        if deadline_status == "Expired":
            dl_text = "❌ Expired"
        elif days_left and str(days_left).replace('.','').replace('-','').isdigit():
            dl_text = f"⏰ {int(float(days_left))}d lagi"
        elif deadline_status:
            dl_text = f"📅 {deadline_status}"
        
        message += f"*{i}. {company}*\n"
        message += f"📌 {title}\n"
        message += f"⭐ Skor: {score}/100\n"
        if gpa_status:
            message += f"{gpa_emoji} GPA: {gpa_status}\n"
        if dl_text:
            message += f"{dl_text}\n"
        if url and url != "Tidak tercantum":
            message += f"🔗 [Link Lamaran]({url})\n"
        message += "\n"
        
    if len(top_jobs) > 5:
        message += f"...dan {len(top_jobs) - 5} lowongan lainnya. Cek Dashboard lokal Anda!"
        
    send_telegram_message(message)
