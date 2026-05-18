#!/usr/bin/env python3
import http.server
import socketserver
import webbrowser
import os
import threading
import time
import json
import urllib.request
import urllib.error
import socket

PORT = int(os.environ.get('PORT', 8000))
IS_CLOUD = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER') or os.environ.get('IS_CLOUD')
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(DIRECTORY, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
STATE_FILE = os.path.join(DATA_DIR, "dashboard_state.json")

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# Import configuration to get Gemini API key
try:
    import sys
    sys.path.append(DIRECTORY)
    from config.ai import GEMINI_API_KEY
    from candidate_profile import CANDIDATE_PROFILE
except ImportError:
    GEMINI_API_KEY = ""
    CANDIDATE_PROFILE = {}

import re
import glob
import csv

_historical_jobs_cache = {}
_cached_kanban_keys = set()

def slugify(s):
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r'[^a-z0-9]', '', s)
    return s[:80]

def build_historical_jobs_cache(state_kanban_keys):
    historical_jobs = {}
    if not state_kanban_keys:
        return historical_jobs
        
    keys_set = set(state_kanban_keys)
    output_dir = os.path.join(DIRECTORY, "output")
    if not os.path.exists(output_dir):
        return historical_jobs
        
    csv_paths = glob.glob(os.path.join(output_dir, "**", "*.csv"), recursive=True)
    
    for path in csv_paths:
        if len(keys_set) == 0:
            break
        try:
            with open(path, mode='r', encoding='utf-8-sig', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    company = row.get("Company", "")
                    title = row.get("Job Title", "") or row.get("job_title", "")
                    location = row.get("Location", "")
                    
                    if not company and not title:
                        continue
                        
                    slug1 = slugify(company + title + location)
                    slug2 = slugify(title + company + location)
                    
                    match_key = None
                    if slug1 in keys_set:
                        match_key = slug1
                    elif slug2 in keys_set:
                        match_key = slug2
                        
                    if match_key:
                        historical_jobs[match_key] = {
                            "Company": company,
                            "Job Title": title,
                            "Location": location,
                            "Url": row.get("Url", "") or row.get("job_url", "") or row.get("Link", ""),
                            "URL": row.get("Url", "") or row.get("job_url", "") or row.get("Link", ""),
                            "Score": float(row.get("Score", 0) or row.get("match_score", 0) or 0),
                            "Why Match": row.get("Why Match", "") or row.get("recommendation_insight", ""),
                            "_score": float(row.get("Score", 0) or row.get("match_score", 0) or 0),
                            "_id": match_key
                        }
                        keys_set.remove(match_key)
        except Exception as e:
            pass
            
    # Add generic placeholders for keys still not found in historical CSVs
    for rem_key in keys_set:
        historical_jobs[rem_key] = {
            "Company": "Histori Pekerjaan",
            "Job Title": "Pekerjaan Terlacak (" + rem_key[:12] + ")",
            "Location": "Tidak tercantum",
            "Url": "",
            "URL": "",
            "Score": 0,
            "Why Match": "Detail pekerjaan ini diarsipkan secara lokal.",
            "_score": 0,
            "_id": rem_key
        }
            
    return historical_jobs

def get_historical_jobs(kanban_keys):
    global _historical_jobs_cache, _cached_kanban_keys
    current_keys = set(kanban_keys)
    if current_keys == _cached_kanban_keys:
        return _historical_jobs_cache
    _historical_jobs_cache = build_historical_jobs_cache(kanban_keys)
    _cached_kanban_keys = current_keys
    return _historical_jobs_cache

def get_state():
    if not os.path.exists(STATE_FILE):
        return {"kanban": {}, "hidden": {}, "apply_dates": {}, "historical_jobs": {}}
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            if "apply_dates" not in data:
                data["apply_dates"] = {}
            
            existing_historical = data.get("historical_jobs", {})
            kanban_keys = list(data.get("kanban", {}).keys())
            
            # Rebuild historical jobs cache dynamically
            fresh_historical = get_historical_jobs(kanban_keys)
            
            # Merge with existing file records for items not found in CSVs
            for k in kanban_keys:
                if k not in fresh_historical and k in existing_historical:
                    fresh_historical[k] = existing_historical[k]
                    
            data["historical_jobs"] = fresh_historical
            return data
    except Exception as e:
        return {"kanban": {}, "hidden": {}, "apply_dates": {}, "historical_jobs": {}}

def save_state(data):
    with open(STATE_FILE, "w") as f:
        json.dump(data, f)

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
        
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self):
        if self.path == '/api/state':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_state()).encode('utf-8'))
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/state':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                state_data = json.loads(post_data.decode('utf-8'))
                # Auto-record apply_date when job first moves to 'applied'
                existing = get_state()
                if "apply_dates" not in state_data:
                    state_data["apply_dates"] = existing.get("apply_dates", {})
                new_kanban = state_data.get("kanban", {})
                old_kanban = existing.get("kanban", {})
                today = time.strftime("%Y-%m-%d")
                for job_id, status in new_kanban.items():
                    if status == "applied" and job_id not in state_data["apply_dates"]:
                        state_data["apply_dates"][job_id] = today
                save_state(state_data)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"success": true}')
                
                # Trigger Google Sheets sync in background
                import threading
                import subprocess
                def run_sync():
                    try:
                        script_path = os.path.join(DIRECTORY, "sync_sheets.py")
                        subprocess.run(["python3", script_path], cwd=DIRECTORY)
                    except:
                        pass
                threading.Thread(target=run_sync, daemon=True).start()
                
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
                
        elif self.path == '/api/generate-cover':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            try:
                job_data = json.loads(post_data.decode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "Invalid JSON"}')
                return

            if not GEMINI_API_KEY:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'{"error": "GEMINI_API_KEY belum dikonfigurasi di config/ai.py"}')
                return

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
            
            prompt = f"""
            Buatkan draft email (Cover Letter) profesional dalam bahasa yang paling cocok dengan posisi ini (Inggris atau Indonesia) untuk melamar lowongan berikut.

            === PROFIL SAYA ===
            Nama: {CANDIDATE_PROFILE.get('name')}
            Pendidikan: {CANDIDATE_PROFILE.get('degree')} dari {CANDIDATE_PROFILE.get('university')}
            
            === PEKERJAAN ===
            Perusahaan: {job_data.get('company')}
            Posisi: {job_data.get('title')}
            
            Fokuskan pada kemampuan operasional, supply chain, kepemimpinan, atau adaptabilitas saya yang cepat sebagai fresh graduate.
            Buatlah singkat, profesional, langsung pada intinya (tidak lebih dari 3-4 paragraf pendek). 
            Berikan sapaan kepada "Hiring Manager" atau "Tim Rekrutmen {job_data.get('company')}".
            Jangan gunakan placeholder yang tidak saya berikan (seperti [Alamat Perusahaan]), biarkan natural saja.
            Hanya balas dengan isi suratnya.
            """

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7}
            }
            
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            
            try:
                response = urllib.request.urlopen(req, timeout=20)
                result = json.loads(response.read().decode('utf-8'))
                cover_letter = result['candidates'][0]['content']['parts'][0]['text']
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"cover_letter": cover_letter}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

        elif self.path == '/api/generate-interview-prep':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                job_data = json.loads(post_data.decode('utf-8'))
            except:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "Invalid JSON"}')
                return

            if not GEMINI_API_KEY:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'{"error": "GEMINI_API_KEY belum dikonfigurasi"}')
                return

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
            prompt = f"""
            Kamu adalah seorang HR Coach profesional. Buatkan daftar persiapan wawancara untuk kandidat berikut:

            === PROFIL KANDIDAT ===
            Nama: {CANDIDATE_PROFILE.get('name')}
            Pendidikan: {CANDIDATE_PROFILE.get('degree')} dari {CANDIDATE_PROFILE.get('university')}

            === POSISI YANG DILAMAR ===
            Perusahaan: {job_data.get('company')}
            Posisi: {job_data.get('title')}

            Buatkan dalam format berikut (dalam Bahasa Indonesia):
            1. **5 Pertanyaan yang Kemungkinan Besar Ditanyakan** beserta contoh jawaban terbaik (sesuaikan dengan profil kandidat).
            2. **3 Pertanyaan yang Harus Ditanyakan Balik ke HRD** untuk menunjukkan antusiasme.
            3. **Tips Singkat** tentang budaya perusahaan tersebut jika kamu tahu.

            Fokuskan jawaban pada pengalaman organisasi, kemampuan adaptasi cepat, dan relevansi pendidikan.
            Jawab langsung tanpa pengantar.
            """
            payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.5}}
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            try:
                response = urllib.request.urlopen(req, timeout=30)
                result = json.loads(response.read().decode('utf-8'))
                text = result['candidates'][0]['content']['parts'][0]['text']
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"prep": text}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

        elif self.path == '/api/generate-resume-tips':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                job_data = json.loads(post_data.decode('utf-8'))
            except:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error": "Invalid JSON"}')
                return

            if not GEMINI_API_KEY:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'{"error": "GEMINI_API_KEY belum dikonfigurasi di config/ai.py"}')
                return

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
            prompt = f"""
            Sebagai konsultan karir profesional dan ahli ATS (Applicant Tracking System), tolong berikan 5 bullet points spesifik 
            yang harus kandidat ini tambahkan ke dalam CV-nya agar lolos seleksi otomatis (ATS) dan mata HRD untuk lowongan ini.

            === PROFIL KANDIDAT ===
            Nama: {CANDIDATE_PROFILE.get('name')}
            Pendidikan: {CANDIDATE_PROFILE.get('degree')} dari {CANDIDATE_PROFILE.get('university')}
            Pengalaman/Proyek: Memiliki latar belakang kuat di Operasional, Supply Chain Management, Logistics, dan Process Improvement.
            Memiliki pengalaman kewirausahaan yang menunjukkan inisiatif bisnis praktis.

            === POSISI YANG DILAMAR ===
            Perusahaan: {job_data.get('company')}
            Posisi: {job_data.get('title')}

            Instruksi:
            - Berikan 5 poin kalimat pencapaian/pengalaman (bullet points) yang bisa langsung di-copy-paste oleh kandidat ke CV-nya.
            - Gunakan bahasa yang relevan dengan perusahaan ({job_data.get('company')}).
            - Jangan bertele-tele, langsung berikan 5 poin tersebut menggunakan Markdown bullet points.
            """
            payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.5}}
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            try:
                response = urllib.request.urlopen(req, timeout=30)
                result = json.loads(response.read().decode('utf-8'))
                text = result['candidates'][0]['content']['parts'][0]['text']
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"tips": text}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

