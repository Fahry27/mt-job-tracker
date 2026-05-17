import requests
import json
import time

try:
    from config.ai import GEMINI_API_KEY
except ImportError:
    GEMINI_API_KEY = ""

try:
    from candidate_profile import CANDIDATE_PROFILE
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from candidate_profile import CANDIDATE_PROFILE

def analyze_job_with_ai(job):
    """
    Menggunakan Gemini API untuk melakukan semantic matching
    dan ekstraksi gaji.
    """
    if not GEMINI_API_KEY:
        print("    ! GEMINI_API_KEY tidak diatur. Melewati AI Matching.")
        return job

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {
        "Content-Type": "application/json"
    }

    # Format profil kandidat agar lebih ringkas
    profile_summary = f"""
    Nama: {CANDIDATE_PROFILE.get('name')}
    Status: {CANDIDATE_PROFILE.get('status')}
    Pendidikan: {CANDIDATE_PROFILE.get('degree')} dari {CANDIDATE_PROFILE.get('university')} (GPA: {CANDIDATE_PROFILE.get('gpa')})
    Roles yang diminati: {', '.join(CANDIDATE_PROFILE.get('preferred_roles', [])[:10])}
    Keahlian utama: {', '.join(CANDIDATE_PROFILE.get('skills', [])[:15])}
    Pengalaman utama:
    """
    for exp in CANDIDATE_PROFILE.get('experience', [])[:2]:
        profile_summary += f"- {exp['title']} di {exp['company']} ({exp.get('type')})\n"

    prompt = f"""
    Anda adalah seorang rekruter senior. Tugas Anda adalah mencocokkan profil kandidat berikut dengan deskripsi pekerjaan.
    
    === PROFIL KANDIDAT ===
    {profile_summary}
    
    === DESKRIPSI PEKERJAAN ===
    Posisi: {job.get('job_title', '')}
    Perusahaan: {job.get('company', '')}
    Kualifikasi/Deskripsi: {job.get('job_description_summary', '')} {job.get('requirements', '')}
    
    Tugas:
    1. Berikan `semantic_score` dari 0 hingga 100 berdasarkan seberapa cocok keterampilan, pengalaman, dan latar belakang kandidat dengan deskripsi tersebut. Fokus pada nuansa dan soft skill, jangan hanya keyword matching.
    2. Berikan `reasoning` singkat (1-2 kalimat) MENGAPA cocok atau tidak cocok.
    3. Ekstrak rentang gaji jika disebutkan (dalam angka IDR). Jika tidak disebutkan, kembalikan null.
    
    Balas HANYA dengan JSON murni (tanpa markdown block ```json) dengan struktur berikut:
    {{
      "semantic_score": 85,
      "reasoning": "Kandidat memiliki latar belakang bisnis internasional dan pengalaman logistik yang sangat relevan dengan peran Operasional ini.",
      "estimated_salary_min": 5000000,
      "estimated_salary_max": 7000000
    }}
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            result_json = response.json()
            text_response = result_json['candidates'][0]['content']['parts'][0]['text']
            
            # Bersihkan markdown
            text_response = text_response.replace('```json', '').replace('```', '').strip()
            ai_data = json.loads(text_response)
            
            # Gabungkan dengan skor base
            base_score = float(job.get("match_score", 0))
            ai_score = float(ai_data.get("semantic_score", base_score))
            
            # Final Score (60% AI, 40% Keyword/Base Rules)
            final_score = (base_score * 0.4) + (ai_score * 0.6)
            job["match_score"] = round(final_score, 1)
            
            # Update alasan
            reasoning = ai_data.get("reasoning", "")
            if reasoning:
                old_why = job.get("why_match", "")
                job["why_match"] = f"[AI] {reasoning} | {old_why}"
                
            # Update gaji jika ada
            if ai_data.get("estimated_salary_min") or ai_data.get("estimated_salary_max"):
                job["salary_ai_extracted"] = f"Rp{ai_data.get('estimated_salary_min')} - Rp{ai_data.get('estimated_salary_max')}"
                
            return job
        else:
            print(f"    ! Gemini API Error ({response.status_code})")
            return job
    except Exception as e:
        print(f"    ! Gagal memproses AI matching")
        return job
