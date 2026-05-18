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

PORT = int(os.environ.get('PORT', 8000))
IS_CLOUD = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER') or os.environ.get('IS_CLOUD')
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(DIRECTORY, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
STATE_FILE = os.path.join(DATA_DIR, "dashboard_state.json")

# Import configuration to get Gemini API key
try:
    import sys
    sys.path.append(DIRECTORY)
    from config.ai import GEMINI_API_KEY
    from candidate_profile import CANDIDATE_PROFILE
except ImportError:
    GEMINI_API_KEY = ""
    CANDIDATE_PROFILE = {}

def get_state():
    if not os.path.exists(STATE_FILE):
        return {"kanban": {}, "hidden": {}}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"kanban": {}, "hidden": {}}

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
                save_state(state_data)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"success": true}')
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

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            
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

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
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
    
    # Auto-start Telegram Bot Agent
    try:
        from telegram_agent import main as telegram_main
        telegram_thread = threading.Thread(target=telegram_main, daemon=True)
        telegram_thread.start()
        print("🤖 Telegram Agent started in background.")
    except Exception as e:
        print(f"⚠️  Telegram Agent gagal start: {e}")
    
    if not IS_CLOUD:
        url = f"http://localhost:{PORT}/dashboard/"
        print(f"Opening browser to {url}")
        webbrowser.open(url)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server.")
