"""Deadline detection and scoring helper."""
import re
import calendar
from datetime import datetime, date

INDO_MONTHS = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

DEADLINE_PATTERNS = [
    # ISO date from validThrough: 2026-05-31
    r'validthrough\s*:?\s*(\d{4})-(\d{2})-(\d{2})',
    # "deadline: 31 Mei 2026" or "batas lamaran: 31 Mei 2026"
    r'(?:deadline|batas\s+lamaran|paling\s+lambat|ditutup\s+tanggal|pendaftaran\s+(?:sampai|ditutup)|apply\s+before|closing\s+date|batas\s+akhir|berlaku\s+hingga|berlaku\s+sampai)\s*:?\s*(\d{1,2})\s+(\w+)\s+(\d{4})',
    # "closing: 31 Mei 2026"
    r'(?:deadline|closing)\s*:?\s*(\d{1,2})\s+(\w+)\s+(\d{4})',
    # "31 Mei 2026 (deadline)"
    r'(\d{1,2})\s+(\w+)\s+(\d{4})\s*(?:\(deadline\)|\(batas\))',
    # ISO date anywhere in text: 2026-05-31 or 2026/05/31
    r'\b(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b',
]

def _parse_date_match(groups, pattern_idx):
    try:
        if pattern_idx == 0:  # validThrough ISO
            return date(int(groups[0]), int(groups[1]), int(groups[2]))
        if pattern_idx == 4:  # ISO date YYYY-MM-DD
            return date(int(groups[0]), int(groups[1]), int(groups[2]))
        # patterns 1,2,3: day month_str year
        day, month_str, year = int(groups[0]), groups[1].lower(), int(groups[2])
        month = INDO_MONTHS.get(month_str)
        if not month:
            return None
        return date(year, month, day)
    except (ValueError, TypeError):
        return None

def _extract_deadline_from_url(url):
    """Extract approximate deadline from URL pattern /MM/YYYY/ (common on lokerbumn.com)."""
    if not url:
        return None
    # Match /NN/YYYY/ where NN is 01-12 (month) and YYYY is year
    m = re.search(r'/(\d{2})/(20\d{2})/', url)
    if m:
        try:
            month = int(m.group(1))
            year = int(m.group(2))
            if 1 <= month <= 12 and 2024 <= year <= 2030:
                # Use last day of that month as estimated deadline
                last_day = calendar.monthrange(year, month)[1]
                return date(year, month, last_day)
        except (ValueError, TypeError):
            pass
    return None

def extract_deadline(job):
    # First try URL-based extraction (fast, works well for lokerbumn.com)
    url_deadline = _extract_deadline_from_url(job.get("job_url") or job.get("Link") or "")
    if url_deadline:
        return url_deadline

    fields = ["deadline", "deadline_parsed", "job_description_summary", "description",
              "requirements", "responsibilities", "gaps_or_concerns", "raw_text",
              "job_description", "why_match"]
    text = " ".join(str(job.get(f, "")) for f in fields if str(job.get(f, "")) != "Tidak tercantum")
    if not text.strip():
        return None
    for i, pattern in enumerate(DEADLINE_PATTERNS):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return _parse_date_match(m.groups(), i)
    return None


def calculate_deadline_fields(job, reference_date=None):
    if reference_date is None:
        reference_date = date.today()
    deadline = extract_deadline(job)
    result = {
        "deadline_parsed": "Tidak tercantum",
        "deadline_status": "Unknown",
        "days_until_deadline": "Tidak tercantum",
        "urgency_level": "Unknown",
        "deadline_note": "No deadline detected",
        "deadline_penalty": 0,
        "deadline_reason_codes": ["DEADLINE_UNKNOWN"],
    }
    if deadline is None:
        return result
    delta = (deadline - reference_date).days
    result["deadline_parsed"] = deadline.isoformat()
    result["days_until_deadline"] = delta
    if delta < 0:
        result["deadline_status"] = "Expired"
        result["urgency_level"] = "Expired"
        result["deadline_note"] = f"Expired {abs(delta)} days ago ({deadline.isoformat()})"
        result["deadline_penalty"] = -50
        result["deadline_reason_codes"] = ["DEADLINE_EXPIRED"]
    elif delta <= 3:
        result["deadline_status"] = "Open"
        result["urgency_level"] = "High"
        result["deadline_note"] = f"Urgent! {delta} days left ({deadline.isoformat()})"
        result["deadline_penalty"] = 5
        result["deadline_reason_codes"] = ["DEADLINE_OPEN", "DEADLINE_URGENT_HIGH"]
    elif delta <= 7:
        result["deadline_status"] = "Open"
        result["urgency_level"] = "Medium"
        result["deadline_note"] = f"{delta} days left ({deadline.isoformat()})"
        result["deadline_penalty"] = 3
        result["deadline_reason_codes"] = ["DEADLINE_OPEN", "DEADLINE_URGENT_MEDIUM"]
    else:
        result["deadline_status"] = "Open"
        result["urgency_level"] = "Low"
        result["deadline_note"] = f"{delta} days left ({deadline.isoformat()})"
        result["deadline_penalty"] = 0
        result["deadline_reason_codes"] = ["DEADLINE_OPEN"]
    return result