def start_server():
    with ReusableTCPServer(("", PORT), Handler) as httpd:
        env = "CLOUD" if IS_CLOUD else "LOCAL"
        print(f"[{env}] Serving dashboard at http://0.0.0.0:{PORT}/dashboard/")
        httpd.serve_forever()

if __name__ == "__main__":
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    time.sleep(1)
    
    local_ip = get_local_ip()
    print("\n" + "━"*52)
    print("  🚀  MT Job Tracker — SIAP!")
    print("━"*52)
    print(f"  💻  MacBook   →  http://localhost:{PORT}/dashboard/")
    print(f"  📱  HP (WiFi) →  http://{local_ip}:{PORT}/dashboard/")
    print("━"*52)
    
    # Auto-start Telegram Bot Agent
    try:
        from telegram_agent import main as telegram_main
        telegram_thread = threading.Thread(target=telegram_main, daemon=True)
        telegram_thread.start()
        print("  🤖  Telegram  →  Running")
    except Exception as e:
        print(f"  ⚠️   Telegram  →  Gagal ({e})")
    
    print("━"*52)
    print("  Tekan Ctrl+C untuk berhenti.\n")
    
    if not IS_CLOUD:
        webbrowser.open(f"http://localhost:{PORT}/dashboard/")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server.")
