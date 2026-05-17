import os
import json
import urllib.request
import urllib.error
import sys

# Adjust path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from config.ai import GEMINI_API_KEY
except ImportError:
    GEMINI_API_KEY = ""

def generate_market_insights(jobs_list, output_dir):
    if not GEMINI_API_KEY:
        print("Skipping Market Insights: GEMINI_API_KEY is not configured.")
        return
        
    print("🤖 AI is analyzing market trends...")
    
    # Ambil sampel 30 pekerjaan terbaik agar tidak melampaui token limit terlalu besar
    sample_jobs = jobs_list[:30]
    
    text_data = ""
    for j in sample_jobs:
        text_data += f"Title: {j.get('Job Title')}\n"
        text_data += f"Company: {j.get('Company')}\n"
        text_data += f"Desc: {str(j.get('Description', ''))[:400]}\n"
        text_data += f"Req: {str(j.get('Requirements', ''))[:400]}\n---\n"
        
    prompt = f"""
    You are an expert HR Data Analyst. Analyze the following Management Trainee job postings in Indonesia.
    Return ONLY a valid JSON string (no markdown, no backticks) with the following exact structure:
    {{
        "top_skills": [
            {{"skill": "Name of Skill 1", "demand": "Tinggi"}},
            {{"skill": "Name of Skill 2", "demand": "Tinggi"}},
            {{"skill": "Name of Skill 3", "demand": "Menengah"}},
            {{"skill": "Name of Skill 4", "demand": "Menengah"}},
            {{"skill": "Name of Skill 5", "demand": "Menengah"}}
        ],
        "hiring_trend_summary": "A 2-3 sentence summary in Indonesian about what companies are currently prioritizing (e.g. specific majors, data/tech skills, leadership).",
        "salary_insights": "A 1-sentence summary in Indonesian about salary expectations based on the data or general MT standards."
    }}
    
    Data to analyze:
    {text_data}
    """
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2}
    }
    
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        response = urllib.request.urlopen(req, timeout=40)
        result = json.loads(response.read().decode('utf-8'))
        
        response_text = result['candidates'][0]['content']['parts'][0]['text']
        
        # Bersihkan format JSON dari markdown
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
            
        insights_data = json.loads(response_text)
        
        out_path = os.path.join(output_dir, 'market_insights.json')
        with open(out_path, 'w') as f:
            json.dump(insights_data, f, indent=2)
            
        print("✅ Market Insights generated successfully.")
    except Exception as e:
        print(f"⚠️ Failed to generate market insights: {e}")
