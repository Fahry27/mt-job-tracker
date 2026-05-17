"""GPA Extraction & Scoring Helper — Audit v2.
Candidate GPA: 3.29 (Fahry Ramadhan)
"""
import re

CANDIDATE_GPA = 3.29

GPA_NUMERIC_PATTERNS = [
    r'(?:IPK|ipk)\s*(?:minimal?\.?|min\.?|minimum)\s*(\d[.,]\d{1,2})',
    r'(?:GPA|gpa)\s*(?:minimal?\.?|min\.?|minimum)\s*(\d[.,]\d{1,2})',
    r'(?:minimum|minimal?\.?)\s*(?:cumulative\s+)?(?:GPA|gpa|IPK|ipk)\s*(\d[.,]\d{1,2})',
    r'(?:memiliki|dengan)\s+(?:IPK|ipk)\s+(?:minimal?\.?|min\.?|minimum)\s*(\d[.,]\d{1,2})',
    r'(?:IPK|ipk)\s+(?:S1|s1)\s+(?:minimal?\.?|min\.?|minimum)\s*(\d[.,]\d{1,2})',
    r'(?:S1|s1)\s+(?:IPK|ipk)\s+(?:minimal?\.?|min\.?|minimum)\s*(\d[.,]\d{1,2})',
    r'(?:Bachelor|bachelor)\s+(?:GPA|gpa)\s*(\d[.,]\d{1,2})',
    r'(?:IPK|ipk|GPA|gpa)\s*(?:>=?|≥)\s*(\d[.,]\d{1,2})',
    r'(?:IPK|ipk|GPA|gpa)\s+(\d[.,]\d{1,2})(?:\s|$|,|;|\))',
]

GPA_QUALITATIVE_PATTERNS = [
    r'excellent\s+academic\s+record',
    r'strong\s+academic\s+record',
    r'outstanding\s+academic',
    r'prestasi\s+akademik\s+(?:baik|bagus|tinggi|unggul)',
    r'academic\s+achievement',
    r'akademik\s+yang\s+baik',
    r'academic\s+record\s+yang\s+baik',
    r'nilai\s+akademik\s+(?:baik|tinggi)',
]

def _normalize_gpa(raw):
    try:
        return round(float(raw.replace(",", ".")), 2)
    except (ValueError, AttributeError):
        return None

def _get_text(job):
    fields = ["job_description_summary", "description", "requirements", "responsibilities",
              "qualifications", "job_title", "raw_text", "job_description",
              "why_match", "gaps_or_concerns", "suggested_cv_tailoring"]
    return " ".join(str(job.get(f, "")) for f in fields if str(job.get(f, "")) != "Tidak tercantum")

def extract_gpa_requirement(job):
    text = _get_text(job)
    if not text:
        return None, False
    for pat in GPA_NUMERIC_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = _normalize_gpa(m.group(1))
            if val and 2.0 <= val <= 4.0:
                return val, False
    for pat in GPA_QUALITATIVE_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return None, True
    return None, False

def calculate_gpa_fields(job, candidate_gpa=CANDIDATE_GPA):
    gpa_val, is_qual = extract_gpa_requirement(job)
    r = {"gpa_required": "Tidak tercantum", "gpa_gap": "Tidak tercantum",
         "gpa_status": "No GPA Listed", "gpa_note": "No GPA requirement detected",
         "gpa_penalty": 0, "gpa_reason_codes": ["GPA_NOT_LISTED"]}

    if gpa_val is not None:
        r["gpa_required"] = f"{gpa_val:.2f}"
        gap = round(gpa_val - candidate_gpa, 2)
        if gpa_val <= 3.00:
            r["gpa_gap"] = 0
            r["gpa_status"] = "Priority GPA Match"
            r["gpa_note"] = f"GPA {candidate_gpa} comfortably exceeds {gpa_val:.2f}"
            r["gpa_penalty"] = 5
            r["gpa_reason_codes"] = ["GPA_PRIORITY_MATCH"]
        elif gpa_val <= 3.25:
            r["gpa_gap"] = 0
            r["gpa_status"] = "Priority GPA Match"
            r["gpa_note"] = f"GPA {candidate_gpa} exceeds requirement {gpa_val:.2f}"
            r["gpa_penalty"] = 4
            r["gpa_reason_codes"] = ["GPA_PRIORITY_MATCH"]
        elif gpa_val <= 3.29:
            r["gpa_gap"] = 0
            r["gpa_status"] = "Meets GPA"
            r["gpa_note"] = f"GPA {candidate_gpa} meets requirement {gpa_val:.2f}"
            r["gpa_penalty"] = 2
            r["gpa_reason_codes"] = ["GPA_MEETS"]
        elif gpa_val <= 3.35:
            r["gpa_gap"] = gap
            r["gpa_status"] = "Slight GPA Gap"
            r["gpa_note"] = f"GPA {candidate_gpa} slightly below {gpa_val:.2f}"
            r["gpa_penalty"] = -8
            r["gpa_reason_codes"] = ["GPA_RISK_SLIGHT", "GPA_RISK"]
        elif gpa_val <= 3.50:
            r["gpa_gap"] = gap
            r["gpa_status"] = "Moderate GPA Gap"
            r["gpa_note"] = f"GPA {candidate_gpa} below {gpa_val:.2f}"
            r["gpa_penalty"] = -18
            r["gpa_reason_codes"] = ["GPA_RISK_MODERATE", "GPA_RISK"]
        else:
            r["gpa_gap"] = gap
            r["gpa_status"] = "High GPA Gap"
            r["gpa_note"] = f"GPA {candidate_gpa} significantly below {gpa_val:.2f}"
            r["gpa_penalty"] = -30
            r["gpa_reason_codes"] = ["GPA_RISK_HIGH", "GPA_RISK"]
    elif is_qual:
        r["gpa_required"] = "Qualitative"
        r["gpa_status"] = "Qualitative GPA Requirement"
        r["gpa_note"] = "Only qualitative academic requirement detected"
        r["gpa_penalty"] = -3
        r["gpa_reason_codes"] = ["GPA_QUALITATIVE"]
    return r
