import os
import json
import asyncio

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

async def parse_with_llm(text):
    if not HAS_GENAI:
        return None
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
        
    try:
        genai.configure(api_key=api_key)
        # Using flash model for fast and cheap extraction
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Extract the following job details from the text below. 
        Return ONLY a valid JSON object with the following keys, and nothing else (no markdown format, no backticks):
        "job_title" (string or null),
        "company" (string or null),
        "location" (string or null),
        "salary" (string or null),
        "requirements" (string or null)
        
        Text:
        {text[:5000]}
        """
        
        response = await asyncio.to_thread(model.generate_content, prompt)
        res_text = response.text.strip()
        
        # Clean up markdown if model still returns it
        if res_text.startswith("```json"):
            res_text = res_text[7:]
        if res_text.endswith("```"):
            res_text = res_text[:-3]
            
        data = json.loads(res_text.strip())
        return data
    except Exception as e:
        # Silently fail and fallback to regex so it doesn't interrupt the pipeline
        print(f"      ! LLM fallback warning: {e}")
        return None
