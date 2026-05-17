import json
from bs4 import BeautifulSoup

def extract_json_ld(html):
    """
    Extract JobPosting data from <script type="application/ld+json">.
    """
    soup = BeautifulSoup(html, "lxml")
    scripts = soup.find_all("script", type="application/ld+json")
    
    for script in scripts:
        try:
            data = json.loads(script.string)
            
            # Handle list of objects
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") == "JobPosting":
                        return _format_job_posting(item)
            # Handle single object
            elif data.get("@type") == "JobPosting":
                return _format_job_posting(data)
            # Handle Graph object
            elif data.get("@graph"):
                for item in data["@graph"]:
                    if item.get("@type") == "JobPosting":
                        return _format_job_posting(item)
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue
    return None

def _format_job_posting(data):
    """Map Schema.org fields to internal job fields."""
    return {
        "job_title": data.get("title", "Tidak tercantum"),
        "company": data.get("hiringOrganization", {}).get("name") if isinstance(data.get("hiringOrganization"), dict) else data.get("hiringOrganization", "Tidak tercantum"),
        "location": _get_location(data.get("jobLocation")),
        "date_posted": data.get("datePosted", "Tidak tercantum"),
        "deadline": data.get("validThrough", "Tidak tercantum"),
        "employment_type": data.get("employmentType", "Tidak tercantum"),
        "salary": _get_salary(data.get("baseSalary")),
        "description": data.get("description", "Tidak tercantum"),
        "requirements": data.get("qualifications", "Tidak tercantum"),
        "responsibilities": data.get("responsibilities", "Tidak tercantum")
    }

def _get_location(loc):
    if not loc: return "Tidak tercantum"
    if isinstance(loc, str): return loc
    if isinstance(loc, dict):
        address = loc.get("address", {})
        if isinstance(address, str): return address
        return address.get("addressLocality", address.get("addressRegion", "Tidak tercantum"))
    return "Tidak tercantum"

def _get_salary(sal):
    if not sal: return "Tidak tercantum"
    if isinstance(sal, (int, float, str)): return str(sal)
    if isinstance(sal, dict):
        val = sal.get("value", {})
        if isinstance(val, (int, float, str)): return str(val)
        return f"{val.get('minValue', '')}-{val.get('maxValue', '')} {val.get('unitText', '')}".strip()
    return "Tidak tercantum"
