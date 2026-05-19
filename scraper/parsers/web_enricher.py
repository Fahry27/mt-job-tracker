"""Web Enricher — AI-powered metadata fallback for jobs with missing data.
Uses Gemini to fill in company type, salary, deadline, industry when scraper couldn't extract them.
Token-efficient: max 10 enrichments per run, 14-day cache TTL.
"""
import json
import os
import requests
import time
from datetime import datetime, timedelta

try:
    from config.ai import GEMINI_API_KEY
except ImportError:
    GEMINI_API_KEY = ""

ENRICHMENT_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "cache", "enrichment_cache.json")
MAX_ENRICHMENTS_PER_RUN = 10

def _load_cache():
    if os.path.exists(ENRICHMENT_CACHE_FILE):
        try:
            with open(ENRICHMENT_CACHE_FILE, "r") as f:
                return json.load(f)
        except: pass
    return {}

def _save_cache(cache):
    os.makedirs(os.path.dirname(ENRICHMENT_CACHE_FILE), exist_ok=True)
    with open(ENRICHMENT_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

def _needs_enrichment(job):
    """Check if a job has too many missing fields."""
    empty_count = 0
    for field in ["company", "salary", "deadline", "industry"]:
        val = str(job.get(field, "Tidak tercantum")).strip()
        if val in ("Tidak tercantum", "", "None"):
            empty_count += 1
    confidence = float(job.get("data_confidence", 100))
    score = float(job.get("match_score", 0))
    return empty_count >= 2 and confidence < 65 and score >= 55

def enrich_jobs(ranked_jobs):
    """Enrich top jobs with missing metadata using Gemini AI.
    Returns the same list with enriched fields.
    """
    if not GEMINI_API_KEY:
        print("    ! GEMINI_API_KEY not set. Skipping web enrichment.")
        return ranked_jobs

    cache = _load_cache()
    enriched_count = 0

    for job in ranked_jobs:
        if enriched_count >= MAX_ENRICHMENTS_PER_RUN:
            break

        if not _needs_enrichment(job):
            continue

        job_url = job.get("job_url", "")
        
        # Check cache (14-day TTL)
        if job_url in cache:
            cached = cache[job_url]
            cached_time = datetime.fromisoformat(cached.get("timestamp", "2000-01-01"))
            if datetime.now() - cached_time < timedelta(days=14):
                _apply_enrichment(job, cached.get("data", {}))
                continue

        # Call Gemini for enrichment
        enrichment = _call_gemini_enrichment(job)
        if enrichment:
            _apply_enrichment(job, enrichment)
            cache[job_url] = {
                "data": enrichment,
                "timestamp": datetime.now().isoformat()
            }
            enriched_count += 1
            time.sleep(1.5)  # Rate limit

    if enriched_count > 0:
        _save_cache(cache)
        print(f"    ✨ Enriched {enriched_count} jobs with AI metadata")

    return ranked_jobs

def _apply_enrichment(job, data):
    """Apply enrichment data to job dict."""
    for field in ["company_type", "estimated_salary", "industry", "deadline_info"]:
        if data.get(field) and data[field] != "unknown":
            if field == "company_type":
                job["company_type"] = data[field]
            elif field == "estimated_salary" and job.get("salary", "Tidak tercantum") == "Tidak tercantum":
                job["salary"] = data[field]
            elif field == "industry" and job.get("industry", "Tidak tercantum") == "Tidak tercantum":
                job["industry"] = data[field]
            elif field == "deadline_info":
                job["enrichment_note"] = data[field]
    job["scrape_status"] = job.get("scrape_status", "") + " + Enriched (AI)"

def _call_gemini_enrichment(job):
    """Call Gemini API to fill missing metadata."""
    company = job.get("company", "Unknown")
    title = job.get("job_title", "Unknown")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""Berikan metadata berikut tentang lowongan kerja ini. Jawab HANYA dengan JSON murni.

Posisi: {title}
Perusahaan: {company}

{{
  "company_type": "BUMN" atau "Swasta" atau "Multinasional" atau "unknown",
  "estimated_salary": "range gaji dalam Rupiah jika diketahui, atau 'unknown'",
  "industry": "sektor industri perusahaan (FMCG, Banking, Mining, dll), atau 'unknown'",
  "deadline_info": "info deadline lamaran jika diketahui, atau 'unknown'"
}}"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=12)
        if response.status_code == 200:
            result = response.json()
            text = result['candidates'][0]['content']['parts'][0]['text']
            text = text.replace('```json', '').replace('```', '').strip()
            data = json.loads(text)
            print(f"    [Enrich] {company} - {title}: type={data.get('company_type')}, industry={data.get('industry')}")
            return data
        else:
            print(f"    ! Enrichment API error ({response.status_code}) for {company}")
    except Exception as e:
        print(f"    ! Enrichment failed for {company}: {e}")
    
    return None
